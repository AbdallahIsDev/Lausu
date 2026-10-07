"""Pre-app dispatch buffering for the early-WS-bind escape hatch.

The bounded buffer that :func:`voice_typer.server.sidecar_ws.run` installs
when the entry point marked the server with ``_early_ws_bind``, plus the
drain that replays it once the app is bound. Split out of
``sidecar_ws.py`` so the transport module keeps the entrypoint and the
connection orchestrators, and this leaf owns the buffering concern.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import TYPE_CHECKING

from voice_typer.server.ipc.validation import ErrorCodes

# C-ARCH-2 canonical form: sibling names resolve at CALL time so a test
from voice_typer.server.sidecar_ws_internals import (
    outbound as _outbound_mod,
    read_loop as _read_loop_mod,
)

if TYPE_CHECKING:  # pragma: no cover - type-checker-only
    from voice_typer.server.ipc_server import IPCServer

log = logging.getLogger("voice_typer.server.sidecar_ws")

# and the C-WS-1 ready-first ordering is entirely untouched: the
_EARLY_BIND_BUFFER_CAP: int = 32


def _wrap_dispatch_for_early_bind(server: IPCServer, dispatch):
    """Wrap ``dispatch`` with the bounded pre-app buffer (early mode).

    Installed by :func:`run` ONLY when the entry point marked the server
    with ``_early_ws_bind``. Before the app is bound
    (``server._early_bind_app_ready``: set by the entry point's
    startup thread after the late bind), every dispatch frame is
    appended to a bounded in-memory buffer and the wrapper returns
    ``None`` (response deferred to the drain, the frame is NOT lost).
    On overflow the oldest entry is dropped and answered immediately
    with a retryable busy error through ``_safe_send`` (C-WS-2 TEXT
    frame, request id echoed). After the bind the wrapper is a pure
    passthrough (one attribute read per frame).

    The buffer is mutated ONLY on the asyncio loop thread: the wrapper
    runs inside dispatch coroutines, and the drain is scheduled via
    ``loop.call_soon_threadsafe``: the same single-thread-access
    invariant the read loop's heartbeat window relies on. The one
    cross-thread bit is the ``_early_bind_app_ready`` flag write (an
    atomic bool assignment from the startup thread).

    Documented tolerance (flag-gated mode, default OFF): pre-app frames
    bypass the per-renderer rate limiter (the wrapper sits OUTSIDE
    ``_make_dispatch``, which owns the limiter). The bound is the buffer
    itself (32 frames) and each overflow costs exactly one busy-error
    send for the DROPPED frame, so a misbehaving client cannot grow
    memory or spam beyond the cap. The surface is loopback-only and
    behind the authenticated WS handshake (ADR-0019 token boundary),
    so pre-app unthrottled dispatch is a trusted-inner-sender window of
    a few seconds at most (construction duration). Accepted for the
    escape-hatch mode; if the limiter must cover the pre-app window,
    install the wrapper inside ``_make_dispatch`` at flag-flip time.
    """
    buffer: deque = deque()
    server._early_bind_dispatch_buffer = buffer

    async def _early_bind_dispatch(msg: dict, websocket) -> dict | None:
        if getattr(server, "_early_bind_app_ready", False):
            return await dispatch(msg, websocket)
        dropped: tuple | None = None
        if len(buffer) >= _EARLY_BIND_BUFFER_CAP:
            dropped = buffer.popleft()
            log.warning(
                "[SIDECAR-WS] early-bind dispatch buffer full (%d), dropped oldest frame, busy error sent",
                _EARLY_BIND_BUFFER_CAP,
            )
        buffer.append((msg, websocket))
        if dropped is not None:
            # The dropped frame gets an immediate retryable error so its
            dropped_msg, dropped_ws = dropped
            busy: dict = {
                "type": "error",
                "data": {
                    "code": ErrorCodes.NOT_INITIALIZED,
                    "message": "backend is starting; retry shortly",
                },
            }
            dropped_id = dropped_msg.get("id") if isinstance(dropped_msg, dict) else None
            if dropped_id is not None:
                busy["id"] = dropped_id
            await _outbound_mod._safe_send(dropped_ws, busy)
        return None

    server._early_bind_dispatch = _early_bind_dispatch
    return _early_bind_dispatch


def flush_early_dispatch_buffer(server: IPCServer) -> None:
    """Drain the buffered pre-app frames onto the WS loop (thread-safe).

    Called by the entry point's startup thread right after it sets
    ``server._early_bind_app_ready``. The drain itself runs on the loop
    thread via ``call_soon_threadsafe``; each buffered frame is replayed
    through the read loop's own ``_dispatch_and_respond`` so the replay
    reuses verbatim the id echo + ``_safe_send`` (C-WS-2 TEXT frame) +
    close-on-failure semantics of the normal dispatch path.

    Documented tolerance (flag-gated mode, default OFF): between the
    flag flip and the scheduled drain, NEW frames pass straight through
    while older buffered frames still await replay, responses can
    arrive out of FIFO order within that sub-millisecond window. Every
    frame is id-correlated (the renderer resolves by id, not order), so
    the renderer sees every response exactly once; scheduling the drain
    BEFORE flipping the flag would invert the hazard instead (the drain
    would race frames arriving before it). Accepted for the escape-hatch
    mode; revisit if the flag ever flips default-ON.

    Safe when no loop exists yet (construction finished before ``run``
    even bound the listener, nothing was buffered, so there is nothing
    to drain: frames can only be buffered while the loop is live) and
    during loop teardown (RuntimeError → DEBUG log).
    """
    loop = getattr(server, "_ws_loop", None)
    if loop is None or loop.is_closed():
        return
    try:
        loop.call_soon_threadsafe(_drain_early_dispatch_buffer, server)
    except RuntimeError:
        # The loop closed between the liveness checks above and the
        log.debug("[SIDECAR-WS] early-bind buffer drain skipped, event loop closed")


def _drain_early_dispatch_buffer(server: IPCServer) -> None:
    """Loop-thread body of :func:`flush_early_dispatch_buffer`."""
    buffer = getattr(server, "_early_bind_dispatch_buffer", None)
    dispatch = getattr(server, "_early_bind_dispatch", None)
    if not buffer or dispatch is None:
        return
    loop = asyncio.get_running_loop()
    while buffer:
        msg, websocket = buffer.popleft()
        request_id = msg.get("id") if isinstance(msg, dict) else None
        loop.create_task(_read_loop_mod._dispatch_and_respond(msg, request_id, websocket, dispatch))
