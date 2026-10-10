"""Slim-core sidecar WS client to the runtime-pack worker (ADR-0024 Step 3).

One purpose only: own the worker hop (connect, auth, forward, route,
heartbeat, reconnect). Transcribe dispatch policy lives in
``voice_typer/server/ipc/lifecycle.py`` (Step 4 owns that body).

The wire codec lives in :mod:`voice_typer.server.worker_protocol` and the
socket/loop machinery in :mod:`voice_typer.server.worker_session`; both are
re-exported here, so every existing import path keeps resolving.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import logging
import queue
import threading
import time
from typing import Any

from voice_typer.server import event_bus

log = logging.getLogger("voice_typer.server.worker_client")


_HEARTBEAT_SECONDS = 15.0
_MAX_MISSED_HEARTBEATS = 3
_BACKOFF_FIRST_SECONDS = 0.5
_BACKOFF_CAP_SECONDS = 30.0
_OUTBOUND_QUEUE_MAX = 64


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
        """Delegate to :func:`voice_typer.server.worker_session.current_url`."""
        return current_url(self)

    def _is_current(self, generation: int) -> bool:
        """Delegate to :func:`voice_typer.server.worker_session.is_current`."""
        return is_current(self, generation)

    async def _connect_loop(self, generation: int) -> None:
        """Delegate to :func:`voice_typer.server.worker_session.connect_loop`."""
        await connect_loop(self, generation)

    async def _run_session(self, ws: Any, generation: int) -> None:
        """Delegate to :func:`voice_typer.server.worker_session.run_session`."""
        await run_session(self, ws, generation)

    async def _pump(self, ws: Any, generation: int, wake: asyncio.Event) -> None:
        """Delegate to :func:`voice_typer.server.worker_session.pump`."""
        await pump(self, ws, generation, wake)

    async def _drain_outbound(self, ws: Any) -> None:
        """Delegate to :func:`voice_typer.server.worker_session.drain_outbound`."""
        await drain_outbound(self, ws)



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

# Facade re-exports: the wire codec (``worker_protocol``) and the WS session
# machinery (``worker_session``) keep resolving through this module, so every
# existing import path and monkeypatch target stays intact.
from voice_typer.server.worker_protocol import (  # noqa: E402,F401  # facade re-export
    _MAX_FRAME_BYTES,
    _SAMPLES_CHUNK_RAW_BYTES,
    backoff_delay,
    build_abort_frame,
    build_auth_frame,
    build_heartbeat_frame,
    build_streaming_frame,
    build_transcribe_frame,
    chunk_samples,
    parse_incoming,
    port_from_worker_started,
    route_frame,
)
from voice_typer.server.worker_session import (  # noqa: E402,F401  # facade re-export
    _WorkerUnresponsiveError,
    connect_loop,
    current_url,
    drain_outbound,
    is_current,
    pump,
    run_session,
)
