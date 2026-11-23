"""GGUF registry tests: real names, loud placeholders, no invented hashes."""

from __future__ import annotations

import pytest

from voice_typer.server.gguf_model_registry import (
    GGUF_MODELS,
    PLACEHOLDER_SHA256,
    GgufModelSpec,
    all_placeholders,
    is_placeholder_hash,
    is_placeholder_size,
    require_complete_spec,
    resolve_gguf_spec,
)


def test_catalogue_covers_all_registered_asr_models() -> None:
    assert set(GGUF_MODELS) == {
        "tiny",
        "large-v3",
        "large-v3-turbo",
        "parakeet",
        "qwen3-0.6b",
        "qwen3-1.7b",
    }


def test_repos_and_files_follow_verified_upstream_names() -> None:
    assert resolve_gguf_spec("parakeet").repo_id == "handy-computer/parakeet-ultra-gguf"
    assert resolve_gguf_spec("parakeet").filename == "parakeet-ultra-Q8_0.gguf"
    assert resolve_gguf_spec("parakeet").size_bytes == 740_363_168
    assert resolve_gguf_spec("large-v3-turbo").repo_id == "handy-computer/whisper-large-v3-turbo-gguf"
    assert resolve_gguf_spec("qwen3-1.7b").filename == "Qwen3-ASR-1.7B-Q8_0.gguf"


def test_no_invented_hashes() -> None:
    # The cloud agent cannot download models. Every hash MUST still be a
    # placeholder; a real-looking digest here would be fabricated.
    assert all(spec.sha256 == PLACEHOLDER_SHA256 for spec in GGUF_MODELS.values())
    assert all_placeholders()


def test_placeholder_guard_is_loud() -> None:
    spec = resolve_gguf_spec("parakeet")
    with pytest.raises(RuntimeError, match="placeholder SHA-256"):
        require_complete_spec(spec)
    real = GgufModelSpec(
        model_key="x",
        repo_id="org/repo",
        filename="x.gguf",
        sha256="a" * 64,
        size_bytes=123,
        license="MIT",
    )
    require_complete_spec(real)


def test_placeholder_classifiers() -> None:
    assert is_placeholder_hash(PLACEHOLDER_SHA256)
    assert is_placeholder_hash("deadbeef")
    assert not is_placeholder_hash("A" * 64)
    assert is_placeholder_size(None)
    assert not is_placeholder_size(740_363_168)
