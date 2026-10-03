"""Slim-core sidecar WS client to the runtime-pack worker (ADR-0024 Step 3).

One purpose only: own the worker hop (connect, auth, forward, route,
heartbeat, reconnect). Transcribe dispatch policy lives in
``voice_typer/server/ipc/lifecycle.py`` (Step 4 owns that body).
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import contextlib
import json
import logging
import os
import queue
import threading
import time
from typing import Any

from voice_typer.server import event_bus
from voice_typer.server._paths import IPC_TOKEN_ENV_VAR, LOOPBACK_HOST
from voice_typer.server.duration import format_duration
from voice_typer.server.ipc.protocol_version import MAX_WS_FRAME_BYTES

log = logging.getLogger("voice_typer.server.worker_client")

# 1 MiB frame cap (ADR-0020 §10), shared with the worker's WS server via
# a dependency-free module. Imported rather than redefined: the slim-core
# build must not depend on the ``voice_typer.worker`` package (Step 7
# slims it out), so the constant lives under ``voice_typer.server.ipc``.
_MAX_FRAME_BYTES = MAX_WS_FRAME_BYTES

_HEARTBEAT_SECONDS = 15.0
_MAX_MISSED_HEARTBEATS = 3
_BACKOFF_FIRST_SECONDS = 0.5
_BACKOFF_CAP_SECONDS = 30.0
_OUTBOUND_QUEUE_MAX = 64


def build_auth_frame(token: str) -> str:
    """First-frame auth envelope the worker's ``_authenticate`` expects."""
    # C-WS-2: str, never bytes, so the frame leaves as a TEXT opcode.
    return json.dumps({"type": "auth", "token": token})


def build_transcribe_frame(audio_path: str, sample_rate: int | None, language: str | None, request_id: int) -> str:
    """Forward envelope for one offline transcription (event_bus §7.4 shape)."""
    # C-WS-2: numeric top-level id for response correlation; the worker
    # echoes it (ADR-0025 C1) and results without one fall back to type
    # routing so older workers keep working.
    return json.dumps(
        {
            "cmd": "transcribe_offline",
            "id": int(request_id),
            "data": {"audio_path": audio_path, "sample_rate": sample_rate, "language": language},
        }
    )


def build_heartbeat_frame() -> str:
    """Liveness ping; the worker answers ``heartbeat_ack`` (plan §7.2)."""
    return json.dumps({"type": "heartbeat"})


# ADR-0025 C3: raw PCM bytes per chunk. 720 KiB raw encodes to ~960 KiB
# of base64, which plus the small JSON envelope stays under the 1 MiB
# frame cap on both hops. (The ADR text says "1 MiB raw", but 1 MiB raw
# would encode to ~1.4 MiB and breach the cap — the cap wins, the
# intent (bounded frames) is preserved.)
_SAMPLES_CHUNK_RAW_BYTES = 720 * 1024


