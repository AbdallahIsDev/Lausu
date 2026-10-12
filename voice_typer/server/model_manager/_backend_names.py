"""ASR backend names and the ``model_size`` -> owning-backend mapping."""

from __future__ import annotations

from typing import Literal

# Mirrors ``Config.asr_backend`` (config/_schema.py), the four valid
AsrBackendName = Literal["whisper", "qwen", "parakeet", "cloud"]

#: Every legal ``asr_backend`` value. The single runtime source of truth for
#: the backend allowlists: ``set_active_backend`` and
#: ``_set_active_backend_blocking`` used to re-spell the tuple independently,
#: so adding a backend meant finding all three sites (or silently rejecting it
#: on one path only).
ASR_BACKEND_NAMES: tuple[AsrBackendName, ...] = ("whisper", "qwen", "parakeet", "cloud")


def _backend_for_model_size(model_size: str) -> AsrBackendName:
    """Map a user-selected ``model_size`` to its owning ASR backend."""
    if model_size == "parakeet":
        return "parakeet"
    if model_size == "qwen":
        return "qwen"
    return "whisper"
