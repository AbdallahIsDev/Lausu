"""Lock-free per-chunk inference loops for the Qwen3-ASR engine.

Split out of ``voice_typer.server.qwen_engine`` (one concern per file):
the facade keeps the lock discipline (RACE-032) and the chunk
orchestration, this module owns only the leaf loops that decode chunks
once the model reference has been taken under the lock. Each function
takes the engine as its first argument and calls back through the
engine's own methods, so the facade's call graph and its monkeypatch
seams stay unchanged.
"""

import logging
import threading
from typing import Any, Protocol

import numpy as np

from voice_typer.server.hallucination import log_hallucination_rejection, reject_and_stamp_reason

log = logging.getLogger(__name__)


class _QwenChunkingHost(Protocol):
    """Engine surface these loops drive, owned by ``QwenEngine``.

    Declared here so the loops stay type-checked against the real host
    instead of an ``Any`` handle that would erase the callbacks' return
    types.
    """

    _INFERENCE_BATCH_SIZE: int
    _abort_event: threading.Event
    language: str

    def _transcribe_chunks_sequential(
        self,
        model: Any,
        chunks: list[np.ndarray],
        sample_rate: int,
    ) -> list[str]: ...

    def _transcribe_batch(
        self,
        model: Any,
        batch: list[np.ndarray],
        sample_rate: int,
    ) -> list[str]: ...


def transcribe_chunks_batched(
    engine: _QwenChunkingHost,
    model: Any,
    chunks: list[np.ndarray],
    sample_rate: int,
) -> list[str]:
    """Transcribe ``chunks`` in batches, falling back to sequential on OOM.

    Mirrors ParakeetEngine._transcribe_chunks_batched.  When
    ``_INFERENCE_BATCH_SIZE`` is 1 (default), this function is
    strictly sequential and preserves the historical call-count
    contract pinned by ``test_qwen_engine_overlap_dedup.py``
    (one ``model.transcribe()`` call per chunk, in order).  When
    set to 2+ via the ``QWEN_BATCH_SIZE`` env var, we group that
    many chunks per ``model.transcribe()`` call.  On an OOM
    (``"out of memory"`` in the error string), we fall back to
    per-chunk sequential inference for the remaining chunks so the
    user still gets a transcription.

    Returns a list of text strings (one per chunk).  Empty strings
    indicate hallucination rejection or no speech, the caller's
    dedup pass skips them without advancing ``prev_text``.

    NOTE: The batched path (``_INFERENCE_BATCH_SIZE > 1``) assumes
    the model adapter accepts a list of ``(audio, sample_rate)``
    tuples as its first positional arg.  The ONNX adapter's
    ``transcribe`` currently accepts a single tuple; if a batched
    call raises, the sequential fallback fires, so correctness is
    preserved even if the batched path is unavailable.
    """
    if not chunks:
        return []

    if engine._INFERENCE_BATCH_SIZE <= 1 or len(chunks) == 1:
        return engine._transcribe_chunks_sequential(model, chunks, sample_rate)

    results: list[str] = []
    i = 0
    while i < len(chunks):
        # Same abort check as the sequential branch, see above.
        if engine._abort_event.is_set():
            log.info(
                "[QWEN] Abort requested, stopping batch loop early (completed %d/%d chunks)",
                i,
                len(chunks),
            )
            break
        batch = chunks[i : i + engine._INFERENCE_BATCH_SIZE]
        i += len(batch)
        log.info(
            "[QWEN] Transcribing batch of %d chunks (%d/%d done)",
            len(batch),
            i - len(batch),
            len(chunks),
        )
        try:
            batch_texts = engine._transcribe_batch(model, batch, sample_rate)
            results.extend(batch_texts)
        except Exception as exc:
            err_str = str(exc).lower()
            if "out of memory" in err_str or ("cuda" in err_str and "allocat" in err_str):
                log.warning(
                    "[QWEN] Batched inference OOM on batch of %d chunks, falling back to sequential: %s",
                    len(batch),
                    exc,
                    exc_info=True,
                )
                seq_texts = engine._transcribe_chunks_sequential(model, batch, sample_rate)
                results.extend(seq_texts)
            else:
                raise
    # than chunks (shouldn't happen, but defensive).
    while len(results) < len(chunks):
        results.append("")
    return results[: len(chunks)]


def transcribe_chunks_sequential(
    engine: _QwenChunkingHost,
    model: Any,
    chunks: list[np.ndarray],
    sample_rate: int,
) -> list[str]:
    """Transcribe chunks one at a time (the default path).

    Extracted from the pre-batched ``_transcribe_chunked`` body so
    ``_transcribe_chunks_batched`` can fall back to it on OOM
    without duplicating the per-chunk hallucination-filter logic.
    """
    results: list[str] = []
    for i, chunk in enumerate(chunks):
        # Abort check: break out after the current chunk when an
        if engine._abort_event.is_set():
            log.info(
                "[QWEN] Abort requested, stopping chunk loop early (completed %d/%d chunks)",
                i,
                len(chunks),
            )
            break
        log.info(
            "[QWEN] Transcribing chunk %d/%d (%.1fs)",
            i + 1,
            len(chunks),
            len(chunk) / sample_rate,
        )
        chunk_result = model.transcribe(
            (chunk, sample_rate),
            language=engine.language,
        )
        if not chunk_result:
            results.append("")
            continue
        text = chunk_result[0].text if hasattr(chunk_result[0], "text") else str(chunk_result[0])
        text = text.strip()
        if not text:
            results.append("")
            continue
        # Per-chunk hallucination filter using the chunk's own RMS.
        rms = float(np.sqrt(np.mean(np.square(chunk), dtype=np.float64)))
        if reject_and_stamp_reason(engine, text, rms):
            # SEC-009: Use PII-safe logging helper instead of raw text
            log_hallucination_rejection(
                "[QWEN]",
                text,
                reason="hallucination",
                log_transcriptions=False,
            )
            results.append("")
            continue
        results.append(text)
    return results


def transcribe_batch(
    engine: _QwenChunkingHost,
    model: Any,
    batch: list[np.ndarray],
    sample_rate: int,
) -> list[str]:
    """Run ``model.transcribe`` on a batch of chunks in one call.

    Assumes the model adapter accepts a list of ``(audio,
    sample_rate)`` tuples as its first positional arg.  If the API
    does not support batched input, this function raises and the
    caller (``_transcribe_chunks_batched``) falls back to
    ``_transcribe_chunks_sequential``.
    """
    # Build list of (audio, sample_rate) tuples, one per chunk.
    inputs = [(chunk, sample_rate) for chunk in batch]
    results = model.transcribe(inputs, language=engine.language)
    # Decode each result, apply per-chunk hallucination filter.
    texts: list[str] = []
    for idx, chunk_result in enumerate(results or []):
        if idx >= len(batch):
            break
        if not chunk_result:
            texts.append("")
            continue
        text = chunk_result.text if hasattr(chunk_result, "text") else str(chunk_result)
        text = text.strip()
        if not text:
            texts.append("")
            continue
        rms = float(np.sqrt(np.mean(np.square(batch[idx]), dtype=np.float64)))
        if reject_and_stamp_reason(engine, text, rms):
            log_hallucination_rejection(
                "[QWEN]",
                text,
                reason="hallucination",
                log_transcriptions=False,
            )
            texts.append("")
            continue
        texts.append(text)
    # than chunks (defensive, shouldn't happen with a correct
    while len(texts) < len(batch):
        texts.append("")
    return texts
