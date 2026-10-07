"""ASR backend names and the ``model_size`` -> owning-backend mapping."""

from __future__ import annotations

from typing import Literal

# Mirrors ``Config.asr_backend`` (config/_schema.py), the three valid
AsrBackendName = Literal["whisper", "qwen", "parakeet"]


def _backend_for_model_size(model_size: str) -> AsrBackendName:
    """Map a user-selected ``model_size`` to its owning ASR backend."""
    if model_size == "parakeet":
        return "parakeet"
    if model_size == "qwen":
        return "qwen"
    return "whisper"
