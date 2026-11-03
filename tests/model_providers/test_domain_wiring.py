"""Domain wiring: TTS and ASR route through the provider layer at call time."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from voice_typer.server.model_providers.contracts.tts import TtsRequest
from voice_typer.server.model_providers.errors import ProviderCapabilityError
from voice_typer.server.model_providers.hosted_tts import HostedTtsClient
from voice_typer.server.tts.manager import TtsManager


def _config(**overrides: object) -> SimpleNamespace:
    base = {
        "asr_provider": "",
        "asr_backend": "whisper",
        "tts_provider": "",
        "tts_engine": "audio8",
        "llm_provider": "",
        "tts_voice_id": "",
        "tts_language": "en",
        "model_size": "large-v3-turbo",
        "cloud_model": "",
        "cloud_provider": "",
        "llm_model": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_local_tts_config_keeps_the_local_engine_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty ``tts_provider`` never builds a remote client."""
    local = SimpleNamespace(provider=SimpleNamespace(id="local"))
    monkeypatch.setattr("voice_typer.server.model_providers.resolve_tts", lambda cfg: local)
    manager = TtsManager(config=_config())
    assert manager._resolved_remote_tts() is None


def test_remote_tts_provider_is_used_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured remote provider speaks instead of the local engine."""
    calls: list[str] = []

    class _Client:
        def synthesize(self, request: TtsRequest, *, abort_event: object = None) -> object:
            calls.append(request.text)
            return SimpleNamespace(data=_minimal_wav(), content_type="audio/wav")

    resolved = SimpleNamespace(
        provider=SimpleNamespace(id="custom"),
        model_id="tts-1",
        client=lambda: _Client(),
    )
    monkeypatch.setattr("voice_typer.server.model_providers.resolve_tts", lambda cfg: resolved)
    manager = TtsManager(config=_config(tts_provider="custom"))
    result = manager.speak("hello", play=False)
    assert calls == ["hello"]
    assert result["engine"] == "custom"


def test_unadvertised_voice_is_rejected_before_any_request() -> None:
    """A voice the provider does not advertise never reaches the network."""

    class _Opener:
        def open(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("no HTTP request may be sent for an unadvertised voice")

    client = HostedTtsClient(
        provider_id="custom",
        model_id="tts-1",
        base_url="https://example.com/v1",
        api_key="test-key",
        voices=("alloy",),
        opener=_Opener(),
    )
    with pytest.raises(ProviderCapabilityError):
        client.synthesize(TtsRequest(text="hello", voice="not-a-voice"))


def test_transcribe_step_uses_the_selected_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """``asr_provider=openrouter`` transcribes through the provider client."""
    from voice_typer.server.dictation_pipeline.transcribe_step import _TranscribeStepMixin

    class _Client:
        model_id = "audio-model"

        def transcribe(self, audio: object, *, abort_event: object = None) -> str:
            return "provider text"

    resolved = SimpleNamespace(
        provider=SimpleNamespace(id="openrouter"),
        model_id="audio-model",
        client=lambda: _Client(),
    )
    monkeypatch.setattr("voice_typer.server.model_providers.resolve_asr", lambda cfg: resolved)
    stub = SimpleNamespace(
        _app=SimpleNamespace(config=_config(asr_provider="openrouter")),
        _audio="audio",
    )
    assert _TranscribeStepMixin._transcribe_with_provider(stub) == "provider text"


def test_transcribe_step_keeps_the_legacy_path_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default resolution (local) returns ``None`` so the old path runs."""

    class _Client:
        def transcribe(self, audio: object, *, abort_event: object = None) -> str:
            raise AssertionError("the local path must not build a provider client")

    resolved = SimpleNamespace(
        provider=SimpleNamespace(id="local"),
        model_id="large-v3-turbo",
        client=lambda: _Client(),
    )
    monkeypatch.setattr("voice_typer.server.model_providers.resolve_asr", lambda cfg: resolved)
    from voice_typer.server.dictation_pipeline.transcribe_step import _TranscribeStepMixin

    stub = SimpleNamespace(_app=SimpleNamespace(config=_config()), _audio="audio")
    assert _TranscribeStepMixin._transcribe_with_provider(stub) is None


def _minimal_wav() -> bytes:
    """A 0.1 s silent 16 kHz mono WAV (no external deps)."""
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 1600)
    return buffer.getvalue()
