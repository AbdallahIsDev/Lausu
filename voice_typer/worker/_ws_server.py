"""Worker WebSocket server helpers."""

from __future__ import annotations

import contextlib
import json
import logging
import signal
import sys
import time
from types import FrameType
from typing import TYPE_CHECKING

from voice_typer.server._paths import LOOPBACK_HOST
from voice_typer.server.duration import format_duration
from voice_typer.server.ipc.protocol_version import MAX_WS_FRAME_BYTES, PROTOCOL_VERSION
from voice_typer.worker._auth import _authenticate, _send_auth_failed_and_close
from voice_typer.worker._parent_watch import start_parent_watch
from voice_typer.worker.streaming import (
    SessionConfig,
    StreamingSession,
    to_16k_array,
    transcribe_window_words,
)

if TYPE_CHECKING:
    import asyncio

log = logging.getLogger("voice_typer.worker")

# ADR-0020 §10: 1 MiB WS frame cap. Shared with the slim-core sidecar's
# outbound sender through a dependency-free module so the two transports
# cannot drift apart on the maximum envelope size.
_MAX_FRAME_BYTES = MAX_WS_FRAME_BYTES

# Protocol version: imported from the shared
# ``voice_typer.server.ipc.protocol_version`` module (single source of
# truth, kept in lockstep with the TCP/WS transports and the Rust/TS
# constants). The slim-core sidecar's WS client checks this on the
# ``worker_started`` line so a version-skewed worker is rejected at
# handshake time rather than failing on the first ``transcribe_offline``
# request.

# Stdout event name. Distinct from the slim-core sidecar's
# ``server_started`` (which the host already listens for) so the host's
# stdout parser can route the worker's bind info to the worker-spawn
# code path (not the sidecar-spawn code path). See master plan §7.3.
_WORKER_STARTED_EVENT = "worker_started"


# ─── Prewarm phase (master plan §6.2 P-1) ──────────────────────────────


def _fast_startup_enabled() -> bool:
    """Read the ``fast_startup`` config toggle (Settings → General).

    The toggle is the user's start/stop switch for prewarm: when
    disabled, the worker skips its warm phase entirely. Read from the
    config file directly, the worker is a separate process spawned
    by the host, so there is no live ``app.config`` instance to
    consult. Defaults to ENABLED on any read failure (the historical
    default; a config hiccup must not silently stop warming).
    """
    try:
        from voice_typer.server.config import Config

        return bool(getattr(Config.load(), "fast_startup", True))
    except Exception:
        log.debug("[WORKER] fast_startup config read failed: defaulting to enabled", exc_info=True)
        return True


def _run_prewarm_phase() -> float:
    """Run the prewarm phase ONCE at worker startup.

    Calls :func:`voice_typer.server.prewarm.warm_imports_for_worker`,
    which pages the runtime-pack libraries' files into the OS standby
    cache (``onnxruntime`` + ``ctranslate2`` + ``numpy`` + ``scipy`` +
    ``faster_whisper``) WITHOUT importing them. The worker still has
    to execute each library's code once, in its own process, that is
    unavoidable, but the cold-disk read is paid here, in the
    background, BEFORE the first transcription request.

    Skips warming entirely when the ``fast_startup`` config toggle is
    disabled (the user's start/stop control, RESTORED 2026-08-14,
    see plan §6.3 addendum). Either way, the warm-run timing is
    persisted via :func:`write_prewarm_status_file` so the About-page
    Cache Status card can show "last run + seconds".

    Returns the elapsed wall-clock seconds (used for the
    ``[STARTUP]`` log line's space-separated ``<duration>`` suffix per C-LOG-2;
    ``0.0`` when prewarm was skipped).
    """
    from datetime import datetime

    from voice_typer.server.prewarm.status import write_prewarm_status_file

    t0 = time.perf_counter()
    if not _fast_startup_enabled():
        log.info("[STARTUP] worker prewarm phase SKIPPED: fast_startup disabled in config")
        write_prewarm_status_file(last_run=None, elapsed_s=0.0)
        return 0.0
    try:
        from voice_typer.server.prewarm import warm_imports_for_worker

        warm_imports_for_worker()
    except Exception:
        # Prewarm is best-effort: a failure here MUST NOT crash the
        # worker (the cold cache only costs latency, never correctness).
        log.debug("[WORKER] prewarm phase failed: continuing with cold cache", exc_info=True)
    elapsed = time.perf_counter() - t0
    write_prewarm_status_file(
        last_run=datetime.now().isoformat(timespec="seconds"),
        elapsed_s=round(elapsed, 1),
    )
    log.info("[STARTUP] worker prewarm phase complete%s", format_duration(elapsed))
    return elapsed


