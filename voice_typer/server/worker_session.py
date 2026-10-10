"""WS session loop for the slim-core worker client (ADR-0024 Step 3).

One concern only: own one generation's socket session, connect with backoff,
send the auth frame, pump outbound frames, route inbound ones, and probe
liveness with heartbeats. The client state (port, generation, outbound queue,
resolvers) lives on :class:`voice_typer.server.worker_client.WorkerClient`;
these free functions drive it through the client handle so the facade's
monkeypatch seams and its generation stamping (C-WS-3) stay unchanged.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import queue
import time
from typing import Any

from voice_typer.server._paths import IPC_TOKEN_ENV_VAR, LOOPBACK_HOST
from voice_typer.server.duration import format_duration
from voice_typer.server.worker_protocol import (
    _MAX_FRAME_BYTES,
    backoff_delay,
    build_auth_frame,
    build_heartbeat_frame,
    parse_incoming,
    route_frame,
)

log = logging.getLogger(__name__)


class _WorkerUnresponsiveError(Exception):
    """Heartbeat budget exhausted; the session must reconnect."""


def _facade():
    """Resolve the ``worker_client`` facade namespace at call time.

    The facade owns the heartbeat budget (``_HEARTBEAT_SECONDS``,
    ``_MAX_MISSED_HEARTBEATS``) and tests rebind it there to steer this loop,
    so the values are read through the facade instead of being imported.
    Imported lazily: the facade imports this module at module level.
    """
    from voice_typer.server import worker_client

    return worker_client


def current_url(client: Any) -> str | None:
    with client._lock:
        return f"ws://{LOOPBACK_HOST}:{client._port}" if client._port is not None else None


def is_current(client: Any, generation: int) -> bool:
    with client._lock:
        return generation == client._generation and not client._stop_event.is_set()


async def connect_loop(client: Any, generation: int) -> None:
    """Reconnect with backoff until superseded (generation) or closed."""
    attempt = 0
    while client._is_current(generation):
        url = client._current_url()
        if url is None:
            return
        t0 = time.perf_counter()
        try:
            # websockets imported lazily: the module stays importable
            # without the optional WS dep (mirrors _ws_server).
            from websockets.asyncio.client import connect

            async with connect(url, max_size=_MAX_FRAME_BYTES) as ws:
                if not client._is_current(generation):
                    return
                elapsed = format_duration(time.perf_counter() - t0)
                log.info("[WORKER] connected to worker at %s:%s%s", LOOPBACK_HOST, client.port, elapsed)
                attempt = 0
                await client._run_session(ws, generation)
        except Exception:
            if not client._is_current(generation):
                return
            delay = backoff_delay(attempt)
            log.warning("[WORKER] worker connection lost: retrying%s", format_duration(delay))
            attempt += 1
            await asyncio.sleep(delay)



async def run_session(client: Any, ws: Any, generation: int) -> None:
    """Auth, then pump outbound frames and route inbound ones."""
    # ADR-0020 §3: token rides the first frame; the value itself is
    # never logged (only the fact it was sent).
    await ws.send(build_auth_frame(os.environ.get(IPC_TOKEN_ENV_VAR, "")))
    log.debug("[WORKER] auth frame sent (port=%s)", client.port)
    wake = asyncio.Event()
    with client._lock:
        client._session_loop = asyncio.get_running_loop()
        client._session_wake = wake
    try:
        await client._pump(ws, generation, wake)
    finally:
        with client._lock:
            # Clear only our own registration. A newer generation's
            # session may have already repointed these (relay +
            # direct update double-point the client); clearing
            # blindly orphaned the LIVE session's wake-ups, and every
            # forward then waited out the heartbeat interval.
            if client._session_wake is wake:
                client._session_loop = None
                client._session_wake = None



async def pump(client: Any, ws: Any, generation: int, wake: asyncio.Event) -> None:
    """Drain outbound, then wait for inbound traffic OR a wake-up.

    The wake-up (see :meth:`_notify_outbound`) is what keeps abort
    prompt: without it a forward queued while the loop sleeps in
    ``recv()`` waits out the heartbeat interval on a quiet
    connection. Heartbeat semantics are unchanged: only a full
    interval with neither traffic nor wake-ups probes liveness.
    """
    # Facade patch contract: the heartbeat budget is read from the
    # ``worker_client`` facade at call time, so a test that rebinds
    # ``_HEARTBEAT_SECONDS`` there still steers this loop.
    heartbeat_seconds = _facade()._HEARTBEAT_SECONDS
    max_missed_heartbeats = _facade()._MAX_MISSED_HEARTBEATS
    missed = 0
    while client._is_current(generation):
        await client._drain_outbound(ws)
        recv_task = asyncio.ensure_future(ws.recv())
        wake_task = asyncio.ensure_future(wake.wait())
        try:
            done, _pending = await asyncio.wait(
                {recv_task, wake_task}, timeout=heartbeat_seconds, return_when=asyncio.FIRST_COMPLETED
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
            if missed > max_missed_heartbeats:
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
            if missed > max_missed_heartbeats:
                raise _WorkerUnresponsiveError(f"{missed} missed heartbeats") from None
            continue
        frame = parse_incoming(raw)
        if frame is None:
            log.warning("[WORKER] non-JSON frame from worker: ignoring")
            continue
        missed = 0
        if route_frame(frame, client._publish, on_result=client._take_result) == "result":
            data = frame.get("data")
            text_len = len(str(data.get("text") or "")) if isinstance(data, dict) else 0
            t0 = client._last_request_t0
            suffix = format_duration(time.perf_counter() - t0) if t0 is not None else ""
            # C-LOG-2: space-separated duration suffix via format_duration.
            log.info("[WORKER] transcribe_offline_result (len=%d chars)%s", text_len, suffix)



async def drain_outbound(client: Any, ws: Any) -> None:
    """Send every queued frame in order; returns when the queue is empty."""
    # C-WS-2: every outbound frame is str (TEXT opcode, never bytes).
    while True:
        try:
            frame = client._outbound.get_nowait()
        except queue.Empty:
            return
        await ws.send(frame)
