"""Local text-translation stage (ADR-0030).

One text model, separate from the one ASR model. The shipped build is
Index-Translate-2B Q4_K_M served by a bundled llama.cpp runtime.
"""

from __future__ import annotations

from voice_typer.server.translation.service import (
    TranslationCancelledError,
    TranslationError,
    prewarm,
    resolve_model_path,
    resolve_runtime_path,
    shutdown,
    translate_text,
)

__all__ = [
    "TranslationCancelledError",
    "TranslationError",
    "prewarm",
    "resolve_model_path",
    "resolve_runtime_path",
    "shutdown",
    "translate_text",
]
