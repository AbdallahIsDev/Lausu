"""Worker WebSocket server helpers.

Facade for the wave-9 split (one concern per file): the frame-IO body
lives in :mod:`voice_typer.worker._ws_connection`, the samples
reassembly in :mod:`voice_typer.worker._ws_samples`, the startup /
prewarm + stdout protocol in :mod:`voice_typer.worker._ws_startup` and
the shutdown timer / SIGTERM handler in
:mod:`voice_typer.worker._ws_shutdown`. This module keeps the module
names, the accept seam (:func:`run_worker_server`) and every monkeypatch
seam: tests patch ``transcribe_window_words`` here and read
``_MAX_FRAME_BYTES`` / ``_SamplesBuffer`` / ``_valid_samples_header``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from voice_typer.server._paths import LOOPBACK_HOST
from voice_typer.server.duration import format_duration
from voice_typer.server.ipc.protocol_version import MAX_WS_FRAME_BYTES, PROTOCOL_VERSION
from voice_typer.worker._parent_watch import start_parent_watch
from voice_typer.worker._ws_connection import _handle_connection
from voice_typer.worker._ws_samples import _SamplesBuffer, _valid_samples_header  # noqa: F401 - facade re-export
from voice_typer.worker._ws_shutdown import _install_sigterm_handler, _ShutdownTimer
from voice_typer.worker._ws_startup import (
    _emit_worker_started,
    _force_line_buffered_stdout,  # noqa: F401 - facade re-export
    _run_prewarm_phase,  # noqa: F401 - facade re-export
)
from voice_typer.worker.streaming import transcribe_window_words  # noqa: F401 - facade patch seam

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
