"""Worker WS command handlers: offline / samples / abort.

Split out of the frame-IO seam (``voice_typer.worker._ws_connection``) so
no single file exceeds the wave-9 size budget. Each handler receives the
per-connection handles explicitly (:class:`_CommandHandles`) instead of
closing over them, so the frame loop in ``_ws_connection`` stays a thin
dispatcher. No WS frame or ordering change: every handler emits exactly
the frames the inline block did, in the same order.
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from voice_typer.worker._ws_samples import (
    _SamplesBuffer,
    _valid_request_id,
    _valid_samples_header,
)

log = logging.getLogger("voice_typer.worker")


@dataclass
class _CommandHandles:
    """Per-connection state + shared tails the command handlers use.

    ``complete`` / ``launch`` are the frame-IO seam's shared closures
    (defined per connection in ``_ws_connection``); passing them keeps the
    handlers free of module-global mutable state.
    """

    websocket: Any
    samples: dict[int, _SamplesBuffer]
    aborted: set[int]
    streams: dict
    complete: Callable[..., Any]
    launch: Callable[..., Any]


def handle_transcribe_offline(frame: dict, handles: _CommandHandles) -> None:
    """Real offline ASR in the worker (master plan §7.4).

    The slim-core sidecar forwards ``{audio_path, sample_rate, language}``;
    the worker transcribes and pushes the result back via the
    ``transcribe_offline_result`` event. The inference is blocking C-level
    work, run it in a thread so heartbeats + shutdown stay responsive
    mid-inference.
    """
    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
    audio_path = str(data.get("audio_path") or "")
    sample_rate = data.get("sample_rate")
    language = data.get("language")
    log.info(
        "[WORKER] transcribe_offline request (path=%s, sr=%s, lang=%s): running in thread",
        audio_path,
        sample_rate,
        language,
    )

    # Bind the loop variables into the closure's defaults so the thread
    # function does not capture the loop variables by reference (B023, the
    # connection handler's frame loop mutates them on each iteration).
    def _run(
        _path: str = audio_path,
        _sr: object = sample_rate,
        _lang: object = language,
    ) -> dict:
        from voice_typer.worker._transcribe import get_transcriber

        return get_transcriber().transcribe_file(
            _path,
            int(_sr) if isinstance(_sr, (int, str)) and _sr not in (None, "") else None,
            str(_lang) if _lang is not None else None,
        )

    handles.launch(_run, _valid_request_id(frame.get("id")))


async def handle_transcribe_samples(frame: dict, handles: _CommandHandles) -> None:
    """ADR-0025 C3: in-memory float32 PCM in base64 chunks.

    Each chunk carries (id, index, total) so reassembly needs no ordering
    assumption; the final chunk's arrival triggers inference in a thread
    (heartbeats + shutdown stay responsive, same as the file path).
    Malformed input resolves to a structured error RESULT (with the id)
    rather than silence, so a client Future never hangs on a corrupt
    chunk.
    """
    request_id = _valid_request_id(frame.get("id"))
    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
    if request_id is None:
        log.warning("[WORKER] transcribe_samples without a numeric id: ignoring")
        return
    if request_id in handles.aborted:
        handles.aborted.discard(request_id)
        handles.samples.pop(request_id, None)
        await handles.complete(lambda: {"text": "", "error": "request aborted"}, request_id)
        return
    total, index, sample_rate, language, header_error = _valid_samples_header(data)
    if header_error is not None:
        await handles.complete(lambda _e=header_error: {"text": "", "error": _e}, request_id)
        handles.samples.pop(request_id, None)
        return
    buffer = handles.samples.get(request_id)
    if buffer is None:
        buffer = _SamplesBuffer(total, sample_rate, language)
        handles.samples[request_id] = buffer
    elif buffer.total != total:
        handles.samples.pop(request_id, None)
        await handles.complete(lambda: {"text": "", "error": "chunk total mismatch"}, request_id)
        return
    chunk_error = buffer.add_chunk(index, data.get("payload_b64"))
    if chunk_error is not None:
        handles.samples.pop(request_id, None)
        await handles.complete(lambda _e=chunk_error: {"text": "", "error": _e}, request_id)
        return
    if not buffer.is_complete():
        return
    raw = buffer.audio_bytes()
    handles.samples.pop(request_id, None)
    log.info(
        "[WORKER] transcribe_samples request id=%s complete (%d bytes, sr=%s): running in thread",
        request_id,
        len(raw),
        buffer.sample_rate,
    )

    def _run_samples(
        _raw: bytes = raw,
        _sr: int = buffer.sample_rate,
        _lang: object = buffer.language,
    ) -> dict:
        import numpy as _np

        from voice_typer.worker._transcribe import get_transcriber

        audio = _np.frombuffer(_raw, dtype=_np.float32).copy()
        return get_transcriber().transcribe_array(audio, _sr, str(_lang) if _lang is not None else None)

    handles.launch(_run_samples, request_id)


async def handle_abort_request(frame: dict, handles: _CommandHandles) -> None:
    """ADR-0025 C4: best-effort cooperative abort.

    Signals the loaded backend (never builds one), drops any partial
    sample buffer, and marks the id so a result that is already past the
    point of no return is discarded instead of sent. Idempotent: unknown
    ids still ack.
    """
    request_id = _valid_request_id(frame.get("id"))
    if request_id is None:
        log.warning("[WORKER] abort_request without a numeric id: ignoring")
        return
    handles.aborted.add(request_id)
    handles.samples.pop(request_id, None)
    # C6: an abort also tears down live streaming state for the id.
    handles.streams.pop(request_id, None)
    from voice_typer.worker._transcribe import get_transcriber

    signalled = get_transcriber().request_abort()
    log.info("[WORKER] abort_request id=%s (backend signalled=%s)", request_id, signalled)
    with contextlib.suppress(Exception):
        await handles.websocket.send(
            json.dumps({"type": "abort_ack", "id": request_id, "data": {"aborted": True}})
        )
