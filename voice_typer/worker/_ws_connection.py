"""Frame-IO seam of the worker WS server: one connection's command loop.

Split out of ``voice_typer.worker._ws_server`` (one concern per file).
The facade keeps the module names and every monkeypatch seam;
``transcribe_window_words`` in particular is patched ON the facade by
tests, so this module reads it through a facade proxy at call time
(``_facade``), never as a local import binding. The offline / samples /
abort command bodies live in :mod:`voice_typer.worker._ws_commands` (the
size budget); this module owns the loop + the streaming command bodies.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING

from voice_typer.server._lazy_import import lazy_module
from voice_typer.worker._auth import _authenticate, _send_auth_failed_and_close
from voice_typer.worker._ws_commands import (
    _CommandHandles,
    handle_abort_request,
    handle_transcribe_offline,
    handle_transcribe_samples,
)
from voice_typer.worker._ws_samples import _SamplesBuffer, _valid_request_id, _word_to_dict
from voice_typer.worker._ws_shutdown import _ShutdownTimer
from voice_typer.worker.streaming import SessionConfig, StreamingSession, to_16k_array

if TYPE_CHECKING:
    import asyncio

log = logging.getLogger("voice_typer.worker")

# The facade module, read at call time so patches on it are honored
# (tests monkeypatch ``voice_typer.worker._ws_server.transcribe_window_words``).
_facade = lazy_module("voice_typer.worker._ws_server")


# ─── Connection handler ───────────────────────────────────────────────


async def _handle_connection(  # noqa: ANN001 - websockets type is imported lazily
    websocket,
    *,
    prewarm_ran: bool,
    stop_event: asyncio.Event,
    shutdown_timer: _ShutdownTimer,
) -> None:
    """Handle one WS connection from the slim-core sidecar.

    Authenticate, acknowledge heartbeats, dispatch ``shutdown``, and
    dispatch ``transcribe_offline`` (real ASR, the inference runs in
    a thread via :func:`get_transcriber`, the result is pushed back as
    ``transcribe_offline_result``). Unknown commands get an
    ``error`` envelope with ``code: "unknown_command"``.

    On ``shutdown``: send ``shutdown_ack``, mark the shutdown timer's
    start, set ``stop_event`` (so :func:`run_worker_server`'s
    ``await stop_event.wait()`` unblocks), then close the socket. The
    ``stop_event.set()`` MUST be called BEFORE ``websocket.close()`` so
    the worker does not hang forever waiting for a WS-close event the
    asyncio loop never delivers (regression: the previous code skipped
    ``stop_event.set()`` and the worker hung after every shutdown
    command: see ``test_shutdown_command_exits_worker``).
    """

    # Reject browser origins (defense-in-depth; the worker should only
    # ever be connected to by the slim-core sidecar's WS client, never
    # by a browser tab).
    origin = getattr(websocket, "origin", None) or ""
    if origin and origin not in ("", "null"):
        log.warning("[WORKER] rejecting connection with origin=%r (browser origins not allowed)", origin)
        await websocket.close(code=1008)
        return

    if not await _authenticate(websocket):
        await _send_auth_failed_and_close(websocket)
        return

    peer = getattr(websocket, "remote_address", None) or ("?", 0)
    log.info("[WORKER] slim-core sidecar connected from %s:%s (prewarm_ran=%s)", peer[0], peer[1], prewarm_ran)

    import asyncio as _asyncio

    # Per-connection C3/C4 state (ADR-0025): partial sample buffers keyed
    # by request id, plus ids the sidecar aborted. Both die with the
    # connection; a reconnect starts clean rather than inheriting stale
    # buffers.
    samples: dict[int, _SamplesBuffer] = {}
    aborted: set[int] = set()
    # Per-connection C6 streaming sessions (ADR-0025): live PCM buffer +
    # planner cursor + assembler per open session id. Dies with the
    # connection like samples/aborted; a reconnect starts clean.
    streams: dict[int, StreamingSession] = {}
    # Serializes inference while keeping the frame loop responsive: an
    # abort arriving mid-inference must be processed NOW, not after the
    # model finishes (the handler previously awaited inference inline,
    # so an abort queued behind it always lost the race).
    inference_gate = _asyncio.Lock()
    in_flight: set = set()

    async def _complete(transcribe_fn, request_id: int | None) -> None:
        """Run blocking inference, then send the id-echoed result event.

        Shared tail for the file and samples paths (E7: one completion
        path). An id aborted while inference ran resolves to NOTHING on
        purpose — that silence IS the abort — but the mapping is
        discarded so a later reuse of the id starts clean. Never drops
        a non-aborted result.
        """
        try:
            result = await _asyncio.to_thread(transcribe_fn)
        except Exception as exc:  # noqa: BLE001, never drop a result event
            log.exception("[WORKER] transcription thread raised: %s", exc)
            result = {"text": "", "error": f"internal error: {exc}"}
        if request_id is not None and request_id in aborted:
            aborted.discard(request_id)
            log.info("[WORKER] dropping result for aborted request id=%s", request_id)
            return
        # ADR-0025 C1: echo the request id so the sidecar can
        # correlate a result with the request that asked for it.
        # The id is a SIBLING of `type` (like every other frame on
        # this hop), so the frozen `transcribe_offline_result`
        # `data` payload is untouched and a client that ignores
        # the id keeps working unchanged.
        out: dict = {"type": "transcribe_offline_result", "data": result}
        if request_id is not None:
            out["id"] = request_id
        with contextlib.suppress(Exception):
            await websocket.send(json.dumps(out))

    def _launch(transcribe_fn, request_id: int | None) -> None:
        """Start inference in the background, serialized by the gate.

        The frame loop keeps reading (so abort/shutdown land mid-work)
        while inference runs one at a time behind ``inference_gate`` —
        the shared engine is built for serialized requests, not
        concurrent ones.
        """

        async def _guarded() -> None:
            async with inference_gate:
                await _complete(transcribe_fn, request_id)

        task = _asyncio.ensure_future(_guarded())
        in_flight.add(task)
        task.add_done_callback(in_flight.discard)

    def _launch_stream(coro_fn) -> None:
        """Run an async streaming completion serialized by the inference gate.

        Sibling of :func:`_launch` for completions that send their own
        frames (partials / finalize results) instead of the shared
        ``transcribe_offline_result`` tail.
        """

        async def _guarded() -> None:
            async with inference_gate:
                await coro_fn()

        task = _asyncio.ensure_future(_guarded())
        in_flight.add(task)
        task.add_done_callback(in_flight.discard)

    async def _send_stream_result(request_id: int, text: str, error: str | None) -> None:
        """Structured streaming result (C1 id echo as sibling of type, never silence)."""
        with contextlib.suppress(Exception):
            await websocket.send(
                json.dumps(
                    {
                        "type": "streaming_session_result",
                        "id": request_id,
                        "data": {"text": text, "error": error},
                    }
                )
            )

    # Per-connection handles for the extracted offline / samples / abort
    # command handlers (they take the shared tails explicitly).
    handles = _CommandHandles(
        websocket=websocket,
        samples=samples,
        aborted=aborted,
        streams=streams,
        complete=_complete,
        launch=_launch,
    )

    try:
        async for raw in websocket:
            try:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                frame = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                log.warning("[WORKER] non-JSON frame from slim-core sidecar: ignoring")
                continue
            if not isinstance(frame, dict):
                continue
            cmd = frame.get("cmd") or frame.get("type")
            if cmd == "heartbeat":
                # Acknowledge heartbeats so the slim-core sidecar's
                # liveness probe sees a live worker (master plan §7.2).
                with contextlib.suppress(Exception):
                    await websocket.send(json.dumps({"type": "heartbeat_ack"}))
                continue
            if cmd == "shutdown":
                log.info("[WORKER] shutdown command received: exiting gracefully")
                with contextlib.suppress(Exception):
                    await websocket.send(json.dumps({"type": "shutdown_ack"}))
                # Mark the shutdown timer BEFORE stop_event.set() so
                # the duration covers the full shutdown sequence
                # (ack send + socket close + asyncio loop drain +
                # lock release). C-LOG-2.
                shutdown_timer.start()
                # Unblock run_worker_server's await stop_event.wait()
                # BEFORE closing the socket so the worker does not
                # hang waiting for a WS-close event the asyncio loop
                # never delivers.
                stop_event.set()
                # Trigger loop cancellation by closing the socket.
                with contextlib.suppress(Exception):
                    await websocket.close()
                # Let in-flight inference finish first (bounded model
                # work, same exposure the inline await always had) so a
                # shutdown mid-transcription does not orphan a thread
                # writing to a dead loop.
                if in_flight:
                    with contextlib.suppress(Exception):
                        await _asyncio.gather(*in_flight, return_exceptions=True)
                return
            if cmd == "transcribe_offline":
                handle_transcribe_offline(frame, handles)
                continue
            if cmd == "transcribe_samples":
                await handle_transcribe_samples(frame, handles)
                continue
            if cmd == "abort_request":
                await handle_abort_request(frame, handles)
                continue
            if cmd == "streaming_session_open":
                # ADR-0025 C6: additive open; ack carries the id echo.
                request_id = _valid_request_id(frame.get("id"))
                data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
                if request_id is None:
                    log.warning("[WORKER] streaming_session_open without a numeric id: ignoring")
                    continue
                try:
                    config = SessionConfig.from_dict(data.get("config"))
                except ValueError as exc:
                    await _send_stream_result(request_id, "", f"invalid streaming config: {exc}")
                    continue
                streams[request_id] = StreamingSession(request_id, config)
                log.info(
                    "[WORKER] streaming session opened id=%s (sr=%s, cycle=%s)",
                    request_id,
                    config.sample_rate,
                    config.cycle_id,
                )
                with contextlib.suppress(Exception):
                    await websocket.send(
                        json.dumps({"type": "streaming_session_opened", "id": request_id, "data": {"opened": True}})
                    )
                continue
            if cmd == "streaming_session_push":
                # Append live PCM; when a window is due, transcribe it in a
                # thread (frame loop stays responsive) and push the slim
                # partial shape the renderer already consumes.
                request_id = _valid_request_id(frame.get("id"))
                data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
                if request_id is None:
                    log.warning("[WORKER] streaming_session_push without a numeric id: ignoring")
                    continue
                if request_id in aborted:
                    aborted.discard(request_id)
                    streams.pop(request_id, None)
                    await _send_stream_result(request_id, "", "request aborted")
                    continue
                session = streams.get(request_id)
                if session is None:
                    await _send_stream_result(request_id, "", "unknown streaming session")
                    continue
                chunk_error = session.append_chunk(data.get("index"), data.get("payload_b64"))
                if chunk_error is not None:
                    await _send_stream_result(request_id, "", chunk_error)
                    continue
                due = session.due_window()
                if due is None:
                    continue
                start_seconds, end_seconds, _horizon = due
                window_raw = session.window_bytes(start_seconds, end_seconds)

                def _run_window(
                    _raw: bytes = window_raw,
                    _sr: int = session.config.sample_rate,
                    _offset: float = start_seconds,
                    _lang: object = session.config.language,
                ) -> list:
                    return _facade.transcribe_window_words(
                        _raw, _sr, _offset, str(_lang) if _lang is not None else None
                    )

                async def _finish_window(
                    _session: StreamingSession = session,
                    _sid: int = request_id,
                    _end: float = end_seconds,
                ) -> None:
                    try:
                        words = await _asyncio.to_thread(_run_window)
                    except Exception as exc:  # noqa: BLE001, window errors must not kill the session
                        log.warning("[WORKER] streaming window failed id=%s: %s", _sid, exc)
                        return
                    live = streams.get(_sid)
                    if live is not _session:
                        return
                    try:
                        new_text, committed_words = _session.commit_window(words, _end)
                    except (TypeError, ValueError) as exc:
                        log.warning("[WORKER] streaming window words invalid id=%s: %s", _sid, exc)
                        return
                    if not new_text:
                        return
                    with contextlib.suppress(Exception):
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "transcription_partial",
                                    "id": _sid,
                                    "data": {
                                        "text": _session.committed_text,
                                        "cycle_id": _session.config.cycle_id,
                                        "is_final": False,
                                        "words": [_word_to_dict(w) for w in committed_words],
                                    },
                                }
                            )
                        )

                _launch_stream(_finish_window)
                continue
            if cmd == "streaming_session_finalize":
                # Tail merge (or whole-buffer batch when nothing committed),
                # then the final result plus session teardown.
                request_id = _valid_request_id(frame.get("id"))
                if request_id is None:
                    log.warning("[WORKER] streaming_session_finalize without a numeric id: ignoring")
                    continue
                if request_id in aborted:
                    aborted.discard(request_id)
                    streams.pop(request_id, None)
                    await _send_stream_result(request_id, "", "request aborted")
                    continue
                session = streams.pop(request_id, None)
                if session is None:
                    await _send_stream_result(request_id, "", "unknown streaming session")
                    continue
                mode, tail_offset, tail_raw = session.finalize_plan()
                full_raw = session.window_bytes(0.0, session.duration_seconds)

                def _run_final(
                    _mode: str = mode,
                    _tail: bytes = tail_raw,
                    _offset: float = tail_offset,
                    _full: bytes = full_raw,
                    _sr: int = session.config.sample_rate,
                    _lang: object = session.config.language,
                    _session: StreamingSession = session,
                    _sid: int = request_id,
                ) -> dict:
                    t0 = time.perf_counter()
                    language = str(_lang) if _lang is not None else None
                    if _mode == "batch":
                        from voice_typer.worker._transcribe import _ASR_SAMPLE_RATE, get_transcriber

                        out = get_transcriber().transcribe_array(to_16k_array(_full, _sr), _ASR_SAMPLE_RATE, language)
                        return {"text": str(out.get("text") or ""), "error": out.get("error")}
                    try:
                        tail_words = _facade.transcribe_window_words(_tail, _sr, _offset, language)
                        text = _session.commit_tail(tail_words)
                        result: dict = {"text": text, "error": None}
                    except Exception as exc:  # noqa: BLE001, tail merge falls back to batch
                        log.warning("[WORKER] streaming tail merge failed id=%s: %s", _sid, exc)
                        from voice_typer.worker._transcribe import _ASR_SAMPLE_RATE, get_transcriber

                        out = get_transcriber().transcribe_array(to_16k_array(_full, _sr), _ASR_SAMPLE_RATE, language)
                        result = {"text": str(out.get("text") or ""), "error": out.get("error")}
                    result["latency_ms"] = int((time.perf_counter() - t0) * 1000)
                    return result

                async def _finish_final(
                    _sid: int = request_id,
                ) -> None:
                    try:
                        final = await _asyncio.to_thread(_run_final)
                    except Exception as exc:  # noqa: BLE001, finalize always resolves to a result
                        log.warning("[WORKER] streaming finalize failed id=%s: %s", _sid, exc)
                        final = {"text": "", "error": f"finalize failed: {exc}"}
                    await _send_stream_result(_sid, str(final.get("text") or ""), final.get("error"))

                _launch_stream(_finish_final)
                continue
            # Unknown command.
            log.debug("[WORKER] unknown command %r", cmd)
            with contextlib.suppress(Exception):
                await websocket.send(
                    json.dumps(
                        {
                            "type": "error",
                            "data": {
                                "code": "unknown_command",
                                "message": f"unknown command: {cmd!r}",
                            },
                        }
                    )
                )
    except Exception:
        log.debug("[WORKER] connection handler exited with exception", exc_info=True)
