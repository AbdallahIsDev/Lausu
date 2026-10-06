"""Deferred delivery + fan-out for the in-process event bus.

Owns the synchronous fan-out (``_deliver``), the RT-thread-safe deferred
branch of ``publish`` (lazily-created single-worker ``ThreadPoolExecutor``
plus its bounded queue, PERF-2), and the canonical ``shutdown()`` hook.
Moved out of ``voice_typer.server.event_bus`` (which re-exports the entry
points); the same logger name is kept so log-based tests and the app's
rotating file handler see identical records.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from voice_typer.server.event_bus_subscribers import _subscriber_key
from voice_typer.server.log_rate_limit import log_rate_limited

log = logging.getLogger("voice_typer.server.event_bus")

# When ``publish()`` is called from a real-time audio thread
_RT_THREAD_NAME_PREFIXES: tuple[str, ...] = (
    "audio-worker",  # voice_typer.server.recording._AUDIO_WORKER_THREAD_NAME
    "PortAudio",  # sounddevice's native callback thread prefix
)
_deferred_executor: ThreadPoolExecutor | None = None
_deferred_executor_lock = threading.Lock()

# bound the deferred-publish queue. ``ThreadPoolExecutor`` uses
_DEFERRED_QUEUE_MAX = 256
_deferred_in_flight: int = 0
_deferred_in_flight_lock = threading.Lock()
_deferred_drop_count: int = 0  # cumulative, for diagnostics


def _get_deferred_executor() -> ThreadPoolExecutor:
    """Lazily create the single-worker deferred-publish executor.

    previously the double-checked-locking pattern could leak a
        ``ThreadPoolExecutor`` if two threads both entered the slow path
        and both created a fresh executor before either acquired
        ``_deferred_executor_lock``. (The first thread to acquire the
        lock would install theirs; the second thread's executor was a
        local that went out of scope, but its worker thread kept
        running, leaking a thread + a kernel-level worker pool.)

        The fix creates the executor BEFORE acquiring the lock (in the
        slow path), then races for the global slot. The winner installs
        theirs and returns it; the loser calls ``shutdown(wait=False)``
        on theirs (which signals the worker thread to exit) and returns
        the winner. This is the canonical "create-then-compare-and-swap"
        pattern for lazy singletons guarded by a mutex.
    """
    global _deferred_executor
    # Fast path, no lock acquired. The global is published via the
    if _deferred_executor is not None:
        return _deferred_executor
    # Slow path: optimistically create our own executor BEFORE
    local_executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="event-bus-publisher",
    )
    with _deferred_executor_lock:
        if _deferred_executor is None:
            # We won the race. Install ours.
            _deferred_executor = local_executor
            return local_executor
        # We lost the race, another thread installed theirs while we
        winner = _deferred_executor
    # Shutdown OUTSIDE the lock to avoid blocking other racing callers.
    local_executor.shutdown(wait=False)
    return winner


def _is_rt_thread() -> bool:
    """Return True if the current thread is a real-time audio thread."""
    name = threading.current_thread().name
    if name == "audio-worker":
        return True
    return name.startswith("PortAudio")


def _deliver(event, resolvers) -> bool:
    """Deliver *event* to every callback resolved from *resolvers*.

    *resolvers* is a sequence of zero-argument callables (WeakMethod /
    _StrongResolver / _CWeakResolver). Each returns the live callback
    or None if the subscriber was GC'd. Dead resolvers are skipped.
    """
    delivered = False
    for resolver in resolvers:
        cb = resolver()
        if cb is None:
            continue
        try:
            cb(event)
            delivered = True
        except Exception:
            log_rate_limited(
                log,
                logging.WARNING,
                "[event_bus] subscriber raised",
                exc_info=True,
                key=f"subscriber:{_subscriber_key(cb)}",
            )
    return delivered


def _deliver_deferred(event, resolvers):
    """Deliver *event* on the deferred-executor thread, then decrement
    the in-flight counter ().

        Pairs with the bounded-submit logic in ``publish()`` so the
        in-flight counter is decremented exactly once per submitted task —
        whether the delivery succeeded, a subscriber raised, or the
        executor was shut down mid-flight. Failing to decrement would
        re-introduce the unbounded-queue memory growth (the counter would
        hit ``_DEFERRED_QUEUE_MAX`` and never recover).
    """
    global _deferred_in_flight
    try:
        _deliver(event, resolvers)
    finally:
        with _deferred_in_flight_lock:
            _deferred_in_flight = max(0, _deferred_in_flight - 1)


def dispatch_deferred(event, resolvers) -> bool:
    """Queue *event* for deferred fan-out; the bounded-queue branch of ``publish``.

    Called when the publisher is a real-time audio thread or when the
    caller passed ``async_dispatch=True``. Returns ``True`` (the event was
    queued, or dropped at capacity) and falls back to synchronous delivery
    when the executor was already shut down at process exit.
    """
    global _deferred_in_flight, _deferred_drop_count
    # bound the deferred queue. If the single worker is
    with _deferred_in_flight_lock:
        if _deferred_in_flight >= _DEFERRED_QUEUE_MAX:
            _deferred_drop_count += 1
            would_drop = True
        else:
            _deferred_in_flight += 1
            would_drop = False
    if would_drop:
        log_rate_limited(
            log,
            logging.WARNING,
            "[event_bus] deferred queue at capacity (%d); dropping event (cumulative drops: %d)",
            _DEFERRED_QUEUE_MAX,
            _deferred_drop_count,
            key="event_bus:deferred_drop",
        )
        return True
    try:
        _get_deferred_executor().submit(_deliver_deferred, event, resolvers)
    except RuntimeError:
        # Executor was shut down (process exit); fall back to sync.
        with _deferred_in_flight_lock:
            _deferred_in_flight = max(0, _deferred_in_flight - 1)
        return _deliver(event, resolvers)
    return True


def shutdown() -> None:
    """Shut down the deferred-publish ThreadPoolExecutor.

        This is the SINGLE canonical lifecycle hook for the lazily-created
        ``ThreadPoolExecutor``.  Previously a duplicate ``shutdown_executor()``
    function existed alongside this one, it was deleted in
        (DRY, Rule 24) because nothing in the codebase called it (only
        ``shutdown()`` is invoked from
        ``shutdown_controller._teardown_event_bus``).

    the call now uses ``executor.shutdown(wait=True,
        cancel_futures=True)`` instead of ``wait=False``. ``wait=False``
        returned immediately and did NOT block on already-running or queued
        tasks, but the worker thread is a NON-DAEMON (CPython
        ``ThreadPoolExecutor`` default), so it kept the interpreter alive
        past the ``shutdown()`` call until all queued/in-flight tasks
        finished. The 5s ``_run_with_timeout`` wrapper in
        ``_teardown_event_bus`` was therefore bounding NOTHING (the
        non-blocking call returned in microseconds). With
        ``wait=True, cancel_futures=True``:
          (a) queued-but-not-started tasks are cancelled immediately (they
              are stale by definition on shutdown);
          (b) the call blocks until the in-flight task completes.
        The 5s ``_run_with_timeout`` wrapper then ACTUALLY bounds the wait.
        If the in-flight task exceeds 5s, the wrapper returns ``TIMEOUT``
        and the worker thread is leaked as a daemon (the
        ``_run_with_timeout`` worker is daemon-marked).

        The single-worker ``ThreadPoolExecutor`` lazily created by
        ``_get_deferred_executor()`` is a process-global resource. On
        ``quit()`` / process exit, calling this from
        ``ShutdownController._teardown_event_bus`` releases the worker
        promptly so it doesn't contribute to shutdown latency.

        Idempotent, safe to call multiple times. After this call,
        ``_deferred_executor`` is set to ``None`` so the next RT-thread
        ``publish`` lazily creates a fresh executor (or, if the process
        is exiting, the ``RuntimeError`` branch in ``publish`` falls
        back to synchronous delivery).
    """
    global _deferred_executor
    with _deferred_executor_lock:
        executor = _deferred_executor
        _deferred_executor = None
    if executor is not None:
        try:
            executor.shutdown(wait=True, cancel_futures=True)
        except Exception:
            log.debug(
                "[event_bus] deferred executor shutdown failed",
                exc_info=True,
            )
