"""Startup config reconciliation: autostart sync, model reset, onboarding reset.

Split out of ``voice_typer.server.startup_tasks`` (one concern per file);
the facade re-exports every name so existing ``startup_tasks.X`` call
sites and monkeypatch seams keep resolving.
"""

from __future__ import annotations

import logging
from pathlib import Path

from voice_typer.server import onboarding_status
from voice_typer.server.providers import AppProtocol

# Logger name stays the facade module's so log routing is unchanged.
log = logging.getLogger("voice_typer.server.startup_tasks")


def sync_autostart(app: AppProtocol) -> dict:
    """Ensure ``config.autostart`` matches the actual platform autostart state.

    returns a result dict ``{"registered": bool, "error": str | None}``
        so the caller (``ConfigApplier.apply_config_side_effects``) can
        propagate the autostart status to the ``set_config`` IPC response.
        The renderer reads ``autostart_status.registered`` /
        ``autostart_status.error`` to surface "Autostart registration
        failed: <reason>" instead of silently failing.

        The dict shape matches :func:`voice_typer.server.server_platform
        .enable_autostart_ex` so the renderer can use the same field names
        whether the status came from a config-change sync or a direct
        ``enable_autostart`` IPC call.

        Note: this function still calls the bool-returning
        ``autostart.enable_autostart`` / ``autostart.disable_autostart``
        (not the rich ``enable_autostart_ex``) so existing tests that
        monkeypatch ``voice_typer.server.server_platform.autostart.enable_autostart``
        continue to take
        effect. The error string is therefore only populated when the
        bool function raises (defensive, the production ``enable_autostart``
        catches exceptions internally and returns False, so ``error`` will
        typically be ``None`` even on failure). A future refactor that
        routes through ``enable_autostart_ex`` directly will populate
        ``error`` with the real failure reason.
    """
    # Import the autostart facade module at call time so tests that
    from voice_typer.server.server_platform import autostart as _autostart

    # One-time per-install cleanup of legacy autostart entries
    try:
        from voice_typer.server.config import _config_dir as _cfg_dir
        from voice_typer.server.server_platform import sweep_legacy_autostart_entries

        _sweep = sweep_legacy_autostart_entries(_cfg_dir())
        if _sweep.get("swept"):
            _removed = _sweep.get("removed", {})
            _total = sum(len(v) for v in _removed.values())
            if _total:
                log.info(
                    "[AUTOSTART] Legacy autostart sweep removed %s duplicate entrys: %s",
                    _total,
                    _removed,
                )
    except Exception:
        log.debug("[AUTOSTART] Legacy autostart sweep failed", exc_info=True)

    # (a): track the post-sync ACTUAL OS-level autostart state so the
    result: dict = {"registered": False, "error": None, "actual_post_sync": False}
    try:
        actual = _autostart.is_autostart_enabled()
        if app.config.autostart and not actual:
            log.info("[CONFIG] Config says autostart=true but it is disabled -- enabling")
            registered = _autostart.enable_autostart()
            # capture the post-enable state. enable_autostart()
            result = {
                "registered": bool(registered),
                "error": None,
                "actual_post_sync": bool(registered),
            }
            log.info(
                "[CONFIG] Autostart sync: enable attempted, registered=%s, post_sync_state=%s",
                result["registered"],
                result["actual_post_sync"],
            )
        elif not app.config.autostart and actual:
            log.info("[CONFIG] Config says autostart=false but it is enabled -- disabling")
            removed = _autostart.disable_autostart()
            # ``registered`` in the result dict reflects "is the
            result = {
                "registered": bool(removed),
                "error": None,
                "actual_post_sync": not bool(removed),
            }
            log.info(
                "[CONFIG] Autostart sync: disable attempted, removed=%s, post_sync_state=%s",
                result["registered"],
                result["actual_post_sync"],
            )
        else:
            # Already in sync, report the current state.
            result = {
                "registered": bool(actual),
                "error": None,
                "actual_post_sync": bool(actual),
            }
            log.info(
                "[CONFIG] Autostart already in sync (config=%s, os=%s)",
                bool(app.config.autostart),
                bool(actual),
            )
    except Exception as e:
        log.warning("[CONFIG] Autostart sync failed: %s", e)
        # (a): on failure we don't know the post-sync OS state, leave
        result = {"registered": False, "error": str(e), "actual_post_sync": False}
    return result

