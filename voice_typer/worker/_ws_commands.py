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
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from voice_typer.worker._ws_samples import (
    _SamplesBuffer,
    _valid_request_id,
    _valid_samples_header,
)

log = logging.getLogger("voice_typer.worker")

# Cooperative shutdown abort for model loads. A threading.Event because the
# load body runs on a default-executor thread: cancelling the asyncio task
# alone cannot stop that thread, and asyncio.run() joins the executor at
# finalization. Load paths re-check this so the join is bounded.
model_load_abort = threading.Event()

# Model-load tasks, registered so shutdown can drain them under a deadline.
# Mirrors the per-connection in_flight set used for transcription launches.
model_loads: set = set()

# Ceiling on the model-load drain. A load already deep in a blocking native
# call cannot be interrupted, so the abort event is what actually bounds exit.
MODEL_LOAD_DRAIN_TIMEOUT_S = 5.0


def _shutdown_load_result(backend: str) -> dict:
    """Uniform result for a load skipped/aborted by shutdown (C-LOG-5 line)."""
    return {"loaded": False, "backend": backend, "device_info": None, "error": "cancelled during shutdown"}


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


def _spawn_model_load(
    handles: _CommandHandles,
    *,
    backend: str,
    result_type: str,
    request_id: int,
    run: Callable[[], dict],
) -> None:
    """Run one model load as a TRACKED task with a cooperative abort.

    Every load path funnels through here so no load coroutine escapes the
    shutdown drain. The task registers itself in ``model_loads``, re-checks
    ``model_load_abort`` before and after the executor call, and logs one
    cancellation outcome (C-LOG-5) when shutdown wins the race.
    """
    import asyncio as _asyncio

    async def _do() -> None:
        if model_load_abort.is_set():
            log.info("[WORKER] %s model load cancelled during shutdown (before start)", backend)
            result = _shutdown_load_result(backend)
        else:
            try:
                result = await _asyncio.to_thread(run)
            except _asyncio.CancelledError:
                log.info("[WORKER] %s model load cancelled during shutdown", backend)
                raise
            except Exception as exc:  # noqa: BLE001, never leave the request hanging
                log.exception("[WORKER] %s model thread raised: %s", backend, exc)
                result = {
                    "loaded": False,
                    "backend": backend,
                    "device_info": None,
                    "error": f"internal error: {exc}",
                }
            if model_load_abort.is_set():
                log.info("[WORKER] %s model load cancelled during shutdown", backend)
                result = _shutdown_load_result(backend)
        with contextlib.suppress(Exception):
            await handles.websocket.send(json.dumps({"type": result_type, "id": request_id, "data": result}))

    # Register at creation, not inside _do: a coroutine that has not yet
    # started must still be in the shutdown drain.
    task = _asyncio.ensure_future(_do())
    model_loads.add(task)
    task.add_done_callback(model_loads.discard)


async def handle_load_whisper_model_async(frame: dict, handles: _CommandHandles) -> None:
    """Load a whisper model in the worker; answer ``load_whisper_model_result``."""
    request_id = _valid_request_id(frame.get("id"))
    if request_id is None:
        log.warning("[WORKER] load_whisper_model without a numeric id: ignoring")
        return
    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
    model_size = data.get("model_size")
    device = data.get("device")
    language = data.get("language")
    if not isinstance(model_size, str) or not model_size:
        with contextlib.suppress(Exception):
            await handles.websocket.send(
                json.dumps(
                    {
                        "type": "load_whisper_model_result",
                        "id": request_id,
                        "data": {
                            "loaded": False,
                            "backend": "whisper",
                            "device_info": "",
                            "error": "missing model_size",
                        },
                    }
                )
            )
        return

    def _run(
        _size: str = model_size,
        _device: object = device,
        _lang: object = language,
    ) -> dict:
        if model_load_abort.is_set():
            return _shutdown_load_result("whisper")
        from voice_typer.worker._transcribe import get_transcriber

        return get_transcriber().load_whisper_model(
            _size,
            str(_device) if _device is not None else None,
            str(_lang) if _lang is not None else None,
        )

    _spawn_model_load(
        handles,
        backend="whisper",
        result_type="load_whisper_model_result",
        request_id=request_id,
        run=_run,
    )


async def _handle_load_async(
    frame: dict,
    handles: _CommandHandles,
    *,
    backend: str,
    result_type: str,
    run: Callable[[], dict],
    missing_error: str | None = None,
) -> None:
    """Shared tail for the explicit model-load commands.

    Validates the id, short-circuits a missing required field with a
    structured error frame, and runs the (blocking) load in a thread so
    heartbeats keep flowing; the request always resolves with a result.
    """
    request_id = _valid_request_id(frame.get("id"))
    if request_id is None:
        log.warning("[WORKER] %s without a numeric id: ignoring", result_type.removesuffix("_result"))
        return
    if missing_error is not None:
        with contextlib.suppress(Exception):
            await handles.websocket.send(
                json.dumps(
                    {
                        "type": result_type,
                        "id": request_id,
                        "data": {"loaded": False, "backend": backend, "device_info": "", "error": missing_error},
                    }
                )
            )
        return

    _spawn_model_load(
        handles,
        backend=backend,
        result_type=result_type,
        request_id=request_id,
        run=run,
    )


async def handle_load_parakeet_model_async(frame: dict, handles: _CommandHandles) -> None:
    """Load the parakeet model in the worker; answer ``load_parakeet_model_result``."""
    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
    device = data.get("device")
    language = data.get("language")

    def _run(_device: object = device, _lang: object = language) -> dict:
        if model_load_abort.is_set():
            return _shutdown_load_result("parakeet")
        from voice_typer.worker._transcribe import get_transcriber

        return get_transcriber().load_parakeet_model(
            str(_device) if _device is not None else None,
            str(_lang) if _lang is not None else None,
        )

    await _handle_load_async(
        frame, handles, backend="parakeet", result_type="load_parakeet_model_result", run=_run
    )


async def handle_load_qwen_model_async(frame: dict, handles: _CommandHandles) -> None:
    """Load the qwen model in the worker; answer ``load_qwen_model_result``."""
    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
    model_path = data.get("model_path")
    device = data.get("device")
    language = data.get("language")
    missing_error = None if isinstance(model_path, str) and model_path else "missing model_path"

    def _run(
        _path: str = model_path if isinstance(model_path, str) else "",
        _device: object = device,
        _lang: object = language,
    ) -> dict:
        if model_load_abort.is_set():
            return _shutdown_load_result("qwen")
        from voice_typer.worker._transcribe import get_transcriber

        return get_transcriber().load_qwen_model(
            _path,
            str(_device) if _device is not None else None,
            str(_lang) if _lang is not None else None,
        )

    await _handle_load_async(
        frame,
        handles,
        backend="qwen",
        result_type="load_qwen_model_result",
        run=_run,
        missing_error=missing_error,
    )


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
