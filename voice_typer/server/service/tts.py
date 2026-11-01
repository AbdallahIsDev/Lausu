"""TTS service mixin: status, pack preparation, speak, compare.

This module exists so the IPC layer reaches TTS through the same service facade
as ASR and models, with one lazily-created manager per app instance.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.service._base import ServiceMixinBase

log = logging.getLogger(__name__)


class TtsMixin(ServiceMixinBase):
    """Mixin: local text-to-speech surface (Audio8 + MagpieTTS)."""

    _tts_manager: Any = None

    def _get_tts_manager(self) -> Any:
        """Return the per-app manager, creating it on first use."""
        manager = getattr(self, "_tts_manager", None)
        if manager is None:
            from voice_typer.server.tts.manager import TtsManager

            manager = TtsManager(config=self._app.config)
            self._tts_manager = manager
        return manager

    def get_tts_status(self) -> dict[str, object]:
        """Engines, selection, and pack availability for the Models page."""
        return self._get_tts_manager().status()

    def tts_prepare(self, engine: str) -> dict[str, object]:
        """Download one engine's pack into the Hugging Face folder."""
        log.info("[TTS] preparing pack for %s", engine)
        return self._get_tts_manager().prepare(engine)

    def tts_speak(self, text: str, engine: str | None = None) -> dict[str, object]:
        """Render and play one utterance with ``engine`` (default: configured)."""
        return self._get_tts_manager().speak(text, engine)

    def stop_tts(self) -> None:
        """Stop every TTS runtime (shutdown path)."""
        manager = getattr(self, "_tts_manager", None)
        if manager is not None:
            manager.shutdown()
            self._tts_manager = None
