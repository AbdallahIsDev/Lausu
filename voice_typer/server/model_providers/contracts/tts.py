"""TTS domain contract: text + voice + language in, audio bytes out."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class TtsRequest:
    """One synthesis request (voice/language already validated by the client)."""

    text: str
    voice: str | None = None
    language: str | None = None


@dataclass(frozen=True)
class TtsAudio:
    """Raw audio returned by a TTS client."""

    data: bytes
    content_type: str = "audio/wav"
    sample_rate: int | None = None


@runtime_checkable
class TtsClient(Protocol):
    """A speech-synthesis client for exactly one provider + model."""

    provider_id: str
    model_id: str

    def voices(self) -> tuple[str, ...]:
        """Voice ids this provider/model advertises (never guess one)."""
        ...

    def languages(self) -> tuple[str, ...]:
        """Language tags the provider advertises for ``model_id``."""
        ...

    def synthesize(self, request: TtsRequest, *, abort_event: Any = None) -> TtsAudio:
        """Render ``request.text`` to audio bytes."""
        ...


__all__ = ["TtsAudio", "TtsClient", "TtsRequest"]