# ─── Stdout protocol ──────────────────────────────────────────────────


def _force_line_buffered_stdout() -> None:
    """Force stdout to line buffering (ADR-0020 §1 Phase-0 blocker).

    When the Tauri host pipes the worker's stdout, CPython switches to
    block buffering, so the ``worker_started`` JSON is held in the
    buffer and the host hangs forever waiting. ``reconfigure`` flips
    the stream back to line buffering so each ``\\n`` flushes.

    Mirrors :func:`voice_typer.server.sidecar_ws._force_line_buffered_stdout`.
    """
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        with contextlib.suppress(Exception):
            sys.stdout = open(  # noqa: SIM115 - intentional reopen
                sys.stdout.fileno(),
                "w",
                buffering=1,
                encoding="utf-8",
                closefd=False,
            )


def _emit_worker_started(port: int, protocol: int = PROTOCOL_VERSION) -> None:
    """Write the ONE structured stdout line the host is parsing for.

    Per master plan §7.3, this is the ONLY thing that ever goes to
    stdout from the worker. Every other log goes to stderr / the
    rotating file log. The host blocks reading stdout until it parses
    this JSON, then opens a WS client to ``ws://127.0.0.1:<port>``.

    The ``protocol`` field lets the host detect version skew at
    handshake time (mirrors :func:`sidecar_ws._emit_server_started`).
    """
    print(
        json.dumps({"event": _WORKER_STARTED_EVENT, "port": int(port), "protocol": int(protocol)}),
        flush=True,
    )


# ─── Shutdown timer (C-LOG-2 duration suffix on the SHUTDOWN log line) ─


class _ShutdownTimer:
    """Tracks the wall-clock start time of graceful shutdown.

    Used to compute the space-separated ``<duration>`` suffix on the
    ``[SHUTDOWN] worker shutdown complete <duration>`` log line per
    C-LOG-2. The timer is started ONCE, the first call to
    :meth:`start` wins, so concurrent shutdown triggers (SIGTERM +
    shutdown command arriving simultaneously) do not reset the
    measurement.

    The measurement source is :func:`time.perf_counter` (monotonic)
    per C-LOG-2.
    """

    __slots__ = ("_t0",)

    def __init__(self) -> None:
        self._t0: float | None = None

    def start(self) -> None:
        """Mark the start of graceful shutdown (idempotent).

        Safe to call from a signal handler context (POSIX
        ``add_signal_handler`` runs in the loop thread, not interrupt
        context) and from inside an async connection handler. The
        first call wins; subsequent calls are no-ops.
        """
        if self._t0 is None:
            self._t0 = time.perf_counter()

    def elapsed(self) -> float:
        """Return seconds since :meth:`start` was first called.

        Returns ``0.0`` if :meth:`start` was never called (e.g. the
        worker exited before any shutdown trigger fired, covered by
        the ``max(0.0, ...)`` clamp inside :func:`format_duration`).
        """
        if self._t0 is None:
            return 0.0
        return time.perf_counter() - self._t0


# ─── SIGTERM handler (POSIX) ───────────────────────────────────────────


