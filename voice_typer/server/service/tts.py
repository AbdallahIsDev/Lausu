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
        status: dict[str, object] = self._get_tts_manager().status()
        return status

    def tts_prepare(self, engine: str) -> dict[str, object]:
        """Download one engine's pack into the Hugging Face folder."""
        log.info("[TTS] preparing pack for %s", engine)
        result: dict[str, object] = self._get_tts_manager().prepare(engine)
        return result

    def tts_speak(
        self,
        text: str,
        engine: str | None = None,
        *,
        voice: str | None = None,
        sample: bool = False,
    ) -> dict[str, object]:
        """Render one utterance, or play a voice sample from the cache.

        ``sample=True`` ignores ``text`` and reuses the shipped/cached clip, so
        pressing Test never re-synthesizes the same sentence.
        """
        manager = self._get_tts_manager()
        result: dict[str, object] = manager.speak_sample(engine, voice) if sample else manager.speak(text, engine)
        return result

    def tts_stop(self) -> dict[str, object]:
        """Stop the clip that is playing (the control's stop state)."""
        stopped = bool(self._get_tts_manager().stop_playback())
        log.info("[TTS] playback stop requested stopped=%s", stopped)
        return {"stopped": stopped}

    def tts_prewarm(self, engine: str) -> bool:
        """Start ``engine``'s runtime in the background (post-ready startup)."""
        started: bool = self._get_tts_manager().prewarm(engine)
        return started

    def stop_tts(self) -> None:
        """Stop playback + every TTS runtime (shutdown path)."""
        manager = getattr(self, "_tts_manager", None)
        if manager is not None:
            manager.shutdown()
            self._tts_manager = None
