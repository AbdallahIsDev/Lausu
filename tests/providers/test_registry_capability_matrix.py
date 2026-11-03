"""The registry's capability matrix is explicit, not inferred."""

from __future__ import annotations

import pytest
from voice_typer.server.model_providers import Domain, get_registry
from voice_typer.server.model_providers.errors import (
    ProviderCapabilityError,
    ProviderModelNotFoundError,
)


def test_every_provider_advertises_only_domains_it_can_serve() -> None:
    matrix = get_registry().capability_matrix()
    assert matrix["local"] == ["asr", "tts"]
    assert matrix["cloud_direct"] == ["asr", "llm"]
    assert matrix["openrouter"] == ["asr", "llm", "tts"]
    assert matrix["ollama"] == ["llm"]
    assert matrix["lmstudio"] == ["llm"]
    assert matrix["local_onnx"] == ["llm"]
    assert matrix["openai"] == ["tts"]
    assert matrix["custom"] == ["tts"]


def test_domain_listing_is_filtered_by_capability() -> None:
    registry = get_registry()
    llm_ids = {p.id for p in registry.for_domain(Domain.LLM)}
    assert llm_ids == {"cloud_direct", "openrouter", "ollama", "lmstudio", "local_onnx"}
    assert "local" not in llm_ids


def test_a_provider_cannot_almost_satisfy_a_domain() -> None:
    ollama = get_registry().get("ollama")
    with pytest.raises(ProviderCapabilityError):
        ollama.client(Domain.ASR, "llama3")


def test_unsupported_domains_carry_a_reason() -> None:
    ollama = get_registry().get("ollama")
    assert ollama.unsupported_reason[Domain.ASR]
    assert ollama.unsupported_reason[Domain.TTS]


def test_unknown_model_is_rejected() -> None:
    registry = get_registry()
    with pytest.raises(ProviderModelNotFoundError):
        registry.get("lmstudio").client(Domain.LLM, "not-a-real-model")


def test_unknown_provider_is_a_typed_error() -> None:
    from voice_typer.server.model_providers.errors import ProviderNotFoundError

    with pytest.raises(ProviderNotFoundError):
        get_registry().get("nope")