def reconcile_configured_model(app: AppProtocol) -> bool:
    """Clear ``config.model_size`` when the configured ASR model isn't on disk."""
    from voice_typer.server.model_registry import NO_MODEL_SIZE
    from voice_typer.server.tray_models import is_active_model_downloaded

    config = app.config
    # "No model selected" already, nothing to do.
    if getattr(config, "model_size", None) == NO_MODEL_SIZE:
        return False
    backend = getattr(config, "asr_backend", "whisper") or "whisper"
    # Cloud backends have no local model to install, don't touch.
    if backend in ("openai", "groq", "deepgram", "gemini", "custom"):
        return False
    # Model IS on disk, nothing to do.
    if is_active_model_downloaded(config):
        return False
    # Configured model is definitively absent, clear it.
    config.model_size = NO_MODEL_SIZE
    try:
        ok = config.save()
    except Exception as e:
        log.warning("[MODEL] failed to persist reconciled model_size: %s", e)
        return False
    if not ok:
        log.warning("[MODEL] failed to persist reconciled model_size (save returned False)")
        return False
    log.info(
        "[MODEL] configured %s model is not installed, cleared model_size to 'no model selected' (NO_MODEL_SIZE)",
        backend,
    )
    return True

def reset_onboarding_complete(
    config_dir: Path | None = None,
    *,
    app: object | None = None,
) -> dict:
    """Delete the ``.onboarding_complete`` AND ``.onboarding_started``
    markers so the wizard re-runs on next launch.

    This is the backend primitive for the "Re-run setup wizard"
    affordance in Settings → Advanced. The renderer calls a future
    ``onboarding_reset`` IPC handler which delegates to this function;
    on next app launch, :meth:`OnboardingController.is_first_run`
    returns True (because the marker is gone) and the wizard re-appears.

    Marker consistency: BOTH ``.onboarding_complete`` and
    ``.onboarding_started`` are deleted. The
    :meth:`OnboardingController.reset` method deletes both, the IPC
    handler must do the same or it leaves a stale
    ``.onboarding_started`` marker. If that marker survives, the
    auto-heal (in ``startup_sequence``) treats the next launch as a
    mid-wizard crash and SKIPS the auto-heal, so the wizard never
    re-appears even though the user explicitly requested a re-run.

    Parameters
    ----------
    config_dir:
        Optional override for the config directory (defaults to the
        canonical :func:`voice_typer.server.config._config_dir`).
        Used by tests to point at a tmp_path.
    app:
        Optional :class:`voice_typer.server.app.LausuApp` instance.
        When provided, the ``onboarding_completed`` flag is mutated on
        the live ``app.config`` object and persisted via
        ``app.config.save_strict()``: which acquires the config-mutation
        lock so the write cannot race a concurrent
        ``set_config`` IPC handler. When ``None`` (e.g. tests), falls
        back to a fresh ``Config.load()`` snapshot + ``cfg.save()``;
        this bypasses the lock and is acceptable for the test-only path
        but callers should pass ``app`` whenever one is in scope.

    Returns
    -------
    dict
        ``{"reset": bool, "error": str | None}`` where ``reset`` is
        True if the marker was deleted (or already absent, idempotent).
        The renderer surfaces ``error`` if the deletion failed (e.g.
        permission denied on the marker file).
    """
    try:
        if config_dir is None:
            from voice_typer.server.config import _config_dir

            config_dir = _config_dir()
        # Delete the merged ``.onboarding_status.json`` document (which
        if not onboarding_status.reset_status(config_dir):
            raise OSError("could not delete the onboarding status document")
        log.info(
            "[ONBOARDING] Reset onboarding status: %s",
            onboarding_status.status_path(config_dir),
        )
        # Also clear the ``onboarding_completed`` flag in config.json so
        if app is not None:
            try:
                cfg = getattr(app, "config", None)
                if cfg is not None and getattr(cfg, "onboarding_completed", False):
                    # Acquire the app's config-mutation lock around the
                    lock = getattr(app, "_config_mutation_lock", None)
                    if lock is not None:
                        with lock:
                            cfg.onboarding_completed = False
                            cfg.save_strict()
                    else:
                        cfg.onboarding_completed = False
                        cfg.save_strict()
                    log.info("[ONBOARDING] Cleared onboarding_completed flag in config.json (via app.config)")
            except Exception:
                log.debug("[ONBOARDING] could not clear onboarding_completed via app.config", exc_info=True)
        else:
            # Fall back to ``Config.load()`` + ``cfg.save()`` for the
            try:
                from voice_typer.server.config import Config

                cfg = Config.load()
                if getattr(cfg, "onboarding_completed", False):
                    cfg.onboarding_completed = False
                    cfg.save()
                    log.info("[ONBOARDING] Cleared onboarding_completed flag in config.json")
            except Exception:
                log.debug("[ONBOARDING] could not clear onboarding_completed in config.json", exc_info=True)
        return {"reset": True, "error": None}
    except Exception as exc:
        log.exception("[ONBOARDING] Failed to reset onboarding marker")
        return {"reset": False, "error": str(exc)}
