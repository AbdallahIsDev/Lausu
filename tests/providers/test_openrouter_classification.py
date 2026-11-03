"""OpenRouter classification comes from modalities, never from model names."""

from __future__ import annotations

from voice_typer.server.model_providers.descriptor import Domain
from voice_typer.server.model_providers.openrouter import (
    classify_architecture,
    classify_pricing,
    parse_models,
)


def test_text_in_text_out_is_llm_only() -> None:
    arch = {"input_modalities": ["text"], "output_modalities": ["text"]}
    assert classify_architecture(arch) == frozenset({Domain.LLM})


def test_audio_in_text_out_is_asr() -> None:
    arch = {"input_modalities": ["audio"], "output_modalities": ["text"]}
    assert classify_architecture(arch) == frozenset({Domain.ASR})


def test_audio_output_is_tts() -> None:
    arch = {"input_modalities": ["text"], "output_modalities": ["audio"]}
    assert classify_architecture(arch) == frozenset({Domain.TTS})


def test_a_misleading_name_does_not_create_a_domain() -> None:
    model = {
        "id": "acme/whisper-transcriber-tts",
        "name": "Whisper Transcriber TTS",
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "pricing": {"prompt": "0.000001", "completion": "0.000002"},
    }
    parsed = parse_models({"data": [model]})
    assert parsed[0].domains == frozenset({Domain.LLM})


def test_modality_string_fallback() -> None:
    arch = {"modality": "audio+text->text"}
    assert classify_architecture(arch) == frozenset({Domain.ASR, Domain.LLM})


def test_free_pricing_is_labelled_free() -> None:
    prompt, completion, free = classify_pricing({"prompt": "0", "completion": "0"})
    assert (prompt, completion, free) == (0.0, 0.0, True)
    assert classify_pricing({"prompt": "0.000001", "completion": "0.000002"})[2] is False
    assert classify_pricing(None) == (None, None, False)


def test_models_without_modalities_are_skipped() -> None:
    rows = [{"id": "no-arch"}]
    assert parse_models({"data": rows}) == []
