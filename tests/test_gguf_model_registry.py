"""Catalogue tests: real hashes/sizes, five production models, dev-only tiny."""

from __future__ import annotations

import re

import pytest
from voice_typer.server import gguf_model_registry as registry
from voice_typer.server.gguf_model_registry import (
    DEFAULT_MODEL_KEY,
    GGUF_MODELS,
    PRODUCTION_MODEL_KEYS,
    all_placeholders,
    available_models,
    is_placeholder_hash,
    is_placeholder_size,
    production_models,
    require_complete_spec,
    resolve_gguf_spec,
)

EXPECTED = {
    "parakeet": (
        "parakeet-ultra-Q8_0.gguf",
        740_363_168,
        "007a59761e9258779f189df396b50d12b83bb5b79e66df4b955c230d2f2a0a59",
    ),
    "large-v3-turbo": (
        "whisper-large-v3-turbo-Q8_0.gguf",
        886_381_728,
        "257aa7ec9121c22c167d5e2c49e3e76b4ba0e6e27ebc13074eba0a80f8190220",
    ),
    "qwen3-1.7b": (
        "Qwen3-ASR-1.7B-Q4_K_M.gguf",
        1_319_830_496,
        "b7afe3674f653fa84f712ed2440353c6e7cf7f93697fef76b05a26538b24844e",
    ),
    "qwen3-0.6b": (
        "Qwen3-ASR-0.6B-Q8_0.gguf",
        850_423_456,
        "f081b2d5e23bd669d92cc331d722a8a0681943b8e6f34b48996fd5c319b5acd8",
    ),
    "large-v3": (
        "whisper-large-v3-Q6_K.gguf",
        1_297_130_208,
        "88e6dc60bd0538da145a50c19f4778e4a106fe28713adeeca43163215ee02805",
    ),
}


def test_no_placeholders_or_invalid_values() -> None:
    assert all_placeholders() == ()
    for spec in GGUF_MODELS.values():
        assert re.fullmatch(r"[0-9a-f]{64}", spec.sha256), spec.model_key
        assert spec.size_bytes > 0, spec.model_key
        require_complete_spec(spec)


def test_production_catalogue_is_exactly_the_five_owner_models() -> None:
    assert set(production_models()) == PRODUCTION_MODEL_KEYS
    assert set(PRODUCTION_MODEL_KEYS) == set(EXPECTED)
    assert "tiny" not in production_models()
    assert DEFAULT_MODEL_KEY in PRODUCTION_MODEL_KEYS


def test_exact_files_sizes_and_hashes() -> None:
    for key, (filename, size, digest) in EXPECTED.items():
        spec = resolve_gguf_spec(key, allow_dev=False)
        assert (spec.filename, spec.size_bytes, spec.sha256) == (filename, size, digest)
        assert spec.repo_id.startswith("handy-computer/")


def test_tiny_is_dev_only_and_not_production() -> None:
    spec = resolve_gguf_spec("tiny", allow_dev=True)
    assert spec.dev_only
    assert spec.filename == "whisper-tiny-Q8_0.gguf"
    assert spec.size_bytes == 45_981_088
    with pytest.raises(KeyError):
        resolve_gguf_spec("tiny", allow_dev=False)


def test_available_models_respects_frozen_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "is_frozen", lambda: True)
    assert "tiny" not in available_models()
    monkeypatch.setattr(registry, "is_frozen", lambda: False)
    assert "tiny" in available_models()


def test_placeholder_classifiers_reject_garbage() -> None:
    assert is_placeholder_hash("FILL_ME")
    assert not is_placeholder_hash("a" * 64)
    assert is_placeholder_size(None) and is_placeholder_size(0)
    assert not is_placeholder_size(1)