def _install_sigterm_handler(stop_event: asyncio.Event, shutdown_timer: _ShutdownTimer) -> None:
    """Install a SIGTERM handler that initiates graceful shutdown (POSIX only).

    Uses :meth:`asyncio.AbstractEventLoop.add_signal_handler` (the
    asyncio-idiomatic way) so the handler runs INSIDE the event loop
    thread, NOT in the signal-handler interrupt context. This matters
    because ``asyncio.Event.set()`` is not safe to call from a signal
    handler directly (it doesn't acquire the loop's internal lock).

    On SIGTERM: ``shutdown_timer.start()`` captures the shutdown
    wall-clock t0, then ``stop_event.set()`` unblocks
    :func:`run_worker_server`'s ``await stop_event.wait()`` so the
    worker exits cleanly and ``run()``'s ``finally`` block runs
    ``lock_handle.release()`` + emits the SHUTDOWN log line with the
    measured duration.

    On Windows the Tauri host uses ``taskkill`` (no SIGTERM equivalent);
    the asyncio loop is cancelled via the ``shutdown`` command instead.
    The handler is best-effort: if the OS does not deliver the signal
    (e.g. the process is in a C extension call), the host's
    kill-children backstop still terminates the process.
    """
    import asyncio

    if not hasattr(signal, "SIGTERM"):
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop. Called outside ``asyncio.run``. Fall back
        # to the signal-handler-in-interrupt-context path. This is
        # safe-ish because ``stop_event.set()`` is the only thing the
        # handler does, and on CPython ``asyncio.Event.set()`` is
        # implemented as ``self._value = True`` + waking waiters via
        # ``self._loop.call_soon(...)``. The ``call_soon`` IS thread-
        # safe (it acquires the loop's internal lock), so calling it
        # from a signal handler is technically OK but produces a
        # DeprecationWarning on Python 3.10+. The fallback is here
        # for defensive reasons (e.g. a future test that calls
        # ``run()`` outside ``asyncio.run``); the production path
        # always uses the loop-aware branch above.
        def _on_sigterm_fallback(_signum: int, _frame: FrameType | None) -> None:
            log.info("[WORKER] SIGTERM received: initiating graceful shutdown (fallback)")
            shutdown_timer.start()
            with contextlib.suppress(Exception):
                stop_event.set()

        with contextlib.suppress(ValueError, OSError):
            signal.signal(signal.SIGTERM, _on_sigterm_fallback)
        return

    def _on_sigterm() -> None:
        log.info("[WORKER] SIGTERM received: initiating graceful shutdown")
        shutdown_timer.start()
        stop_event.set()

    with contextlib.suppress(NotImplementedError, RuntimeError):
        # ``add_signal_handler`` raises NotImplementedError on Windows
        # (ProactorEventLoop does not support it), the
        # shutdown-command path is the worker's shutdown mechanism
        # there.
        loop.add_signal_handler(signal.SIGTERM, _on_sigterm)


# ─── Connection handler ───────────────────────────────────────────────


# ─── In-memory sample reassembly (ADR-0025 C3) ──────────────────────────


# Bound the per-request reassembly state: 64 chunks × ~720 KiB raw keeps
# one request under ~46 MiB before inference (a 30 s window needs ~3).
_SAMPLES_MAX_CHUNKS = 64
# Base64 of one chunk must itself respect the frame cap (ADR-0020 §10).
_SAMPLES_MAX_PAYLOAD_B64 = 1_400_000
_SAMPLES_MIN_RATE = 1000
_SAMPLES_MAX_RATE = 192000