def chunk_samples(audio_f32: bytes, sample_rate: int, language: str | None, request_id: int) -> list[str]:
    """Split raw float32 PCM into ``transcribe_samples`` chunk frames.

    Pure function (no IO): every frame carries ``(id, index, total)``
    so the worker reassembles without ordering assumptions. Empty audio
    yields exactly one (empty-payload) chunk — silence is data, not an
    error. Every returned frame is ``str`` (C-WS-2, TEXT opcode).
    """
    total = max(1, (len(audio_f32) + _SAMPLES_CHUNK_RAW_BYTES - 1) // _SAMPLES_CHUNK_RAW_BYTES)
    frames = []
    for index in range(total):
        raw = audio_f32[index * _SAMPLES_CHUNK_RAW_BYTES : (index + 1) * _SAMPLES_CHUNK_RAW_BYTES]
        frames.append(
            json.dumps(
                {
                    "cmd": "transcribe_samples",
                    "id": int(request_id),
                    "data": {
                        "index": index,
                        "total": total,
                        "sample_rate": int(sample_rate),
                        "language": language,
                        "payload_b64": base64.b64encode(raw).decode("ascii"),
                    },
                }
            )
        )
    return frames


def build_abort_frame(request_id: int) -> str:
    """Best-effort cooperative abort for one in-flight request (C4)."""
    return json.dumps({"cmd": "abort_request", "id": int(request_id), "data": {}})


def build_streaming_frame(cmd: str, request_id: int, data: dict) -> str:
    """One streaming-session command frame (C6: open/push/finalize)."""
    return json.dumps({"cmd": str(cmd), "id": int(request_id), "data": dict(data)})


def parse_incoming(raw: object) -> dict | None:
    """Decode one inbound frame; ``None`` means ignorable (never raises)."""
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        frame = json.loads(raw)  # type: ignore[arg-type]
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return None
    return frame if isinstance(frame, dict) else None


def route_frame(frame: dict, publish: Any, on_result: Any = None) -> str:
    """Route one decoded frame; returns the action taken for liveness.

    ADR-0025 C1: when ``on_result`` is supplied and the worker echoed a
    numeric request ``id``, the callback receives ``(request_id, result)``
    so a future request/reply bridge can correlate. The event-bus publish
    is UNCHANGED in every case, so existing consumers (and the frozen
    ``transcribe_offline_result`` shape) are unaffected either way.
    """
    ftype = frame.get("type") or frame.get("cmd")
    if ftype == "transcribe_offline_result":
        data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
        result = {"text": str(data.get("text") or ""), "latency_ms": int(data.get("latency_ms") or 0)}
        # ADR-0025 C4: optional worker device description. Copied only
        # when present as a string, so the frozen shape is unchanged for
        # results that do not carry it (older workers keep working).
        device_info = data.get("device_info")
        if isinstance(device_info, str) and device_info:
            result["device_info"] = device_info
        if on_result is not None:
            request_id = frame.get("id")
            if isinstance(request_id, int) and not isinstance(request_id, bool):
                try:
                    on_result(request_id, result)
                except Exception:  # noqa: BLE001, a bad resolver must not drop the result
                    log.debug("[WORKER] result resolver failed for id=%s", request_id, exc_info=True)
        publish({"type": "transcribe_offline_result", "data": result})
        return "result"
    if ftype == "heartbeat_ack":
        return "heartbeat_ack"
    if ftype == "abort_ack":
        return "abort_ack"
    if ftype == "streaming_session_opened":
        # Resolve the opener's Future; nothing to publish (the renderer
        # only cares about partials and the pipeline consumes finalize).
        if on_result is not None:
            request_id = frame.get("id")
            if isinstance(request_id, int) and not isinstance(request_id, bool):
                try:
                    on_result(request_id, {"opened": True})
                except Exception:  # noqa: BLE001, same never-drop contract
                    log.debug("[WORKER] streaming open resolver failed for id=%s", request_id, exc_info=True)
        return "streaming_opened"
    if ftype == "streaming_session_result":
        # Final text for one streaming session: resolve the finalize
        # Future. NOT published — live partials already went out and the
        # pipeline consumes the final text synchronously.
        if on_result is not None:
            request_id = frame.get("id")
            if isinstance(request_id, int) and not isinstance(request_id, bool):
                try:
                    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
                    on_result(
                        request_id,
                        {"text": str(data.get("text") or ""), "error": data.get("error")},
                    )
                except Exception:  # noqa: BLE001, same never-drop contract
                    log.debug("[WORKER] streaming result resolver failed for id=%s", request_id, exc_info=True)
        return "streaming_result"
    if ftype == "transcription_partial":
        # Live preview: straight to the event bus in the worker's shape
        # (text + cycle_id, plus additive is_final/words the renderer
        # tolerates). Published by the slim side, not the worker.
        data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
        publish({"type": "transcription_partial", "data": dict(data)})
        return "partial"
    if ftype == "error":
        log.warning("[WORKER] worker error frame: %s", frame.get("data"))
        return "error"
    log.debug("[WORKER] unknown frame type %r: ignoring", ftype)
    return "ignored"


def backoff_delay(attempt: int) -> float:
    """Exponential reconnect backoff, capped (attempt counts failed tries)."""
    return min(_BACKOFF_FIRST_SECONDS * (2.0 ** max(0, attempt)), _BACKOFF_CAP_SECONDS)


def port_from_worker_started(payload: object) -> int | None:
    """Extract the worker port from a Step-2 ``worker_started`` payload."""
    # E8: None is the only no-value; invalid ports degrade to it.
    if not isinstance(payload, dict):
        return None
    port = payload.get("port")
    if isinstance(port, bool) or not isinstance(port, int):
        return None
    return port if 1 <= port <= 65535 else None


class _WorkerUnresponsiveError(Exception):
    """Heartbeat budget exhausted; the session must reconnect."""


class WorkerAbortedError(Exception):
    """A pending worker request was aborted via ``abort_all_outstanding``."""


class WorkerClient:
    """Long-lived WS client to the worker (§7.3); generation-stamped (C-WS-3)."""

    def __init__(self, publish: Any | None = None) -> None:
        self._publish = publish if publish is not None else event_bus.publish
        self._lock = threading.Lock()
        self._port: int | None = None
        self._generation = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._outbound: queue.Queue[str] = queue.Queue(maxsize=_OUTBOUND_QUEUE_MAX)
        self._request_seq = 0
        self._last_request_t0: float | None = None
        # Wake-up for the session loop (ADR-0025 C4): the loop blocks in
        # recv() for up to a heartbeat interval, so a queued forward
        # (and especially an abort) would otherwise wait that long on a
        # quiet connection. Send paths ping the running loop through
        # this pair; both are owned by the live session only.
        self._session_loop: asyncio.AbstractEventLoop | None = None
        self._session_wake: asyncio.Event | None = None
        # ADR-0025 C2: id → Future bridge resolved by the C1 id router.
        # Guarded by the same lock; entries are popped on resolve,
        # cancel, or timeout, so the map stays bounded by in-flight.
        self._resolvers: dict[int, concurrent.futures.Future[dict]] = {}

    @property
    def port(self) -> int | None:
        """Current worker port; ``None`` means unknown (E8)."""
        with self._lock:
            return self._port

    def update_from_worker_started(self, payload: object) -> bool:
        """Consume the Step-2 relay; invalid payloads are ignored, never stored."""
        port = port_from_worker_started(payload)
        if port is None:
            log.debug("[WORKER] worker_started relay without a valid port: ignoring")
            return False
        self.set_port(port)
        return True

    def set_port(self, port: int) -> None:
        """Point the client at a worker; bumps the generation (C-WS-3)."""
        with self._lock:
            self._port = int(port)
            self._generation += 1
            generation = self._generation
            self._stop_event.clear()
            # Always start this generation's thread. A previous
            # generation's thread may still be alive inside its reconnect
            # backoff; it exits on its next `_is_current` check because
            # the generation was just bumped. Treating "still alive" as
            # "already handled" therefore left NOBODY running against the
            # new port, which is exactly what a host run caught: after a
            # respawn relay the client never reconnected. The superseded
            # thread is a daemon (RACE-008) and exits promptly, so this
            # cannot block process exit.
            self._thread = threading.Thread(target=self._run, args=(generation,), name="worker-client", daemon=True)
            self._thread.start()

    def close(self) -> None:
        """Stop reconnecting; the bumped generation orphans stale loops (C-WS-3)."""
        with self._lock:
            self._generation += 1
            self._port = None
        self._stop_event.set()

    def _next_id(self) -> int:
        """Monotonic request id (caller must hold no lock; takes it)."""
        with self._lock:
            self._request_seq += 1
            return self._request_seq

    def _notify_outbound(self) -> None:
        """Wake the session loop so queued frames drain without waiting.

        Called (from any thread) after a successful enqueue. Best-effort:
        no live session means the next loop iteration drains anyway.
        """
        with self._lock:
            loop = self._session_loop
            wake = self._session_wake
        if loop is None or wake is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(wake.set)

    def send_transcribe(
        self, audio_path: str, sample_rate: int | None = None, language: str | None = None
    ) -> int | None:
        """Queue one forward; ``None`` when there is nowhere to send it (E8)."""
        request_id = self._next_id()
        with self._lock:
            port = self._port
        if port is None:
            return None
        try:
            self._outbound.put_nowait(build_transcribe_frame(audio_path, sample_rate, language, request_id))
        except queue.Full:
            log.warning("[WORKER] outbound queue full: dropping transcribe request")
            return None
        self._last_request_t0 = time.perf_counter()
        self._notify_outbound()
        return request_id

    def request_transcribe(
        self,
        audio_path: str,
        sample_rate: int | None = None,
        language: str | None = None,
        timeout: float | None = None,
    ) -> concurrent.futures.Future[dict] | None:
        """Send one forward and return a Future resolved by id (ADR-0025 C2).

        The Future completes with the ``{"text", "latency_ms"}`` result
        dict when the worker echoes this request's ``id``. ``timeout``
        bounds the wait: on expiry the Future fails with ``TimeoutError``
        and the id mapping is dropped, so a late result falls back to
        the type-routed publish instead of resolving a dead waiter.
        ``Future.cancel()`` (or :meth:`cancel_request`) drops the mapping
        the same way. Returns ``None`` when there is nowhere to send it,
        mirroring :meth:`send_transcribe` (E8).
        """
        request_id = self.send_transcribe(audio_path, sample_rate, language)
        if request_id is None:
            return None
        return self._register_future(request_id, timeout)

    def cancel_request(self, request_id: int) -> bool:
        """Drop one pending id mapping; a late result still publishes by type."""
        with self._lock:
            future = self._resolvers.pop(int(request_id), None)
        if future is None:
            return False
        return future.cancel()

    def _register_future(self, request_id: int, timeout: float | None) -> concurrent.futures.Future[dict]:
        """Register a resolver Future for ``request_id`` (shared C2/C6 path)."""
        future: concurrent.futures.Future[dict] = concurrent.futures.Future()
        with self._lock:
            self._resolvers[request_id] = future
        if timeout is not None:
            timer = threading.Timer(timeout, self._expire_request, args=(request_id,))
            # Daemon (RACE-008): see request_transcribe.
            timer.daemon = True
            timer.start()
        return future

    def open_streaming_session(self, config: dict, timeout: float | None = 10.0) -> tuple[int, Any] | None:
        """Open a worker streaming session; Future resolves on opened-ack (C6).

        Returns ``(id, Future)`` or ``None`` when there is nowhere to
        send it. The caller registers the finalize waiter separately via
        :meth:`expect_streaming_result` once the session is open.
        """
        request_id = self._next_id()
        with self._lock:
            port = self._port
        if port is None:
            return None
        try:
            self._outbound.put_nowait(build_streaming_frame("streaming_session_open", request_id, {"config": config}))
        except queue.Full:
            log.warning("[WORKER] outbound queue full: dropping streaming open")
            return None
        self._notify_outbound()
        return (request_id, self._register_future(request_id, timeout))

    def expect_streaming_result(self, request_id: int, timeout: float | None = None) -> Any:
        """Register the finalize waiter for an open streaming session (C6)."""
        return self._register_future(int(request_id), timeout)

    def enqueue_frames(self, frames: list[str]) -> bool:
        """Queue prebuilt frames atomically; ``False`` sends nothing (E8)."""
        with self._lock:
            port = self._port
        if port is None:
            return False
        try:
            for frame in frames:
                self._outbound.put_nowait(frame)
        except queue.Full:
            log.warning("[WORKER] outbound queue full: dropping %d streaming frames", len(frames))
            return False
        self._notify_outbound()
        return True

    def send_abort(self, request_id: int) -> bool:
        """Ask the worker to cooperatively abort one request (C4).

        Best-effort: ``False`` when there is nowhere to send it (E8).
        Pair with :meth:`cancel_request` so the local Future does not
        wait on work the worker was told to drop.
        """
        with self._lock:
            port = self._port
        if port is None:
            return False
        try:
            self._outbound.put_nowait(build_abort_frame(request_id))
        except queue.Full:
            log.warning("[WORKER] outbound queue full: dropping abort request")
            return False
        self._notify_outbound()
        return True

    def abort_all_outstanding(self) -> int:
        """Abort every pending request; returns how many futures failed.

        Best-effort per id: each registered id gets a cooperative abort
        frame, and its Future fails with ``WorkerAbortedError`` so a
        blocked ``result()`` wakes promptly instead of timing out.
        """
        with self._lock:
            ids = [int(request_id) for request_id in self._resolvers]
        count = 0
        for request_id in ids:
            try:
                self.send_abort(request_id)
            except Exception:
                log.debug("[WORKER] abort_all: send_abort failed for id=%s", request_id, exc_info=True)
            with self._lock:
                future = self._resolvers.pop(request_id, None)
            if future is None or future.done():
                continue
            with contextlib.suppress(concurrent.futures.InvalidStateError):
                future.set_exception(WorkerAbortedError(f"worker request aborted (id={request_id})"))
            count += 1
        return count

    def request_samples(
        self,
        audio_f32: bytes,
        sample_rate: int,
        language: str | None = None,
        timeout: float | None = None,
    ) -> concurrent.futures.Future[dict] | None:
        """Send in-memory float32 PCM and return a Future (ADR-0025 C3).

        Same Future/timeout/cancel contract as :meth:`request_transcribe`;
        ``None`` when there is nowhere to send it. All chunks are queued
        atomically: if the outbound queue cannot fit the whole request,
        nothing is sent and ``None`` is returned (a half-sent request
        would hang its Future forever).
        """
        request_id = self._next_id()
        with self._lock:
            port = self._port
        if port is None:
            return None
        frames = chunk_samples(bytes(audio_f32), int(sample_rate), language, request_id)
        try:
            for frame in frames:
                self._outbound.put_nowait(frame)
        except queue.Full:
            log.warning("[WORKER] outbound queue full: dropping samples request")
            return None
        self._notify_outbound()
        return self._register_future(request_id, timeout)

    def _expire_request(self, request_id: int) -> None:
        """Fail one pending Future with ``TimeoutError`` (timer callback)."""
        with self._lock:
            future = self._resolvers.pop(int(request_id), None)
        if future is None or future.done():
            return
        with contextlib.suppress(concurrent.futures.InvalidStateError):
            future.set_exception(TimeoutError(f"worker transcribe timed out (id={request_id})"))

    def _take_result(self, request_id: int, result: dict) -> bool:
        """C1 router callback: resolve the C2 Future for ``request_id``.

        Returns ``True`` when a live waiter consumed the result. ``False``
        (unknown, cancelled, or timed-out id) tells the caller to keep
        the type-routed publish, so a result is never dropped. Never
        raises: a resolver runs on the client's IO thread and must not
        break the session loop.
        """
        try:
            with self._lock:
                future = self._resolvers.pop(int(request_id), None)
            if future is None or future.done():
                return False
            try:
                future.set_result(result)
            except concurrent.futures.InvalidStateError:
                return False
            return True
        except Exception:
            log.debug("[WORKER] result handoff failed for id=%s", request_id, exc_info=True)
            return False

    def _run(self, generation: int) -> None:
        """Thread entry: own an asyncio loop for this generation's lifetime."""
        try:
            asyncio.run(self._connect_loop(generation))
        except Exception:
            log.debug("[WORKER] client loop exited", exc_info=True)

    def _current_url(self) -> str | None:
        with self._lock:
            return f"ws://{LOOPBACK_HOST}:{self._port}" if self._port is not None else None

    def _is_current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation and not self._stop_event.is_set()

    async def _connect_loop(self, generation: int) -> None:
        """Reconnect with backoff until superseded (generation) or closed."""
        attempt = 0
        while self._is_current(generation):
            url = self._current_url()
            if url is None:
                return
            t0 = time.perf_counter()
            try:
                # websockets imported lazily: the module stays importable
                # without the optional WS dep (mirrors _ws_server).
                from websockets.asyncio.client import connect

                async with connect(url, max_size=_MAX_FRAME_BYTES) as ws:
                    if not self._is_current(generation):
                        return
                    elapsed = format_duration(time.perf_counter() - t0)
                    log.info("[WORKER] connected to worker at %s:%s%s", LOOPBACK_HOST, self.port, elapsed)
                    attempt = 0
                    await self._run_session(ws, generation)
            except Exception:
                if not self._is_current(generation):
                    return
                delay = backoff_delay(attempt)
                log.warning("[WORKER] worker connection lost: retrying%s", format_duration(delay))
                attempt += 1
                await asyncio.sleep(delay)

    async def _run_session(self, ws: Any, generation: int) -> None:
        """Auth, then pump outbound frames and route inbound ones."""
        # ADR-0020 §3: token rides the first frame; the value itself is
        # never logged (only the fact it was sent).
        await ws.send(build_auth_frame(os.environ.get(IPC_TOKEN_ENV_VAR, "")))
        log.debug("[WORKER] auth frame sent (port=%s)", self.port)
        wake = asyncio.Event()
        with self._lock:
            self._session_loop = asyncio.get_running_loop()
            self._session_wake = wake
        try:
            await self._pump(ws, generation, wake)
        finally:
            with self._lock:
                # Clear only our own registration. A newer generation's
                # session may have already repointed these (relay +
                # direct update double-point the client); clearing
                # blindly orphaned the LIVE session's wake-ups, and every
                # forward then waited out the heartbeat interval.
                if self._session_wake is wake:
                    self._session_loop = None
                    self._session_wake = None

    async def _pump(self, ws: Any, generation: int, wake: asyncio.Event) -> None:
        """Drain outbound, then wait for inbound traffic OR a wake-up.

        The wake-up (see :meth:`_notify_outbound`) is what keeps abort
        prompt: without it a forward queued while the loop sleeps in
        ``recv()`` waits out the heartbeat interval on a quiet
        connection. Heartbeat semantics are unchanged: only a full
        interval with neither traffic nor wake-ups probes liveness.
        """
        missed = 0
        while self._is_current(generation):
            await self._drain_outbound(ws)
            recv_task = asyncio.ensure_future(ws.recv())
            wake_task = asyncio.ensure_future(wake.wait())
            try:
                done, _pending = await asyncio.wait(
                    {recv_task, wake_task}, timeout=_HEARTBEAT_SECONDS, return_when=asyncio.FIRST_COMPLETED
                )
            except Exception:
                for task in (recv_task, wake_task):
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                raise
            if not done:
                # No traffic at all for a full interval: probe liveness.
                for task in (recv_task, wake_task):
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                await ws.send(build_heartbeat_frame())
                missed += 1
                if missed > _MAX_MISSED_HEARTBEATS:
                    raise _WorkerUnresponsiveError(f"{missed} missed heartbeats") from None
                continue
            if wake_task in done:
                wake.clear()
                if recv_task not in done:
                    recv_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await recv_task
                    continue
            else:
                wake_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await wake_task
            try:
                raw = recv_task.result()
            except (asyncio.TimeoutError, TimeoutError):
                # A recv that itself reports a timeout is idleness, same
                # as the wait above (the scripted-fake harness path).
                await ws.send(build_heartbeat_frame())
                missed += 1
                if missed > _MAX_MISSED_HEARTBEATS:
                    raise _WorkerUnresponsiveError(f"{missed} missed heartbeats") from None
                continue
            frame = parse_incoming(raw)
            if frame is None:
                log.warning("[WORKER] non-JSON frame from worker: ignoring")
                continue
            missed = 0
            if route_frame(frame, self._publish, on_result=self._take_result) == "result":
                data = frame.get("data")
                text_len = len(str(data.get("text") or "")) if isinstance(data, dict) else 0
                t0 = self._last_request_t0
                suffix = format_duration(time.perf_counter() - t0) if t0 is not None else ""
                # C-LOG-2: space-separated duration suffix via format_duration.
                log.info("[WORKER] transcribe_offline_result (len=%d chars)%s", text_len, suffix)

    async def _drain_outbound(self, ws: Any) -> None:
        """Send every queued frame in order; returns when the queue is empty."""
        # C-WS-2: every outbound frame is str (TEXT opcode, never bytes).
        while True:
            try:
                frame = self._outbound.get_nowait()
            except queue.Empty:
                return
            await ws.send(frame)


_lock = threading.Lock()
_shared_client: WorkerClient | None = None


def get_shared_client() -> WorkerClient:
    """The single sidecar-process worker client (C-CONF-1: no second port store)."""
    global _shared_client
    if _shared_client is None:
        with _lock:
            if _shared_client is None:
                _shared_client = WorkerClient()
    return _shared_client


def close_shared_client() -> bool:
    """Stop the shared client's reconnect loop if one exists.

    Called once from the shutdown early bookend so the backoff loop
    does not retry a dead worker through the whole teardown (WARN
    spam + futile connection attempts). Never creates the client:
    ``False`` when there was nothing to stop. Best-effort, never
    raises.
    """
    with _lock:
        client = _shared_client
    if client is None:
        return False
    try:
        client.close()
    except Exception:
        log.debug("[WORKER] shared client close failed", exc_info=True)
        return False
    return True
