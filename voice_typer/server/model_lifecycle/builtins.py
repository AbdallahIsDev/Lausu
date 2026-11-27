"""Built-in policies: core ASR and optional TTS.

Both are thin adapters over the existing owners. No lifecycle logic is
reimplemented here: the ASR owner stays ``model_manager`` and the TTS owner
stays ``tts.prewarm`` / ``TtsManager``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .policy import ModelPolicy
from .registry import current_app, register

log = logging.getLogger(__name__)

_TTS_PRIVATE_BYTES = 5_900_000_000  # measured Audio8 after first synthesis (worst case)


def _service(app: Any) -> Any:
    return getattr(getattr(app, "_ipc_server", None), "service", None)


class _AsrPolicy(ModelPolicy):
    """Core ASR: every verb delegates to the existing ModelManager."""

    def applicable(self, config: Any) -> bool:
        # Only the selected local model needs local weights. A plugin, the
        # cloud engine or a remote ASR provider owns the hotkey instead.
        from voice_typer.server.dictation_provider import for_app, for_config

        app = current_app()
        provider = for_app(app, config) if app is not None else for_config(config)
        return provider.serves_local_asr

    def is_loaded(self, config: Any) -> bool:
        engine = getattr(current_app(), "models", None)
        engine = getattr(engine, "active_transcriber", lambda: None)()
        return bool(engine is not None and getattr(engine, "is_loaded", False))

    def is_busy(self) -> bool:
        app = current_app()
        try:
            backend = getattr(app.config, "asr_backend", "")
            return bool(app.models._registry.is_busy(backend))
        except Exception:
            return False

    def load(self, config: Any) -> bool:
        models = getattr(current_app(), "models", None)
        if models is None:
            return False
        models.ensure_active_engine_loaded()
        return self.is_loaded(config)

    def unload(self) -> None:
        # ASR idle unload and teardown stay owned by model_manager. Touching
        # it here would add a second unload path for the same shared engine.
        return None

    def wait(self, timeout_s: float) -> bool:
        models = getattr(current_app(), "models", None)
        if models is None:
            return False
        return models.wait_for_active_engine_loaded(timeout_s) is not None

    def note_use(self) -> None:
        models = getattr(current_app(), "models", None)
        if models is not None:
            models.touch_active_model()


class _TtsPolicy(ModelPolicy):
    """Optional TTS: load delegates to the existing post-ready prewarm."""

    def applicable(self, config: Any) -> bool:
        if not bool(getattr(config, "tts_enabled", False)):
            return False
        return str(getattr(config, "tts_engine", "off") or "off") in ("audio8", "magpie")

    def is_loaded(self, config: Any) -> bool:
        manager = getattr(_service(current_app()), "_tts_manager", None)
        tts_service = getattr(manager, "_service", None)
        servers = getattr(tts_service, "_servers", {}) or {}
        return any(bool(getattr(server, "running", False)) for server in servers.values())

    def load(self, config: Any) -> bool:
        from voice_typer.server.tts.prewarm import start_prewarm

        # start_prewarm owns its daemon thread and log lines; nothing here
        # downloads a pack or starts a second runtime.
        return start_prewarm(current_app()) is not None

    def unload(self) -> None:
        stop = getattr(_service(current_app()), "stop_tts", None)
        if callable(stop):
            stop()

    def wait(self, timeout_s: float) -> bool:
        cfg = getattr(current_app(), "config", None)
        deadline = time.monotonic() + timeout_s
        while True:
            if self.is_loaded(cfg):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)


def register_builtins() -> None:
    register(
        "asr",
        _AsrPolicy(name="asr", residency="core", estimate_private_bytes=0),
    )
    register(
        "tts",
        _TtsPolicy(
            name="tts",
            residency="optional",
            estimate_private_bytes=_TTS_PRIVATE_BYTES,
            dedicated_startup=True,
        ),
    )


__all__ = ["register_builtins"]
