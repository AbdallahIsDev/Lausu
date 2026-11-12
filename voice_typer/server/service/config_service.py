"""Config-mutation domain mixin for LausuService."""

import contextlib
import logging

from voice_typer.server.config_applier import SideEffectStatus
from voice_typer.server.service._app_internals import (
    app_config_mutation_lock,
    invalidate_cloud_engine,
    invalidate_llm_polisher,
)
from voice_typer.server.service._base import ServiceMixinBase

log = logging.getLogger(__name__)


class ConfigMutationMixin(ServiceMixinBase):
    """Config read / mutate / side-effects surface."""

    def _keyring_status(self) -> dict[str, object]:
        """Probe the OS keychain backend once and return a status dict."""
        try:
            from voice_typer.server import credential_store

            return credential_store.get_keyring_status()
        except Exception as exc:
            log.debug("[SERVICE] keyring_status probe failed: %s", exc)
            return {
                "available": False,
                "backend": None,
                "fallback": True,
                "reason": f"credential_store probe failed: {exc}",
            }

    def get_config(self) -> dict[str, object]:
        """Return the sanitized config (API keys redacted)."""
        # import the canonical sanitizer from the
        from voice_typer.server.config_sanitizer import sanitize_config_for_ipc

        sanitized = sanitize_config_for_ipc(self._app.config)
        # Route through the shared helper (single try/except).
        sanitized["keyring_status"] = self._keyring_status()
        # Linux window-button system snapshot (read-only, computed, NOT
        try:
            from voice_typer.server.server_platform.window_buttons import (
                system_window_buttons,
            )

            sanitized["linux_window_buttons_system"] = system_window_buttons()
        except Exception:  # snapshot must never break get_config
            log.warning(
                "[SERVICE] get_config: linux_window_buttons_system probe failed",
                exc_info=True,
            )
            sanitized["linux_window_buttons_system"] = None
        try:
            from voice_typer.server import device_caps

            sanitized["gpu_available"] = device_caps.gpu_available()
        except Exception:  # snapshot must never break get_config
            log.debug("[SERVICE] get_config: gpu_available probe failed", exc_info=True)
            sanitized["gpu_available"] = False
        try:
            from voice_typer.server import gpu_capability

            backend = getattr(self._app.config, "asr_backend", None)
            capability = gpu_capability.snapshot(
                active_backend=backend if isinstance(backend, str) else None
            )
            sanitized["gpu_capability"] = capability
            sanitized["gpu_hardware_present"] = capability["hardware_present"]
        except Exception:  # snapshot must never break get_config
            log.debug("[SERVICE] get_config: gpu_capability probe failed", exc_info=True)
            sanitized["gpu_capability"] = None
            sanitized["gpu_hardware_present"] = False
        try:
            from voice_typer.server.active_device import resolve_active_device

            # READ-ONLY computed device: what the LOADED engine reports, not
            # the persisted request in `device` (they differ on a silent
            # fallback, e.g. a CPU-only onnxruntime build). C-UI-15.
            sanitized["active_device"] = resolve_active_device(self._app)
        except Exception:  # snapshot must never break get_config
            log.debug("[SERVICE] get_config: active_device probe failed", exc_info=True)
            sanitized["active_device"] = None
        try:
            from voice_typer.server import internal_plugin_hook

            # READ-ONLY computed plugin label: the manifest name of the
            # plugin that owns dictation ("" when the local model does). The
            # sidebar caption and the tray show this instead of the model
            # name, because the model is not what is transcribing.
            sanitized["active_plugin_name"] = (
                internal_plugin_hook.plugin_display_name_for(self._app.config)
            )
        except Exception:  # snapshot must never break get_config
            log.debug("[SERVICE] get_config: plugin name probe failed", exc_info=True)
            sanitized["active_plugin_name"] = ""
        return sanitized

    def get_defaults(self) -> dict[str, object]:
        """Return default config values (sanitized)."""
        from voice_typer.server.config import Config

        # import the canonical sanitizer from the
        from voice_typer.server.config_sanitizer import sanitize_config_for_ipc

        sanitized = sanitize_config_for_ipc(Config())
        # Route through the shared helper (single try/except).
        sanitized["keyring_status"] = self._keyring_status()
        return sanitized

    # ``set_config`` and ``save_config`` were REMOVED from this

    def apply_config_side_effects(self, updates: dict) -> SideEffectStatus:
        """Apply side effects after config changes. Delegates to ConfigApplier.

        Returns
        """
        return self._config_applier.apply_config_side_effects(updates)

    def change_model(self, model_size: str) -> None:
        """Switch the active ASR model to ``model_size``."""
        self._app.change_model(model_size)

    def set_active_backend(self, backend: str) -> None:
        """Set the active ASR backend (e.g. ``"whisper"``, ``"qwen"``)."""
        self._app.models.set_active_backend(backend)

    def apply_config(self, updates: dict) -> SideEffectStatus:
        """Apply validated config updates atomically. Delegates to ConfigApplier.

        Returns
        """
        return self._config_applier.apply_config(updates)

    def reset_config_to_defaults(self, *, preserve_api_keys: bool = True) -> dict:
        """factory-reset the in-memory + on-disk config to defaults."""
        from voice_typer.server import credential_store
        from voice_typer.server.config import Config, _config_dir
        from voice_typer.server.secure_file_io import (
            _secure_atomic_write,
            _secure_read_text,
        )

        app = self._app
        # The mutation lock is one of the private attributes
        with app_config_mutation_lock(app):
            config_dir = _config_dir()
            config_file = config_dir / "config.json"
            backup_path = config_dir / "config.json.bak"

            # 1. Snapshot current config.json → config.json.bak.
            if config_file.exists():
                try:
                    raw = _secure_read_text(config_file)
                    _secure_atomic_write(backup_path, raw)
                except (OSError, ValueError) as exc:
                    log.exception("[SERVICE] reset_config_to_defaults: backup failed: %s", exc)
                    return {
                        "success": False,
                        "message": "failed to back up current config (see log)",
                    }

            # 2. Snapshot the API-key fields from the live Config
            preserved_keys: dict[str, str] = {}
            old_config = getattr(app, "config", None)
            if preserve_api_keys and old_config is not None:
                for field in credential_store.PROVIDER_TO_CONFIG_FIELD.values():
                    try:
                        value = getattr(old_config, field, "")
                    except Exception:
                        value = ""
                    if value:
                        preserved_keys[field] = value

            # 3. Construct a fresh Config (all defaults).
            new_config = Config()

            # 4. Re-apply preserved API keys.
            for field, value in preserved_keys.items():
                try:
                    setattr(new_config, field, value)
                except Exception:
                    log.debug(
                        "[SERVICE] reset_config_to_defaults: could not restore %s",
                        field,
                        exc_info=True,
                    )

            # 5. Save to disk (raises on failure: see Config.save_strict).
            old_config = app.config
            try:
                # Swap the in-memory Config BEFORE save so save() reads
                app.config = new_config
                new_config.save_strict()
            except Exception as exc:
                # Restore the pre-swap config so a save failure
                app.config = old_config
                log.exception("[SERVICE] reset_config_to_defaults: save_strict failed: %s", exc)
                return {
                    "success": False,
                    "message": "failed to persist reset config to disk (see log)",
                }

            # 6. Invalidate cached LLMPolisher / CloudEngine so the
            with contextlib.suppress(Exception):
                invalidate_llm_polisher(app)
            with contextlib.suppress(Exception):
                invalidate_cloud_engine(app)

            log.info(
                "[SERVICE] reset_config_to_defaults: reset to defaults, backup at %s, preserved %d API keys",
                backup_path,
                len(preserved_keys),
            )
            return {
                "success": True,
                "backup_path": str(backup_path) if backup_path.exists() else "",
            }


__all__ = ["ConfigMutationMixin"]
