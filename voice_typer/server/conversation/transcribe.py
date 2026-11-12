"""Shared transcription entry point for the mic test and the chat loop."""

from __future__ import annotations

from typing import Any


def transcribe_with_engine(engine: Any, audio_f32: Any) -> str:
    """Transcribe through the backend contract, not a concrete method name.

    ``transcribe_with_fallback`` is what every ``AsrBackend`` implements
    (worker proxies expose no ``transcribe`` at all, and it is the method
    the dictation pipeline itself calls).
    """
    transcribe = getattr(engine, "transcribe_with_fallback", None)
    if not callable(transcribe):
        transcribe = getattr(engine, "transcribe", None)
    if not callable(transcribe):
        raise AttributeError(f"{type(engine).__name__} exposes no transcription method")
    return str(transcribe(audio_f32) or "")


__all__ = ["transcribe_with_engine"]
