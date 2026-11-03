"""Adapter: the local Audio8 / Magpie engines behind the TTS contract."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from voice_typer.server.model_providers.contracts.tts import TtsAudio, TtsRequest
from voice_typer.server.model_providers.errors import ProviderRuntimeError
from voice_typer.server.tts.manager import TtsManager
from voice_typer.server.tts.voices import languages_for, voice_ids

log = logging.getLogger(__name__)


class LocalTtsClient:
    """One local engine (``audio8`` or ``magpie``) as a TTS domain client."""

    provider_id = "local"

    def __init__(self, *, config: Any, engine: str = "") -> None:
        self._config = config
        self.model_id = engine or str(getattr(config, "tts_engine", "off") or "")
        self._manager = TtsManager(config=config)

    def voices(self) -> tuple[str, ...]:
        return voice_ids(self.model_id)

    def languages(self) -> tuple[str, ...]:
        return languages_for(self.model_id)

    def synthesize(self, request: TtsRequest, *, abort_event: Any = None) -> TtsAudio:
        if self.model_id not in ("audio8", "magpie"):
            raise ProviderRuntimeError(
                "local TTS needs an engine (audio8 or magpie)",
                provider="local",
                domain="tts",
            )
        result = self._manager.speak(request.text, self.model_id, play=False)
        wav_path = Path(str(result.get("wav_path") or ""))
        if not wav_path.is_file():
            raise ProviderRuntimeError("local TTS produced no audio file", provider="local", domain="tts")
        return TtsAudio(data=wav_path.read_bytes(), content_type="audio/wav")


__all__ = ["LocalTtsClient"]
