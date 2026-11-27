"""One authority for which provider serves dictation right now.

The answer is derived from the canonical config, never from a cached readiness
snapshot: a selected plugin owns the hotkey, an explicitly chosen non-local ASR
provider serves audio remotely, ``asr_backend=cloud`` uses the cloud engine,
and only a selected local model needs the local ASR kind. Startup, the record
start hook, model-manager warm paths, notices and tray status all ask here so
they cannot disagree about who is transcribing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

LOCAL = "local"
CLOUD = "cloud"
PLUGIN = "plugin"
REMOTE = "remote"
NONE = "none"

# ``cloud_direct`` keeps the pre-existing engine path (see routing.resolve).
_ENGINE_PROVIDER_IDS = frozenset({"", "local", "cloud_direct"})


@dataclass(frozen=True)
class DictationProvider:
    """The single provider identity shared by every dictation consumer."""

    kind: str
    name: str = ""
    id: str = ""

    @property
    def owns_dictation(self) -> bool:
        return self.kind != NONE

    @property
    def serves_local_asr(self) -> bool:
        return self.kind == LOCAL

    @property
    def label(self) -> str:
        return self.name or self.kind


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def for_config(config: Any | None, *, plugin_name: str = "") -> DictationProvider:
    """Resolve the provider from a bare config.

    ``plugin_name`` lets an app-aware caller pass the authoritative plugin
    probe result; otherwise the config's selection is used, gated on the
    plugin surface being visible. That gate matters: a hidden developer
    surface must not import plugin code or touch a browser profile.
    """
    name = _text(plugin_name)
    if name:
        return DictationProvider(PLUGIN, name)

    plugin_id = _text(getattr(config, "active_plugin", ""))
    if plugin_id:
        try:
            from voice_typer.server import internal_plugin_hook

            if internal_plugin_hook.internal_surface_enabled(config):
                display = _text(internal_plugin_hook.plugin_display_name_for(config))
                return DictationProvider(PLUGIN, display or plugin_id, plugin_id)
        except Exception:
            log.debug("[PROVIDER] plugin ownership probe failed", exc_info=True)

    provider_id = _text(getattr(config, "asr_provider", ""))
    if provider_id and provider_id not in _ENGINE_PROVIDER_IDS:
        return DictationProvider(REMOTE, provider_id, provider_id)

    backend = _text(getattr(config, "asr_backend", ""))
    if backend == "cloud":
        cloud = _text(getattr(config, "cloud_provider", ""))
        return DictationProvider(CLOUD, cloud or backend, cloud)

    model = _text(getattr(config, "model_size", ""))
    from voice_typer.server.model_registry import NO_MODEL_SIZE

    if model and model != NO_MODEL_SIZE:
        return DictationProvider(LOCAL, model, model)
    return DictationProvider(NONE)


def for_app(app: Any | None = None, config: Any | None = None) -> DictationProvider:
    """Resolve the provider with the running app's plugin probe when present.

    The probe fails closed to "no plugin", so a broken plugin workspace can
    never make the local model silently take over a selected plugin's hotkey.
    """
    cfg = config if config is not None else getattr(app, "config", None)
    name = ""
    if app is not None:
        try:
            from voice_typer.server import internal_plugin_hook

            name = _text(internal_plugin_hook.plugin_display_name(app))
        except Exception:
            log.debug("[PROVIDER] app plugin ownership probe failed", exc_info=True)
    return for_config(cfg, plugin_name=name)


__all__ = [
    "CLOUD",
    "LOCAL",
    "NONE",
    "PLUGIN",
    "REMOTE",
    "DictationProvider",
    "for_app",
    "for_config",
]