def _valid_request_id(value: object) -> int | None:
    """Numeric request id, or ``None`` (E8; JSON true/false never pass)."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


class _SamplesBuffer:
    """Accumulates one ``transcribe_samples`` request's base64 chunks.

    Pure reassembly (no IO, no inference): ``add_chunk`` validates and
    stores, ``audio_bytes`` returns the concatenated raw float32 PCM once
    every declared chunk has arrived, regardless of arrival order.
    """

    def __init__(self, total: int, sample_rate: int, language: object) -> None:
        self.total = total
        self.sample_rate = sample_rate
        self.language = str(language) if language is not None else None
        self._chunks: dict[int, bytes] = {}

    def add_chunk(self, index: int, payload_b64: str) -> str | None:
        """Store one chunk; return an error string, or ``None`` on success."""
        if not isinstance(index, int) or isinstance(index, bool):
            return "chunk index must be an integer"
        if not 0 <= index < self.total:
            return f"chunk index {index} out of range for total={self.total}"
        if index in self._chunks:
            return f"duplicate chunk index {index}"
        if not isinstance(payload_b64, str) or len(payload_b64) > _SAMPLES_MAX_PAYLOAD_B64:
            return "chunk payload too large"
        try:
            import base64

            raw = base64.b64decode(payload_b64, validate=True)
        except Exception:
            return "chunk payload is not valid base64"
        self._chunks[index] = raw
        return None

    def is_complete(self) -> bool:
        """True once every declared chunk has arrived (any order)."""
        return len(self._chunks) == self.total

    def audio_bytes(self) -> bytes:
        """Concatenated raw float32 PCM in index order (call when complete)."""
        return b"".join(self._chunks[i] for i in range(self.total))


def _valid_samples_header(data: dict) -> tuple[int, int, int, object, str | None]:
    """Validate a ``transcribe_samples`` chunk header.

    Returns ``(total, index, sample_rate, language, error)``; ``error``
    is ``None`` when the header is usable.
    """
    total = data.get("total")
    index = data.get("index")
    sample_rate = data.get("sample_rate")
    if isinstance(total, bool) or not isinstance(total, int) or not 1 <= total <= _SAMPLES_MAX_CHUNKS:
        return (0, 0, 0, None, f"total must be an integer in 1..{_SAMPLES_MAX_CHUNKS}")
    if isinstance(index, bool) or not isinstance(index, int):
        return (0, 0, 0, None, "index must be an integer")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int):
        return (0, 0, 0, None, "sample_rate must be an integer")
    if not _SAMPLES_MIN_RATE <= sample_rate <= _SAMPLES_MAX_RATE:
        return (0, 0, 0, None, f"sample_rate {sample_rate} out of range")
    return (total, index, sample_rate, data.get("language"), None)


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

    def _word_to_dict(word: object) -> dict:
        """Serialize a window word (local Word or engine-shaped mapping/object)."""
        if isinstance(word, dict):
            return {
                "word": word.get("word"),
                "start_seconds": word.get("start_seconds"),
                "end_seconds": word.get("end_seconds"),
            }
        return {
            "word": getattr(word, "word", None),
            "start_seconds": getattr(word, "start_seconds", None),
            "end_seconds": getattr(word, "end_seconds", None),
        }

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
                # Master plan §7.4: real offline ASR in the worker.
                # The slim-core sidecar forwards ``{audio_path,
                # sample_rate, language}``; the worker transcribes and
                # pushes the result back via the
                # ``transcribe_offline_result`` event. The inference is
                # blocking C-level work, run it in a thread so
                # heartbeats + shutdown stay responsive mid-inference.
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

                # Bind the loop variables into the closure's defaults so
                # the thread function does not capture the loop variables
                # by reference (B023, the connection handler's frame
                # loop mutates them on each iteration).
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

                _launch(_run, _valid_request_id(frame.get("id")))
                continue
            if cmd == "transcribe_samples":
                # ADR-0025 C3: in-memory float32 PCM in base64 chunks.
                # Each chunk carries (id, index, total) so reassembly
                # needs no ordering assumption; the final chunk's
                # arrival triggers inference in a thread (heartbeats +
                # shutdown stay responsive, same as the file path).
                # Malformed input resolves to a structured error RESULT
                # (with the id) rather than silence, so a client Future
                # never hangs on a corrupt chunk.
                request_id = _valid_request_id(frame.get("id"))
                data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
                if request_id is None:
                    log.warning("[WORKER] transcribe_samples without a numeric id: ignoring")
                    continue
                if request_id in aborted:
                    aborted.discard(request_id)
                    samples.pop(request_id, None)
                    await _complete(lambda: {"text": "", "error": "request aborted"}, request_id)
                    continue
                total, index, sample_rate, language, header_error = _valid_samples_header(data)
                if header_error is not None:
                    await _complete(lambda _e=header_error: {"text": "", "error": _e}, request_id)
                    samples.pop(request_id, None)
                    continue
                buffer = samples.get(request_id)
                if buffer is None:
                    buffer = _SamplesBuffer(total, sample_rate, language)
                    samples[request_id] = buffer
                elif buffer.total != total:
                    samples.pop(request_id, None)
                    await _complete(lambda: {"text": "", "error": "chunk total mismatch"}, request_id)
                    continue
                chunk_error = buffer.add_chunk(index, data.get("payload_b64"))
                if chunk_error is not None:
                    samples.pop(request_id, None)
                    await _complete(lambda _e=chunk_error: {"text": "", "error": _e}, request_id)
                    continue
                if not buffer.is_complete():
                    continue
                raw = buffer.audio_bytes()
                samples.pop(request_id, None)
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

                _launch(_run_samples, request_id)
                continue
            if cmd == "abort_request":
                # ADR-0025 C4: best-effort cooperative abort. Signals the
                # loaded backend (never builds one), drops any partial
                # sample buffer, and marks the id so a result that is
                # already past the point of no return is discarded
                # instead of sent. Idempotent: unknown ids still ack.
                request_id = _valid_request_id(frame.get("id"))
                if request_id is None:
                    log.warning("[WORKER] abort_request without a numeric id: ignoring")
                    continue
                aborted.add(request_id)
                samples.pop(request_id, None)
                # C6: an abort also tears down live streaming state for the id.
                streams.pop(request_id, None)
                from voice_typer.worker._transcribe import get_transcriber

                signalled = get_transcriber().request_abort()
                log.info("[WORKER] abort_request id=%s (backend signalled=%s)", request_id, signalled)
                with contextlib.suppress(Exception):
                    await websocket.send(json.dumps({"type": "abort_ack", "id": request_id, "data": {"aborted": True}}))
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
                    return transcribe_window_words(_raw, _sr, _offset, str(_lang) if _lang is not None else None)

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
                        tail_words = transcribe_window_words(_tail, _sr, _offset, language)
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


# ─── Worker run loop ──────────────────────────────────────────────────


async def run_worker_server(  # noqa: ANN001 - websockets type is imported lazily
    *,
    prewarm_elapsed: float,
    prewarm_ran: bool,
    stop_event: asyncio.Event,
    shutdown_timer: _ShutdownTimer,
) -> bool:
    """Bind the WS server on an ephemeral port and run until ``stop_event`` is set.

    Returns ``True`` on clean shutdown (``stop_event`` was set by the
    shutdown command / SIGTERM / KeyboardInterrupt), ``False`` if the
    WS server failed to bind any socket.

    Sequence (master plan §7.3):

    1. Install the SIGTERM handler (POSIX) + the parent-watch (both
       set ``stop_event``: signal vs. dead spawning host).
    2. Bind ``127.0.0.1:0`` (loopback-only, ADR-0020 §1) via
       ``websockets.asyncio.server.serve`` with the 1 MiB frame cap.
    3. Print ``{"event":"worker_started","port":N,"protocol":P}`` to stdout.
    4. Block on ``await stop_event.wait()`` until graceful shutdown.
    5. ``async with serve()`` exits cleanly (websockets' default
       close_timeout drains in-flight handlers).

    Mirrors :func:`voice_typer.server.sidecar_ws.run`'s shape so the
    two entry points read identically.
    """

    from websockets.asyncio.server import serve

    _install_sigterm_handler(stop_event, shutdown_timer)

    # Orphan self-exit: a hard-killed host never reaps us, and the
    # live orphan would hold the single-instance lock forever (every
    # later spawn fails as a duplicate). When the host is gone the
    # watcher routes through the same graceful path as SIGTERM.
    import asyncio as _asyncio

    def _on_parent_gone() -> None:
        # INFO, not WARN: routine on every clean quit (see _parent_watch).
        log.info("[WORKER] parent process gone: initiating graceful shutdown")
        shutdown_timer.start()
        stop_event.set()

    _parent_loop = _asyncio.get_running_loop()
    start_parent_watch(on_gone=lambda: _parent_loop.call_soon_threadsafe(_on_parent_gone))

    # bind on 127.0.0.1:0 → OS assigns an ephemeral port. max_size
    # enforces the 1 MiB frame cap (ADR-0020 §10). The handler is a
    # closure so it can carry the ``prewarm_ran`` flag, ``stop_event``,
    # and ``shutdown_timer`` without globals.
    #
    # NOTE: ``websockets.asyncio.server.serve`` does NOT accept a
    # ``max_connections`` kwarg (unlike the legacy
    # ``websockets.server.serve``), and the worker deliberately ships
    # NO connection cap. Access to this server rests on three real
    # controls: the auth gate inside ``_handle_connection`` (a
    # per-launch bearer token the host generates via
    # ``secrets.token_bytes`` on every worker spawn), the loopback-only
    # bind (``LOOPBACK_HOST``), and the OS-assigned ephemeral port,
    # which is discoverable only through the worker's stdout
    # ``worker_started`` line. The worker should only ever have ONE
    # authenticated client (the slim-core sidecar); there is NO
    # connection tracking here and the auth step does NOT reject a
    # same-token second client, single-client exclusivity holds in
    # practice because the slim-core sidecar's respawn scheduler
    # guarantees at most one sidecar is alive at a time.
    async def _handler(websocket) -> None:  # noqa: ANN001
        await _handle_connection(
            websocket,
            prewarm_ran=prewarm_ran,
            stop_event=stop_event,
            shutdown_timer=shutdown_timer,
        )

    async with serve(
        _handler,
        LOOPBACK_HOST,
        0,
        max_size=_MAX_FRAME_BYTES,
    ) as ws_server:
        socks = ws_server.sockets
        first_sock = next(iter(socks), None)
        if first_sock is None:
            log.error("[WORKER] no sockets bound: aborting")
            return False
        port = first_sock.getsockname()[1]
        _emit_worker_started(port, PROTOCOL_VERSION)
        log.info(
            "[WORKER] listening on %s:%d (prewarm ran in%s)",
            LOOPBACK_HOST,
            port,
            format_duration(prewarm_elapsed),
        )

        # Run until SIGTERM (stop_event) or the asyncio loop is
        # cancelled by the shutdown command (which calls stop_event.set()).
        await stop_event.wait()

    return True
