"""Backward-compatible import path for the single model registry.

The registry itself lives in :mod:`voice_typer.server.gguf_model_registry`.
This module only re-exports names so existing callers keep resolving; it owns
no catalogue data and must never grow a second list of models.
"""

from __future__ import annotations

from voice_typer.server.gguf_model_registry import (
    DEFAULT_MODEL_SIZE,
    LEGACY_MODEL_ALIASES,
    LEGACY_REPO_ID_KEYS,
    MODEL_REGISTRY,
    NO_MODEL_SIZE,
    ModelMetadata,
    get_all_models,
    get_model_metadata,
)

__all__ = [
    "ModelMetadata",
    "MODEL_REGISTRY",
    "DEFAULT_MODEL_SIZE",
    "LEGACY_MODEL_ALIASES",
    "LEGACY_REPO_ID_KEYS",
    "NO_MODEL_SIZE",
    "get_model_metadata",
    "get_all_models",
]
