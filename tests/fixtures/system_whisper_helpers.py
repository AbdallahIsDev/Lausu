"""Fake states for ``SystemWhisperEngine`` tests (never a real model).

The engine talks to faster-whisper directly, so tests build an
already-"loaded" instance via ``__new__`` and hand it fake decode output.
Both the CPU-fallback tests and the decode-parity tests need exactly the
same instance shape (decode protocol attributes + abort token + lock).
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock


def make_system_engine(device: str = "cuda"):
    """Return a loaded-looking engine with a mock faster-whisper model."""
    from voice_typer.server.system_whisper import SystemWhisperEngine

    engine = SystemWhisperEngine.__new__(SystemWhisperEngine)
    engine._model_size = "tiny"
    engine._weights_dir = "/tmp/fake-weights"
    engine._device = device
    engine._effective_device = device
    engine._language = "en"
    engine._beam_size = 5
    engine._model = MagicMock(name="fw-model")
    engine._loaded = True
    engine._cpu_fallback_notified = False
    engine.config = SimpleNamespace(
        condition_on_previous_text=False,
        vad_filter_enabled=False,
        hallucination_filter_mode=None,
        log_transcriptions=False,
    )
    engine.condition_on_previous_text = False
    engine.last_quality_summary = None
    engine.last_rejection_reason = None
    engine._abort_event = threading.Event()
    engine._inference_lock = threading.RLock()
    return engine


def decoded(text: str, *, words: list | None = None):
    """Fake faster-whisper ``(segments, info)`` pair for one decoded line."""
    segment = SimpleNamespace(
        text=text,
        start=0.0,
        end=0.5,
        avg_logprob=-0.2,
        no_speech_prob=0.01,
        words=list(words or []),
    )
    return ([segment], SimpleNamespace(language="en", language_probability=0.99))


def word(text: str, start: float, end: float):
    """Fake faster-whisper word-timestamp entry."""
    return SimpleNamespace(word=text, start=start, end=end)
