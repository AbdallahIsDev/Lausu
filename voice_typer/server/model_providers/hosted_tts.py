"""Hosted TTS over the OpenAI-compatible ``/v1/audio/speech`` route.

The two local engines already speak this route, so a remote provider is the same
request shape with a remote base URL + key. A voice id the provider does not
advertise is rejected before any request is sent (WP7).
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from voice_typer.server._secrets import assert_url_allowed
from voice_typer.server.asr_errors import CloudEngineError, CloudNetworkError
from voice_typer.server.model_providers._http import bearer, map_http_error, read_capped, secure_opener
from voice_typer.server.model_providers.contracts.tts import TtsAudio, TtsRequest
from voice_typer.server.model_providers.errors import ProviderCapabilityError

log = logging.getLogger(__name__)

OPENAI_TTS_BASE = "https://api.openai.com/v1"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_TTS_VOICES: tuple[str, ...] = (
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
)
OPENAI_TTS_LANGUAGES: tuple[str, ...] = (
    "en",
    "ar",
    "de",
    "es",
    "fr",
    "hi",
    "it",
    "ja",
    "ko",
    "pt",
    "ru",
    "zh",
)

#: ``custom`` points at any OpenAI-compatible server the user runs.
CUSTOM_TTS_VOICES: tuple[str, ...] = ()


class HostedTtsClient:
    """Synthesize through a remote ``/v1/audio/speech`` endpoint."""

    def __init__(
        self,
        *,
        provider_id: str,
        model_id: str,
        base_url: str,
        api_key: str = "",
        voices: tuple[str, ...] | None = None,
        languages: tuple[str, ...] | None = None,
        opener: Any = None,
    ) -> None:
        self.provider_id = provider_id
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._voices = OPENAI_TTS_VOICES if voices is None else voices
        self._languages = OPENAI_TTS_LANGUAGES if languages is None else languages
        self._opener = opener

    def voices(self) -> tuple[str, ...]:
        return self._voices

    def languages(self) -> tuple[str, ...]:
        return self._languages

    def synthesize(self, request: TtsRequest, *, abort_event: Any = None) -> TtsAudio:
        voice = request.voice or (self._voices[0] if self._voices else "")
        if self._voices and voice not in self._voices:
            raise ProviderCapabilityError(
                f"{self.provider_id} does not advertise voice {voice!r}",
                provider=self.provider_id,
                domain="tts",
            )
        payload: dict[str, Any] = {
            "model": self.model_id,
            "input": request.text,
            "voice": voice,
            "response_format": "wav",
        }
        if request.language:
            payload["language"] = request.language
        headers = {"Content-Type": "application/json", **bearer(self._api_key)}
        url = f"{self.base_url}/audio/speech"
        assert_url_allowed(url, field_name="tts_api_url", client_name=self.provider_id, allow_loopback_http=True)
        req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        active = self._opener or secure_opener()
        try:
            with active.open(req, timeout=120.0) as resp:
                data = read_capped(resp)
                content_type = resp.headers.get("Content-Type", "audio/wav")
        except HTTPError as exc:
            raise map_http_error(exc, self.provider_id) from exc
        except URLError as exc:
            raise CloudNetworkError(f"{self.provider_id} is unreachable") from exc
        if not data:
            raise CloudEngineError(f"{self.provider_id} returned empty audio")
        return TtsAudio(data=data, content_type=content_type)


__all__ = [
    "CUSTOM_TTS_VOICES",
    "OPENAI_TTS_BASE",
    "OPENAI_TTS_LANGUAGES",
    "OPENAI_TTS_MODEL",
    "OPENAI_TTS_VOICES",
    "HostedTtsClient",
]
