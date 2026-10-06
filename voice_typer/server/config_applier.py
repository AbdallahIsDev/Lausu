"""Config side-effect dispatcher (registered handlers, not an if-chain).

NOTE: see docs/code-notes/security-config.md#config-preset-handlers

Implementation split (every moved name re-exported here, so the
historical import path keeps resolving):
:mod:`voice_typer.server.config_applier_handlers` (the side-effect
handler registry + support helpers). This module keeps the ACL notify
path, the preset-override keys, and :class:`ConfigApplier` -- the
RACE-011 config-mutation lock and the SEC-002 allowlist check stay on
this facade, where tests exercise them.
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

from voice_typer.server import i18n
from voice_typer.server.branding import APP_NAME
from voice_typer.server.config_applier_handlers import (  # noqa: F401  # facade re-export
    _FILTER_CHAIN_KEYS,
    ConfigSideEffect,
    SideEffectContext,
    SideEffectStatus,
    _apply_audio_preset,
    _AudioPresetHandler,
    _AutostartSyncHandler,
    _BubbleBehaviorHandler,
    _DictationHotkeyHandler,
    _EscHotkeyHandler,
    _FilterChainHandler,
    _NotificationsHandler,
    _notify_side_effect_failure,
    _PrewarmSyncHandler,
    _RepasteHotkeyHandler,
    _TrayLeftClickHandler,
    _VolumeDuckPollHandler,
    to_filter_dict,
)

log = logging.getLogger(__name__)

# One-shot flag: the ACL-enforcement-failure tray toast fires at most
_acl_enforcement_failure_notified = False


def _maybe_notify_acl_enforcement_failure(app: Any) -> None:
    """One-time tray warning when Windows ACL enforcement failed; at most once per process."""
    global _acl_enforcement_failure_notified
    if _acl_enforcement_failure_notified:
        return
    try:
        from voice_typer.server.config._saving import acl_enforcement_failures
    except Exception:
        return
    if not acl_enforcement_failures:
        return
    _acl_enforcement_failure_notified = True
    notify = getattr(getattr(app, "tray", None), "notify", None)
    if not callable(notify):
        log.warning(
            "[CONFIG] ACL enforcement failed for %s; plaintext secrets "
            "may be readable by other local users (tray notify unavailable)",
            sorted(acl_enforcement_failures),
        )
        return
    try:
        notify(
            APP_NAME,
            i18n.t("notify.app.config_acl_failed"),
        )
    except Exception:
        log.debug("[CONFIG] tray.notify for ACL failure also failed", exc_info=True)


def _json_dumps_sorted(obj: Any) -> str:
    """Stable JSON serialization for state comparison."""
    return json.dumps(obj, sort_keys=True, default=str)


# NOTE: see docs/code-notes/security-config.md#config-preset-handlers
_PRESET_OVERRIDE_KEYS: frozenset[str] = frozenset(
    {
        "noise_filter_highpass",
        "noise_suppression_method",
        "noise_filter_gate",
        "noise_filter_eq",
        "noise_filter_compressor",
        "noise_filter_limiter",
        "noise_filter_notch",
    }
)

_AUDIO_FILTER_KEYS = (
    "noise_filter_enabled",
    "noise_filter_highpass",
    "noise_filter_gate",
    "noise_filter_rnnoise",
    "noise_filter_post_capture",
)


# Sentinel for "this Config field did not exist before setattr".
_MISSING = object()


class ConfigApplier:
    """Owns the post-config-update side-effect dispatch."""

    def __init__(self, service: Any) -> None:
        self._service = service
        self._app = service._app
        # Build the handler list at construction time. Each handler is
        self._side_effect_handlers: list[ConfigSideEffect] = [
            _AutostartSyncHandler(),
            _PrewarmSyncHandler(),
            _EscHotkeyHandler(),
            _RepasteHotkeyHandler(),
            _DictationHotkeyHandler(),
            _TrayLeftClickHandler(),
            _NotificationsHandler(),
            _BubbleBehaviorHandler(),
            _VolumeDuckPollHandler(),
            _AudioPresetHandler(),
            _FilterChainHandler(),
        ]

    def apply_config_side_effects(self, updates: dict) -> SideEffectStatus:
        """defensive net for handler bugs (``applies()`` raising, etc.)
        Side-effect status dict with the shape::
        """
        app = self._app
        config = app.config

        # accumulate side-effect statuses for the renderer.
        side_effect_status: SideEffectStatus = {
            "autostart_status": None,
            "prewarm_status": None,
        }

        ctx = SideEffectContext(
            app=app,
            config=config,
            updates=updates,
            status=side_effect_status,
        )

        for handler in self._side_effect_handlers:
            try:
                if handler.applies(updates):
                    handler.apply(ctx)
            except Exception as e:
                # Defensive: each handler is expected to catch its own
                handler_name = getattr(handler, "name", type(handler).__name__)
                log.warning(
                    "[SERVICE] Side-effect handler %s raised unexpectedly: %s",
                    handler_name,
                    e,
                    exc_info=True,
                )
                _notify_side_effect_failure(app, handler_name, e)

        # return the accumulated side-effect statuses so
        return side_effect_status

    @staticmethod
    def _empty_side_effect_status() -> SideEffectStatus:
        """Stable all-``None`` status dict for early-raise / no-sync paths."""
        return {
            "autostart_status": None,
            "prewarm_status": None,
        }

    def _maybe_autoswitch_audio_preset(self, updates: dict) -> dict:
        """Auto-switch ``audio_preset`` to ``"custom"`` for individual toggles."""
        if "audio_preset" in updates:
            return updates
        individual_overrides = _PRESET_OVERRIDE_KEYS & updates.keys()
        if not individual_overrides:
            return updates
        current_preset = getattr(self._app.config, "audio_preset", "custom")
        if current_preset == "custom":
            return updates
        log.info(
            "[CONFIG] individual filter toggles %s set via "
            "IPC while audio_preset=%r, auto-switching "
            "audio_preset to 'custom' so the user's toggle "
            "survives the next Config.load() (which would "
            "otherwise re-apply the preset and revert it)",
            sorted(individual_overrides),
            current_preset,
        )
        return {**updates, "audio_preset": "custom"}

    def _setattr_updates(self, app: Any, updates: dict) -> list[tuple[str, Any]]:
        """Set each validated key onto Config, with reverse-order rollback."""
        set_keys: list[tuple[str, Any]] = []
        try:
            for k, v in updates.items():
                old_value = getattr(app.config, k, _MISSING)
                set_keys.append((k, old_value))
                setattr(app.config, k, v)
        except Exception:
            # Restore pre-loop values for keys we already set, in
            for k, old_value in reversed(set_keys):
                try:
                    if old_value is not _MISSING:
                        setattr(app.config, k, old_value)
                except Exception:
                    log.warning(
                        "[SERVICE] failed to restore config key %s during setattr rollback",
                        k,
                        exc_info=True,
                    )
            raise
        return set_keys

    def _maybe_invalidate_llm_polisher(self, app: Any, updates: dict) -> None:
        """Drop the cached LLMPolisher when any polish credential changes."""
        from voice_typer.server import credential_store as _credential_store

        _polish_credential_fields = set(_credential_store.PROVIDER_TO_CONFIG_FIELD.values())
        if any(k.startswith("llm_") or k in _polish_credential_fields for k in updates):
            with contextlib.suppress(Exception):
                app._llm_polisher = None

    def _route_secrets_post_save(self, app: Any, updates: dict) -> None:
        """Redundant keychain routing for the no-keyring plaintext path."""
        if getattr(app.config, "_secrets_routed_in_save", True):
            return
        try:
            from voice_typer.server import credential_store

            for k, v in list(updates.items()):
                provider = credential_store.CONFIG_FIELD_TO_PROVIDER.get(k)
                if provider is None:
                    continue
                credential_store.store_secret(provider, v)
        except Exception as exc:
            log.warning(
                "[SERVICE] credential_store post-save route "
                "failed: %s, secret may not be in keychain (will "
                "fall back to plaintext in config.json on next save)",
                exc,
            )

    def _save_updates_strict(
        self,
        app: Any,
        updates: dict,
        set_keys: list[tuple[str, Any]],
    ) -> None:
        """Dirty-check + ``save_strict`` + save-failure rollback."""
        post_values = {k: getattr(app.config, k, _MISSING) for k in updates}
        pre_values = dict(set_keys)
        state_unchanged = pre_values == post_values
        if state_unchanged:
            log.debug("[SERVICE] apply_config detected no state change, skipping save_strict()")
            return
        try:
            app.config.save_strict()
        except Exception:
            # Restore in-memory snapshot under the same lock, then re-run side-effects with original values.
            for k, old_value in set_keys:
                try:
                    setattr(app.config, k, old_value)
                except Exception:
                    log.warning(
                        "[SERVICE] failed to restore config key %s during save_strict rollback",
                        k,
                        exc_info=True,
                    )
            # Re-run side-effects with the restored values.
            old_updates = dict(set_keys)
            if old_updates:
                try:
                    self.apply_config_side_effects(old_updates)
                except Exception:
                    log.warning(
                        "[SERVICE] failed to re-run side-effects during save_strict rollback",
                        exc_info=True,
                    )
            raise
        self._route_secrets_post_save(app, updates)

    def _maybe_refresh_clipboard(self, app: Any, updates: dict) -> None:
        """ADR-0010 §8.3b: propagate clipboard config changes live; failures log at WARNING."""
        clipboard_keys = {
            "clipboard_save_restore",
            "clipboard_restore_delay_ms",
            "paste_on_stop",
        }
        if not (clipboard_keys & set(updates.keys())):
            return
        try:
            app.clipboard.refresh_config(app.config)
        except Exception as exc:
            log.warning(
                "[SERVICE] clipboard.refresh_config failed: %s, "
                "clipboard config changes will not take effect until restart",
                exc,
            )

    def _post_save_tray_cleanup(self, app: Any) -> None:
        """Invalidate the tray menu cache and surface any ACL warning."""
        try:
            app.tray.invalidate_menu_cache()
        except Exception:
            log.debug("[SERVICE] tray.invalidate_menu_cache failed", exc_info=True)
        _maybe_notify_acl_enforcement_failure(app)

    def apply_config(self, updates: dict) -> SideEffectStatus:
        """RACE-011: holds the app's config-mutation lock for the full
        ``IPC_CONFIG_ALLOWLIST`` (SEC-002 defense-in-depth).
        """
        # SEC-002 defense-in-depth: even though the IPC
        # runtime, defeating SEC-002.
        from voice_typer.server.config_validators import IPC_CONFIG_ALLOWLIST

        _unknown = set(updates) - IPC_CONFIG_ALLOWLIST.keys()
        if _unknown:
            raise ValueError(
                f"SEC-002 violation: apply_config received "
                f"non-allowlisted keys {sorted(_unknown)}; the IPC "
                f"set_config handler should have dropped these via "
                f"validate_config_update. Internal callers must only "
                f"pass IPC_CONFIG_ALLOWLIST keys."
            )
        app = self._app
        # (session-3): capture the side-effect status dict for
        side_effect_status: SideEffectStatus = self._empty_side_effect_status()
        # + : snapshot pre-setattr Config state. Used for
        with app._config_mutation_lock:
            updates = self._maybe_autoswitch_audio_preset(updates)
            set_keys = self._setattr_updates(app, updates)
            self._maybe_invalidate_llm_polisher(app, updates)
            # Apply side effects inside the lock so Config mutations
            side_effect_status = self.apply_config_side_effects(updates)
            # ``save_strict`` raises RuntimeError if ``save()`` returned
            self._save_updates_strict(app, updates, set_keys)
            self._maybe_refresh_clipboard(app, updates)
        # invalidate the tray menu cache so the next menu
        self._post_save_tray_cleanup(app)
        return side_effect_status
