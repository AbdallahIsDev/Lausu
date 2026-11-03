"""Hosted TTS: request shape, unknown-voice refusal, zero network on refusal."""

from __future__ import annotations

from typing import Any

import pytest
from voice_typer.server.model_providers.contracts.tts import TtsRequest
from voice_typer.server.model_providers.errors import ProviderCapabilityError
from voice_typer.server.model_providers.hosted_tts import HostedTtsClient


class _FakeResponse:
    def __init__(self, body: bytes = b"RIFFdata") -> None:
        self._body = body
        self.headers = {"Content-Type": "audio/wav"}
        self.status = 200

    def read(self, _n: int = -1) -> bytes:
        body, self._body = self._body, b""
        return body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _FakeOpener:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    def open(self, req: Any, timeout: float | None = None) -> _FakeResponse:
        self.requests.append(req)
        return _FakeResponse()


def _client(opener: _FakeOpener) -> HostedTtsClient:
    return HostedTtsClient(
        provider_id="openai",
        model_id="gpt-4o-mini-tts",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        opener=opener,
    )


def test_request_shape_is_openai_compatible() -> None:
    opener = _FakeOpener()
    audio = _client(opener).synthesize(TtsRequest(text="hello", voice="nova", language="en"))
    assert audio.data == b"RIFFdata"
    assert len(opener.requests) == 1
    req = opener.requests[0]
    assert req.full_url.endswith("/audio/speech")
    assert req.get_header("Authorization") == "Bearer sk-test"


def test_unknown_voice_is_rejected_before_the_call() -> None:
    opener = _FakeOpener()
    with pytest.raises(ProviderCapabilityError):
        _client(opener).synthesize(TtsRequest(text="hello", voice="not-a-voice"))
    assert opener.requests == []


def test_advertised_voices_are_the_openai_set() -> None:
    voices = _client(_FakeOpener()).voices()
    assert "nova" in voices
    assert "alloy" in voices
