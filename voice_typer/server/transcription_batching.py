"""Decode policy constants and the sequential decode body.

Speech recognition runs through the worker's GGUF runner; the model-adapter
``transcribe(...)`` call is the single decode entry point. Long media jobs get
their window size from :data:`_BATCHED_SUPER_CHUNK_S`, but every window is one
self-contained decode call — there is no second batched decode path.
"""

from __future__ import annotations

import logging
from typing import Any, Final

# Same logger name as ``transcription_result`` so the decode log lines keep
# their established provenance.
log = logging.getLogger("voice_typer.server.transcription")

_VAD_PARAMETERS: Final[dict[str, int]] = {
    "min_silence_duration_ms": 500,
    "speech_pad_ms": 200,
}

# Media windows and the minimum duration above which a job uses them.
_BATCHED_MIN_DURATION_S: Final[float] = 30.0
_BATCHED_SUPER_CHUNK_S: Final[float] = 120.0

# Full anti-repetition ladder: a bare ``0.0`` collapses the decoder to a
# single candidate, so a degenerate repeat-loop is accepted verbatim.
_DECODE_TEMPERATURES: Final[tuple[float, ...]] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def _decode_segments(engine: Any, audio: Any, use_vad_filter: bool, duration: float) -> tuple[Any, Any]:
    """Decode to ``(segments, info)`` through the model adapter."""
    kwargs = {
        "beam_size": engine.beam_size,
        "temperature": _DECODE_TEMPERATURES,
        "vad_filter": use_vad_filter,
        "vad_parameters": _VAD_PARAMETERS,
        "language": engine.language,
        "condition_on_previous_text": engine.condition_on_previous_text,
        "without_timestamps": True,
    }
    log.info(
        "[TRANSCRIBE] decode path=sequential device=%s beam=%s vad=%s condition_prev=%s (%.1fs audio)",
        getattr(engine, "_device", "unknown"),
        engine.beam_size,
        use_vad_filter,
        engine.condition_on_previous_text,
        duration,
    )
    return engine._model.transcribe(audio, **kwargs)
