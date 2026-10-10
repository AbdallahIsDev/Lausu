"""Worker shutdown seam: the graceful-shutdown timer + SIGTERM handler.

Split out of ``voice_typer.worker._ws_server`` (one concern per file).
The facade keeps the module names and every monkeypatch seam; this
module owns the moved bodies only. The timer feeds the C-LOG-2
``[SHUTDOWN] worker shutdown complete <duration>`` suffix; the log line
itself stays in ``__main__``.
"""

from __future__ import annotations

import contextlib
import logging
import signal
import time
from types import FrameType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

log = logging.getLogger("voice_typer.worker")


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
