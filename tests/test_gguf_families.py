"""Family mapping tests: one resident model, language gate, no downloads."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from voice_typer.server.gguf_model_registry import LEGACY_REPO_ID_KEYS as _LEGACY_IDS
from voice_typer.worker._transcribe import WorkerTranscriber
from voice_typer.worker.asr_runner.families import (
    LanguageNotSupportedError,
    assert_model_language,
    gguf_model_path_for_key,
    model_key_for,
)


def _legacy_id(key: str) -> str:
    """Old repo ids live in the one migration map; never duplicate them here."""
    return next(repo for repo, mapped in _LEGACY_IDS.items() if mapped == key)


@pytest.mark.parametrize(
    ("backend", "model_size", "expected"),
    [
        ("whisper", "large-v3-turbo", "large-v3-turbo"),
        ("parakeet", "tiny", "parakeet"),
        ("qwen", "", "qwen3-1.7b"),
        ("cloud", "tiny", "large-v3-turbo"),
        ("whisper", "tiny", "large-v3-turbo"),
        ("whisper", _legacy_id("tiny"), "large-v3-turbo"),
    ],
)
def test_model_key_for(backend: str, model_size: str, expected: str) -> None:
    assert model_key_for(SimpleNamespace(asr_backend=backend, model_size=model_size)) == expected


def test_language_gate_blocks_arabic_on_parakeet() -> None:
    with pytest.raises(LanguageNotSupportedError, match="parakeet does not support ar"):
        assert_model_language("parakeet", "ar")
    assert_model_language("qwen3-1.7b", "ar")


def test_auto_language_is_never_blocked() -> None:
    assert_model_language("parakeet", "")
    assert_model_language("parakeet", None)


def test_local_path_resolution_never_downloads(monkeypatch: pytest.MonkeyPatch) -> None:
    import voice_typer.worker.asr_runner.families as families

    calls: list[str] = []
    monkeypatch.setattr(
        families,
        "resolve_gguf_model_path",
        lambda key: calls.append(key) or __import__("pathlib").Path(f"{key}.gguf"),
    )
    with pytest.raises(LanguageNotSupportedError):
        gguf_model_path_for_key("parakeet", "ar")
    assert calls == []
    path = gguf_model_path_for_key("parakeet", "en")
    assert path.endswith("parakeet.gguf")
    assert calls == ["parakeet"]


def test_worker_registry_points_all_families_at_one_gguf_engine() -> None:
    transcriber = WorkerTranscriber()
    config = SimpleNamespace(asr_backend="whisper", model_size="tiny", language=None)
    registry = transcriber._build_registry(config)
    assert registry is not None
