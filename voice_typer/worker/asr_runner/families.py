"""Map the three ASR families onto one GGUF runner and one model at a time.

ADR-0030 is preserved: exactly one ASR model is resident. The selected backend
only decides which GGUF file the single runner loads; no second engine is
started, and no "language pack" is added (C-ASR-5).
"""

from __future__ import annotations

from typing import Any

from voice_typer.server.gguf_download import resolve_gguf_model_path
from voice_typer.server.model_language_support import PARAKEET_LANGUAGES, QWEN3_LANGUAGES


class LanguageNotSupportedError(ValueError):
    """Raised before recording when a pinned language is outside the model."""


def model_key_for(config: Any) -> str:
    """Return the registry key of the single model to load."""
    backend = getattr(config, "asr_backend", "whisper") or "whisper"
    if backend == "parakeet":
        return "parakeet"
    if backend == "qwen":
        return "qwen3-1.7b"
    return getattr(config, "model_size", "") or "tiny"


def assert_model_language(model_key: str, language: str | None) -> None:
    """Refuse a pinned language the model cannot decode (C-ASR-6)."""
    if not language or language == "auto":
        return
    supported: set[str] | None = None
    if model_key == "parakeet":
        supported = set(PARAKEET_LANGUAGES)
    elif model_key.startswith("qwen3"):
        supported = set(QWEN3_LANGUAGES)
    if supported is not None and language not in supported:
        raise LanguageNotSupportedError(f"{model_key} does not support {language}.")


def gguf_model_path_for_key(model_key: str, language: str | None = None) -> str:
    """Resolve one local GGUF file. Never downloads at inference time."""
    assert_model_language(model_key, language)
    path = resolve_gguf_model_path(model_key)
    if path is None:
        raise RuntimeError("No speech model is selected or downloaded. Open Models to choose one.")
    return str(path)


def gguf_model_path_for(config: Any) -> str:
    """Resolve the local GGUF file selected by config."""
    model_key = model_key_for(config)
    return gguf_model_path_for_key(model_key, getattr(config, "language", None))
