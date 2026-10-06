"""Batched/parallel decode policy for long recordings.

Long CUDA audio is decoded through faster-whisper's ``BatchedInferencePipeline``
in silence-split super-chunks; everything else takes the original single
sequential call. ``transcription_result`` owns the segment loops and re-exports
these helpers.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Final

from voice_typer.server._audio_constants import (
    WHISPER_SAMPLE_RATE as _WHISPER_SAMPLE_RATE,
)
from voice_typer.server._lazy_import import lazy_module

np = lazy_module("numpy")

# Same logger name as ``transcription_result`` so the batched-decode log lines
# keep their established provenance.
log = logging.getLogger("voice_typer.server.transcription")


# Silero-VAD tuning passed to BOTH faster-whisper decode loops (batch
_VAD_PARAMETERS: Final[dict[str, int]] = {
    "min_silence_duration_ms": 500,
    "speech_pad_ms": 200,
}

# Batched-decode policy for long recordings. faster-whisper decodes its
# internal 30 s windows strictly sequentially (one window per generate
# call), so an 8-minute dictation pays full sequential latency. Decoding
# independent windows in parallel (batch_size=8) is mathematically
# identical work and ~3x faster on CUDA. Short audio stays sequential:
# a single window gains nothing from batching.
_BATCHED_MIN_DURATION_S: Final[float] = 30.0
# One batched call still decodes to completion before yielding, so the
# whole recording in one call would blind the ESC-abort poll for the
# full decode. Super-chunks bound abort latency to one piece (~4 s at
# batched speed, same as today's 30 s-window granularity).
_BATCHED_SUPER_CHUNK_S: Final[float] = 120.0
_BATCHED_BATCH_SIZE: Final[int] = 8


def _batched_pipeline_for(engine: Any) -> Any | None:
    """Return a ``BatchedInferencePipeline`` for ``engine._model``, or None.

    None means "stay sequential": non-CUDA device, previous-text
    conditioning (batched windows decode independently, so chaining
    context across them would change results), a mocked/non-faster-whisper
    model (unit tests), or a missing faster-whisper install. The import goes
    through ``importlib`` rather than an ``import`` statement: two consumers
    scan for static imports of ``faster_whisper``/``ctranslate2`` — Nuitka's
    module follower (which must never pull them into the frozen sidecar) and
    the slim-core ratchet (``scripts/slim_core_ml_ratchet_check.py``). Same
    pattern as ``system_whisper.py``.
    """
    if getattr(engine, "condition_on_previous_text", False):
        return None
    if getattr(engine, "_device", "cpu") != "cuda":
        return None
    model = getattr(engine, "_model", None)
    if model is None or type(model).__module__.split(".")[0] != "faster_whisper":
        return None
    try:
        pipeline_cls = importlib.import_module("faster_whisper").BatchedInferencePipeline
    except (ImportError, AttributeError):
        return None
    try:
        return pipeline_cls(model)
    except Exception:
        log.debug("[TRANSCRIBE] batched pipeline unavailable, staying sequential", exc_info=True)
        return None


def _split_on_silence(
    audio: Any,
    sample_rate: int,
    *,
    target_s: float = _BATCHED_SUPER_CHUNK_S,
    search_s: float = 10.0,
) -> list[tuple[float, Any]]:
    """Split audio into ~``target_s`` pieces cut at quiet moments.

    Returns ``[(offset_seconds, view)]`` views (no copies). Each target
    boundary is nudged within ±``search_s`` to the lowest-energy 0.5 s
    window, so a spoken word is never sliced in half.
    """
    n = int(len(audio))
    target = int(target_s * sample_rate)
    if n <= target:
        return [(0.0, audio)]
    win = max(1, int(0.5 * sample_rate))
    energy = np.square(np.asarray(audio, dtype=np.float32))
    cumsum = np.concatenate(([0.0], np.cumsum(energy)))
    starts = np.arange(0, n - win + 1, win)

    def _window_energy(center: int) -> float:
        lo = max(0, min(center - win // 2, n - win))
        return float(cumsum[lo + win] - cumsum[lo])

    bounds = [0]
    k = target
    while k < n:
        lo = max(bounds[-1] + win, k - int(search_s * sample_rate))
        hi = min(k + int(search_s * sample_rate), n - win)
        if hi <= lo:
            bounds.append(k)
        else:
            cands = starts[(starts >= lo) & (starts <= hi)]
            if len(cands) == 0:
                bounds.append(k)
            else:
                best = min(cands, key=lambda c: _window_energy(int(c)))
                bounds.append(int(best + win // 2))
        k += target
    bounds.append(n)
    return [(a / float(sample_rate), audio[a:b]) for a, b in zip(bounds[:-1], bounds[1:], strict=True)]


def _offset_segment(seg: Any, offset: float) -> Any:
    """Copy a segment with start/end shifted by ``offset`` seconds."""
    start = (seg.start or 0.0) + offset
    end = (seg.end or seg.start or 0.0) + offset
    try:
        import dataclasses

        return dataclasses.replace(seg, start=start, end=end)
    except Exception:
        import copy

        dup = copy.copy(seg)
        dup.start = start
        dup.end = end
        return dup


def _decode_segments(engine: Any, audio: Any, use_vad_filter: bool, duration: float) -> tuple[Any, Any]:
    """Decode to ``(segments, info)`` with identical params either way.

    Long CUDA audio goes through ``BatchedInferencePipeline`` in
    silence-split super-chunks (lazy: each piece decodes only when the
    consumer's abort-checked loop reaches it). Everything else takes the
    original single sequential call.
    """
    kwargs = {
        "beam_size": engine.beam_size,
        "temperature": 0.0,
        "vad_filter": use_vad_filter,
        "vad_parameters": _VAD_PARAMETERS,
        "language": engine.language,
        "condition_on_previous_text": engine.condition_on_previous_text,
        "without_timestamps": True,
    }
    if duration <= _BATCHED_MIN_DURATION_S:
        return engine._model.transcribe(audio, **kwargs)
    pipeline = _batched_pipeline_for(engine)
    if pipeline is None:
        return engine._model.transcribe(audio, **kwargs)
    chunks = _split_on_silence(audio, _WHISPER_SAMPLE_RATE)
    log.info(
        "[TRANSCRIBE] batched decode: batch_size=%d, %d super-chunks (%.0fs audio)",
        _BATCHED_BATCH_SIZE,
        len(chunks),
        duration,
    )
    # Decode the first piece eagerly so a REAL info object is available
    # immediately (the caller logs info.language after the loop). The rest
    # stays lazy: each later piece decodes only when the consumer's
    # abort-checked loop reaches it, bounding ESC latency to one piece.
    chunk_iter = iter(chunks)
    first_offset, first_piece = next(chunk_iter)
    first_segments, info = pipeline.transcribe(first_piece, batch_size=_BATCHED_BATCH_SIZE, **kwargs)

    def _gen() -> Any:
        for seg in first_segments:
            yield _offset_segment(seg, first_offset) if first_offset else seg
        for offset, piece in chunk_iter:
            segments, _ = pipeline.transcribe(piece, batch_size=_BATCHED_BATCH_SIZE, **kwargs)
            for seg in segments:
                yield _offset_segment(seg, offset) if offset else seg

    return _gen(), info
