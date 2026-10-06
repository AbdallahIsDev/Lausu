"""Transcription result normalization for ``TranscriptionEngine``.

CANONICAL home of the segment-decode bodies:
``TranscriptionEngine._transcribe_unlocked`` /
``_transcribe_words_unlocked`` are thin one-line delegates to the
functions here (the engine module stays focused on the
load/transcribe pipeline). The functions are also unit-testable in
isolation with stub engines.

* :func:`transcribe_unlocked`: the body of
  :meth:`TranscriptionEngine._transcribe_unlocked`. Drives the
  faster-whisper ``model.transcribe(...)`` call, iterates the segment
  generator (with abort-token check between iterations), collects
  per-segment logprobs / no_speech_probs, builds the compact
  ``last_quality_summary``, applies the low-audio-hallucination
  rejection gate, and returns the joined text. PII-safety:
  per-segment DEBUG logs are gated by ``config.log_transcriptions``
  AND wrapped in ``redact_pii`` when emitted.
* :func:`transcribe_words_unlocked`: the body of
  :meth:`TranscriptionEngine._transcribe_words_unlocked`. Streaming
  word-timestamp variant of the above (used by the streaming
  pipeline). Returns a list of :class:`streaming.WordTiming` objects.
* :func:`format_optional_mean`: formats a list of floats as a
  2-decimal mean, or ``"n/a"`` if empty. Used by the VAD-result log
  line in :func:`transcribe_unlocked`.
* :func:`build_quality_summary`: the compact per-dictation quality
  dict built from the already-collected segment stats; re-exported by
  ``transcription`` for back-compat with callers/tests importing it
  from there.
* :func:`reject_low_audio_hallucination`: thin delegator to
  :func:`hallucination.should_reject_low_audio_hallucination` so the
  engine method can delegate without importing ``hallucination``.

TEST PATCH COMPATIBILITY: tests patch
``voice_typer.server.transcription_result.should_reject_low_audio_hallucination``
(module global) and it stays effective because
:func:`reject_low_audio_hallucination` reads the module global at call
time.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from voice_typer.server._audio_constants import (
    WHISPER_SAMPLE_RATE as _WHISPER_SAMPLE_RATE,
    peak_amplitude,
    silence_percent,
)
from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.hallucination import (
    REJECTION_REASON_HALLUCINATION,
    log_hallucination_rejection,
    should_reject_low_audio_hallucination,
)
from voice_typer.server.vad_policy import decide_vad_filter

np = lazy_module("numpy")

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

# Use the ``transcription`` logger name so log records emitted from this
log = logging.getLogger("voice_typer.server.transcription")


def format_optional_mean(values: list[float]) -> str:
    """Format a list of floats as a 2-decimal mean, or 'n/a' if empty.

    Small helper kept as-is because it has two call sites
    (the avg_logprob + no_speech_prob log fields in
    :func:`transcribe_unlocked`) and inlining would duplicate the
    empty-list check.
    """
    if not values:
        return "n/a"
    return f"{sum(values) / len(values):.2f}"


def _batched_pipeline_for(engine: Any) -> Any | None:
    """Return a ``BatchedInferencePipeline`` for ``engine._model``, or None.

    None means "stay sequential": non-CUDA device, previous-text
    conditioning (batched windows decode independently, so chaining
    context across them would change results), a mocked/non-faster-whisper
    model (unit tests), or a missing faster-whisper install. The import is
    function-local so the slim-core import ratchet never sees it.
    """
    if getattr(engine, "condition_on_previous_text", False):
        return None
    if getattr(engine, "_device", "cpu") != "cuda":
        return None
    model = getattr(engine, "_model", None)
    if model is None or type(model).__module__.split(".")[0] != "faster_whisper":
        return None
    try:
        from faster_whisper import BatchedInferencePipeline
    except ImportError:
        return None
    try:
        return BatchedInferencePipeline(model)
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


def reject_low_audio_hallucination(
    engine: Any,
    *,
    result: str,
    rms: float,
    peak: float,
    silence_pct: float,
    duration: float,
    first_segment_start: float | None,
    last_segment_end: float | None,
    no_speech_prob: float | None = None,
    avg_logprob: float | None = None,
) -> bool:
    """Thin delegator to :func:`hallucination.should_reject_low_audio_hallucination`.

    Reads the user's ``hallucination_filter_mode`` off the engine's config and
    stamps ``engine.last_rejection_reason`` when it fires, so the dictation
    pipeline can report the real cause instead of "no speech detected".
    """
    mode = getattr(getattr(engine, "config", None), "hallucination_filter_mode", None)
    rejected = should_reject_low_audio_hallucination(
        result,
        rms,
        peak=peak,
        silence_pct=silence_pct,
        duration=duration,
        first_segment_start=first_segment_start,
        last_segment_end=last_segment_end,
        no_speech_prob=no_speech_prob,
        avg_logprob=avg_logprob,
        mode=mode,
    )
    engine.last_rejection_reason = REJECTION_REASON_HALLUCINATION if rejected else None
    return rejected


def transcribe_unlocked(
    engine: Any,
    audio,
    audio_stats: tuple[float, float, float] | None = None,
) -> str:
    """Body of :meth:`TranscriptionEngine._transcribe_unlocked`.

    Drives the faster-whisper ``model.transcribe(...)`` call, iterates
    the segment generator (with abort-token check between iterations),
    collects per-segment logprobs / no_speech_probs, builds
    ``engine.last_quality_summary``, applies the low-audio-hallucination
    rejection gate, and returns the joined text.

    Reads per-cycle state from the engine argument (``engine._model``,
    ``engine.beam_size``, ``engine.language``, ``engine._abort_event``,
    ``engine.config``) and writes the quality summary back to it.
    """
    if engine._model is None:
        raise RuntimeError("Model not loaded. Call load() first.")

    if len(audio) == 0:
        return ""

    # Log audio statistics for diagnostics
    duration = len(audio) / _WHISPER_SAMPLE_RATE
    # reuse pre-computed stats when provided (avoids
    if audio_stats is not None:
        rms, peak, silence_pct = audio_stats
    else:
        rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
        peak = peak_amplitude(audio)
        silence_pct = silence_percent(audio)
    # Duration-aware VAD policy: trim once here when the recording is
    audio, use_vad_filter, _trim_offset_s = decide_vad_filter(
        audio,
        _WHISPER_SAMPLE_RATE,
        (rms, peak, silence_pct),
        getattr(engine.config, "vad_filter_enabled", True),
    )
    duration = len(audio) / _WHISPER_SAMPLE_RATE
    log.info(
        "[TRANSCRIBE] Input audio: samples=%d, duration=%.1fs | RMS=%.6f, peak=%.6f, silence_pct=%.1f%%",
        len(audio),
        duration,
        rms,
        peak,
        silence_pct,
    )
    if rms < 0.001:
        log.warning(
            "[TRANSCRIBE] Near-silence input (RMS=%.6f). Speech detection is unlikely.",
            rms,
        )

    # NOTE: ``best_of`` is deliberately NOT passed, faster-whisper only
    # Batched on long CUDA audio (identical params, parallel windows),
    # sequential otherwise. See _decode_segments.
    segments, info = _decode_segments(engine, audio, use_vad_filter, duration)

    # Collect segments and log VAD info
    text_parts: list[str] = []
    segment_count = 0
    first_segment_start = None
    last_segment_end = None
    avg_logprobs = []
    no_speech_probs = []
    # Reset the renderer-facing quality summary at the START of each
    engine.last_quality_summary = None
    # hoist the per-segment ``log_transcriptions`` flag and
    _log_transcriptions_flag = engine.config is not None and getattr(engine.config, "log_transcriptions", False)
    _redact_pii = None
    if _log_transcriptions_flag:
        try:
            from voice_typer.server.security import redact_pii as _redact_pii
        except Exception:
            _redact_pii = None
    for seg in segments:
        # Check the abort token BETWEEN segment iterations. The
        if engine._abort_event.is_set():
            log.info(
                "[TRANSCRIBE] Abort requested, stopping segment loop early (completed %d segments, %d text parts)",
                segment_count,
                len(text_parts),
            )
            break
        segment_count += 1
        start = seg.start or 0.0
        end = seg.end or start
        if first_segment_start is None:
            first_segment_start = start
        last_segment_end = end
        avg_logprob = getattr(seg, "avg_logprob", None)
        no_speech_prob = getattr(seg, "no_speech_prob", None)
        if isinstance(avg_logprob, int | float):
            avg_logprobs.append(float(avg_logprob))
        if isinstance(no_speech_prob, int | float):
            no_speech_probs.append(float(no_speech_prob))
        if seg.text.strip():
            text_parts.append(seg.text.strip())
            # gate the per-segment DEBUG log by
            _seg_text = seg.text.strip()
            if _log_transcriptions_flag and _redact_pii is not None:
                try:
                    _safe_seg_text = _redact_pii(_seg_text)
                except Exception:
                    # fall back to a redacted marker only, do NOT
                    log.warning(
                        "[TRANSCRIBE] Segment: [%.1fs - %.1fs] "
                        "<redaction-engine-failed, segment text NOT "
                        "logged to preserve PII guarantee; enable "
                        "voice_typer.server.security.redact_pii and "
                        "retry>",
                        start,
                        end,
                    )
                    _safe_seg_text = None  # skip the log.debug below
                if _safe_seg_text is not None:
                    log.debug(
                        "[TRANSCRIBE] Segment: [%.1fs - %.1fs] %s",
                        start,
                        end,
                        _safe_seg_text,
                    )

    log.info(
        "[TRANSCRIBE] VAD result: language=%s (prob=%.2f) | "
        "segments=%d, text_segments=%d | avg_logprob=%s, no_speech_prob=%s",
        info.language,
        info.language_probability,
        segment_count,
        len(text_parts),
        format_optional_mean(avg_logprobs),
        format_optional_mean(no_speech_probs),
    )

    # Compact quality summary for the dictation pipeline → renderer
    engine.last_quality_summary = build_quality_summary(avg_logprobs, no_speech_probs)

    result = " ".join(text_parts).strip()
    # Mean of the per-segment probs is the signal the balanced mode needs:
    # a fabricated phrase on silence carries a high ``no_speech_prob`` and a
    # low ``avg_logprob``, a genuinely spoken "so" carries the opposite.
    _mean_logprob = (sum(avg_logprobs) / len(avg_logprobs)) if avg_logprobs else None
    _max_no_speech = max(no_speech_probs) if no_speech_probs else None
    if reject_low_audio_hallucination(
        engine,
        result=result,
        rms=rms,
        peak=peak,
        silence_pct=silence_pct,
        duration=duration,
        first_segment_start=first_segment_start,
        last_segment_end=last_segment_end,
        no_speech_prob=_max_no_speech,
        avg_logprob=_mean_logprob,
    ):
        # Use the PII-safe logging helper instead of raw text
        log_transcriptions = engine.config is not None and getattr(engine.config, "log_transcriptions", False)
        log_hallucination_rejection(
            "[TRANSCRIBE]",
            result,
            reason="low-audio hallucination",
            log_transcriptions=log_transcriptions,
        )
        log.info(
            "[TRANSCRIBE] Hallucination stats: duration=%.1fs | RMS=%.6f, peak=%.6f, silence=%.1f%%",
            duration,
            rms,
            peak,
            silence_pct,
        )
        return ""
    if result:
        log.info("[TRANSCRIBE] Result: %d chars", len(result))
    else:
        log.info(
            "[TRANSCRIBE] No speech detected (RMS=%.6f, silence=%.1f%%)",
            rms,
            silence_pct,
        )
    return result


def transcribe_words_unlocked(
    engine: Any,
    audio,
    offset_seconds: float,
):
    """Body of :meth:`TranscriptionEngine._transcribe_words_unlocked`.

    Streaming word-timestamp variant of :func:`transcribe_unlocked`.
    Returns a list of :class:`streaming.WordTiming` objects.
    """
    if engine._model is None:
        raise RuntimeError("Model not loaded. Call load() first.")

    if len(audio) == 0:
        return []

    from voice_typer.server.streaming import WordTiming

    # Same duration-aware VAD policy as the batch path (stats are
    audio, use_vad_filter, trim_offset_s = decide_vad_filter(
        audio,
        _WHISPER_SAMPLE_RATE,
        None,
        getattr(engine.config, "vad_filter_enabled", True),
    )

    # Same ``best_of`` reasoning as ``transcribe_unlocked`` above: a no-op
    segments, _info = engine._model.transcribe(
        audio,
        beam_size=engine.beam_size,
        temperature=0.0,
        vad_filter=use_vad_filter,
        vad_parameters=_VAD_PARAMETERS,
        language=engine.language,
        condition_on_previous_text=engine.condition_on_previous_text,
        word_timestamps=True,
        without_timestamps=False,
    )

    words = []
    segment_count = 0
    for seg in segments:
        # Check the abort token BETWEEN segment iterations,
        if engine._abort_event.is_set():
            log.info(
                "[TRANSCRIBE] Abort requested, stopping streaming "
                "words segment loop early (completed %d segments, "
                "%d words)",
                segment_count,
                len(words),
            )
            break
        segment_count += 1
        for word in getattr(seg, "words", None) or []:
            text = (word.word or "").strip()
            if not text:
                continue
            start = (word.start or 0.0) + offset_seconds + trim_offset_s
            end = (word.end or word.start or 0.0) + offset_seconds + trim_offset_s
            words.append(
                WordTiming(
                    word=text,
                    start_seconds=start,
                    end_seconds=end,
                )
            )
    return words


def build_quality_summary(avg_logprobs: list[float], no_speech_probs: list[float]) -> dict[str, float] | None:
    """Build the compact per-dictation quality summary for the renderer.

    Computed from the ``avg_logprob`` / ``no_speech_prob`` values the
    segment loop ALREADY collected, no recomputation, one small dict of
    floats allocated once per dictation (never on the paste hot path).

    Returns ``None`` when no numeric stats were collected (empty audio,
    aborted run, or an engine that reports no segment probs) so callers
    can omit the summary entirely instead of shipping an empty object.

    Keys:
      - ``mean_logprob``: mean per-segment ``avg_logprob`` (closer to 0 =
        more confident decoding).
      - ``min_logprob``: worst single-segment ``avg_logprob``.
      - ``no_speech_prob_max``: highest per-segment ``no_speech_prob``
        (high values indicate segments the model considered silent).
      - ``segments``: how many segments contributed numeric stats.
    """
    if not avg_logprobs and not no_speech_probs:
        return None
    summary: dict[str, float] = {}
    if avg_logprobs:
        summary["mean_logprob"] = sum(avg_logprobs) / len(avg_logprobs)
        summary["min_logprob"] = min(avg_logprobs)
        summary["segments"] = float(len(avg_logprobs))
    if no_speech_probs:
        summary["no_speech_prob_max"] = max(no_speech_probs)
    return summary
