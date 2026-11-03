"""OpenRouter catalogue honesty: modalities decide domains, audio-in is chat."""

from __future__ import annotations

import threading

import numpy as np
from voice_typer.server.model_providers.descriptor import Domain
from voice_typer.server.model_providers.openrouter import (
    OpenRouterAsrClient,
    OpenRouterTtsClient,
    _OpenRouterAuth,
    parse_models,
)


def _catalogue() -> dict:
    return {
        "data": [
            {
                "id": "google/gemini-2.0-flash",
                "name": "Gemini 2.0 Flash",
                "context_length": 1_000_000,
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {
                    "input_modalities": ["audio", "text"],
                    "output_modalities": ["text"],
                },
            },
            {
                "id": "whisper-large-v3",
                "name": "Whisper Large v3",
                "context_length": 0,
                "pricing": {"prompt": "0.0001", "completion": "0.0001"},
                "architecture": {
                    "input_modalities": ["audio"],
                    "output_modalities": ["text"],
                },
            },
            {
                "id": "lyria-002",
                "name": "Lyria",
                "context_length": 0,
                "pricing": {"prompt": "0.0002", "completion": "0.0002"},
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["audio"],
                },
            },
        ]
    }


def test_domains_come_from_modalities_not_names() -> None:
    models = {model.id: model for model in parse_models(_catalogue())}

    assert models["google/gemini-2.0-flash"].domains == frozenset({Domain.ASR, Domain.LLM})
    assert models["whisper-large-v3"].domains == frozenset({Domain.ASR})
    assert models["lyria-002"].domains == frozenset({Domain.TTS})


def test_audio_input_models_are_labelled_chat_not_dedicated_asr() -> None:
    models = {model.id: model for model in parse_models(_catalogue())}
    gemini = models["google/gemini-2.0-flash"]

    assert gemini.metadata == {"audio_mode": "chat"}
    assert "chat model with audio input" in (gemini.note or "")
    assert gemini.to_dict()["metadata"] == {"audio_mode": "chat"}


def test_abort_before_the_request_makes_no_network_call(monkeypatch) -> None:
    from voice_typer.server.model_providers import openrouter

    calls: list[object] = []
    monkeypatch.setattr(openrouter, "request_json", lambda *a, **k: calls.append((a, k)))
    client = OpenRouterAsrClient(_OpenRouterAuth(api_key="k"), "google/gemini-2.0-flash")
    abort = threading.Event()
    abort.set()

    assert client.transcribe(np.zeros(16000, dtype=np.float32), abort_event=abort) == ""
    assert calls == []


def test_asr_prompt_carries_language_and_duration_hints(monkeypatch) -> None:
    from voice_typer.server.model_providers import openrouter

    captured: dict = {}

    def fake_request(url, **kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "hello"}}]}

    monkeypatch.setattr(openrouter, "request_json", fake_request)
    monkeypatch.setattr(
        "voice_typer.server.cloud._transport._audio_to_wav_bytes",
        lambda audio: b"wav",
    )
    client = OpenRouterAsrClient(_OpenRouterAuth(api_key="k"), "google/gemini-2.0-flash", language="de")

    assert client.transcribe(np.zeros(8000, dtype=np.float32)) == "hello"
    text = captured["body"]["messages"][0]["content"][0]["text"]
    assert "Language: de." in text
    assert "Audio duration: 0.5 seconds." in text


def test_tts_languages_follow_config_not_a_hardcoded_en() -> None:
    client = OpenRouterTtsClient(_OpenRouterAuth(api_key="k"), "gpt-audio", language="ar")

    assert client.languages() == ("ar",)
