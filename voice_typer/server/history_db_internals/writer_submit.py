"""Caller-side submission, overflow handling and teardown of the writer.

Everything a caller touches when handing work to the writer thread (or
shutting it down) lives here; the thread's own loop is in ``writer``.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import logging
import queue
import sqlite3
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from voice_typer.server._lazy_import import lazy_module

if TYPE_CHECKING:
    from voice_typer.server.history_db import HistoryDB

# Lazy proxy: ``history_db`` imports this package, so a direct import would be circular.
_hd = lazy_module("voice_typer.server.history_db")

log = logging.getLogger(__name__)

def _drop_oldest_for_overflow(
    db: HistoryDB,
    current_future: concurrent.futures.Future | None,
) -> None:
    """Queue-full path: signal the dropped future with HistoryDBError.

    Called when ``_submit_write`` hits ``queue.Full``.
    """
    _SHUTDOWN_SENTINEL = _hd._SHUTDOWN_SENTINEL  # noqa: N806
    _BatchableInsert = _hd._BatchableInsert  # noqa: N806
    HistoryDBError = _hd.HistoryDBError  # noqa: N806

    try:
        dropped = db._queue.get_nowait()
    except queue.Empty:
        # (session-2): Queue drained between put_nowait and
        return
    if dropped is _SHUTDOWN_SENTINEL:
        # Put the sentinel back; drop the new write instead.
        with contextlib.suppress(queue.Full):
            db._queue.put_nowait(dropped)
        if current_future is not None:
            with contextlib.suppress(concurrent.futures.InvalidStateError):
                current_future.set_exception(HistoryDBError("Writer is shutting down; new write dropped"))
        log.warning("[HISTORY_DB] Queue full during shutdown, new write dropped.")
        return
    # the dropped item may be a (fn, future) tuple OR a
    if isinstance(dropped, _BatchableInsert):
        dropped_future = dropped.future
    else:
        _, dropped_future = dropped
    if dropped_future is not None:  #  PERF-5: the dropped future must be resolved
        # with a clear, machine-greppable message so callers
        with contextlib.suppress(concurrent.futures.InvalidStateError):
            dropped_future.set_exception(
                HistoryDBError(
                    "queue full; dropped oldest write to make room for newer write (writer thread may be stalled)"
                )
            )
    log.warning("[HISTORY_DB] queue full, dropped oldest write to make room. Writer thread may be stalled.")
    # The caller (_submit_write) retries the put_nowait after we


def _submit_write(
    db: HistoryDB,
    fn: Callable[[sqlite3.Connection], Any],
    *,
    wait: bool = True,
    allow_after_shutdown: bool = False,
) -> Any | None:
    """Parameters
    ----------

    ``allow_after_shutdown`` is the close-path escape hatch, used ONLY
    by the WAL checkpoint inside ``_close_writer``: the writer is
    verified alive and the exit sentinel unsent, so the write is safe
    even though ``_shutdown`` is already set. Every other caller keeps
    the default refusal.
    """
    _WRITE_FUTURE_TIMEOUT = _hd._WRITE_FUTURE_TIMEOUT  # noqa: N806
    _WRITE_FUTURE_TOTAL_TIMEOUT = _hd._WRITE_FUTURE_TOTAL_TIMEOUT  # noqa: N806
    HistoryDBError = _hd.HistoryDBError  # noqa: N806

    if db._shutdown.is_set() and not allow_after_shutdown:
        log.debug("[HISTORY_DB] Write submitted after shutdown, dropped.")
        return None
    # early-return guard, if the writer thread never
    if db._init_error is not None or not db._writer_thread.is_alive():
        # When the writer is dead AND the queue is full, the
        if db._queue.full():
            db._drop_oldest_for_overflow(None)
        err = db.health_check()["error"]
        log.error(
            "[HISTORY_DB] _submit_write refused, writer is unavailable: %s",
            err,
        )
        if wait:
            raise HistoryDBError(f"HistoryDB writer is unavailable: {err}")
        return None
    future: concurrent.futures.Future | None = None
    if wait:
        future = concurrent.futures.Future()
    # PERF-5: bounded queue (maxsize=_WRITE_QUEUE_MAXSIZE). Use
    try:
        db._queue.put_nowait((fn, future))
    except queue.Full:
        db._drop_oldest_for_overflow(future)
        # Retry once after dropping oldest.
        try:
            db._queue.put_nowait((fn, future))
        except queue.Full:
            # Still full (writer truly stuck); drop the new write.
            if future is not None:
                with contextlib.suppress(concurrent.futures.InvalidStateError):
                    future.set_exception(HistoryDBError("Queue full after drop-oldest; new write dropped"))
            log.warning("[HISTORY_DB] Queue still full after drop-oldest, new write dropped. Writer thread is stuck.")
            if not wait:
                return None
    if not wait:
        return None
    assert future is not None
    # Block on the future. The writer is a daemon thread; if it
    loop_start = time.monotonic()
    while True:
        if time.monotonic() - loop_start >= _WRITE_FUTURE_TOTAL_TIMEOUT:
            log.warning(
                "[HISTORY_DB] Write future total deadline exceeded "
                "(%.0fs); writer is alive but stuck \u2014 aborting wait.",
                _WRITE_FUTURE_TOTAL_TIMEOUT,
            )
            raise HistoryDBError(
                f"HistoryDB write did not complete within "
                f"{_WRITE_FUTURE_TOTAL_TIMEOUT:.0f}s total deadline "
                f"(writer is alive but stuck)"
            )
        try:
            return future.result(timeout=_WRITE_FUTURE_TIMEOUT)
        except concurrent.futures.TimeoutError:
            if not db._writer_thread.is_alive():
                raise HistoryDBError("HistoryDB writer thread is dead; write did not complete") from None
            # Writer still alive. Keep waiting (rare; means a
            log.warning(
                "[HISTORY_DB] Write future still pending after %.0fs; writer is alive, continuing to wait.",
                _WRITE_FUTURE_TIMEOUT,
            )


def flush(db: HistoryDB) -> None:
    """Enqueues a no-op write with ``wait=True`` and blocks on its
    future. Because the queue is FIFO, all writes submitted
    """
    HistoryDBError = _hd.HistoryDBError  # noqa: N806

    if db._shutdown.is_set():
        return
    # short-circuit on dead writer / init error.
    if db._init_error is not None or not db._writer_thread.is_alive():
        err = db.health_check()["error"]
        log.error(
            "[HISTORY_DB] flush skipped, writer is unavailable: %s",
            err,
        )
        return
    with contextlib.suppress(HistoryDBError):
        db._submit_write(lambda conn: None, wait=True)


def _close_writer(db: HistoryDB) -> None:
    """1. Best-effort ``wal_checkpoint(TRUNCATE)`` via the writer
    thread (so the WAL pages are flushed back to the main DB
    """
    _SHUTDOWN_SENTINEL = _hd._SHUTDOWN_SENTINEL  # noqa: N806
    _WRITE_QUEUE_MAXSIZE = _hd._WRITE_QUEUE_MAXSIZE  # noqa: N806
    _WRITER_JOIN_TIMEOUT = _hd._WRITER_JOIN_TIMEOUT  # noqa: N806
    _BatchableInsert = _hd._BatchableInsert  # noqa: N806
    HistoryDBError = _hd.HistoryDBError  # noqa: N806

    # Best-effort wal_checkpoint(TRUNCATE) before shutdown. Submitted
    # with the close-path escape hatch: ``close_db`` sets ``_shutdown``
    # before reaching here, so the plain ``checkpoint()`` would always
    # refuse and every quit logged a phantom "dropped" write while the
    # WAL went uncheckpointed (relying on implicit connection-close
    # checkpointing instead).
    if db._writer_thread.is_alive() and db._init_error is None:
        from voice_typer.server.history_db_internals import crud_writes as _crud_writes

        with contextlib.suppress(sqlite3.Error, HistoryDBError):
            _crud_writes.submit_checkpoint(db, True, allow_after_shutdown=True)
    # before exiting. PERF-5: the queue is now bounded
    try:
        db._queue.put_nowait(_SHUTDOWN_SENTINEL)
    except queue.Full:
        # Drain non-sentinel items until the sentinel fits.
        for _ in range(_WRITE_QUEUE_MAXSIZE + 1):  # bound to avoid infinite loop
            try:
                dropped = db._queue.get_nowait()
            except queue.Empty:
                break
            if dropped is _SHUTDOWN_SENTINEL:
                # Sentinel was already queued by another close() call;
                with contextlib.suppress(queue.Full):
                    db._queue.put_nowait(dropped)
                break
            # Dropped a real write, signal its future. The dropped
            if isinstance(dropped, _BatchableInsert):
                dropped_future = dropped.future
            else:
                _, dropped_future = dropped
            if dropped_future is not None:
                with contextlib.suppress(concurrent.futures.InvalidStateError):
                    dropped_future.set_exception(HistoryDBError("Dropped during shutdown sentinel enqueue"))
            log.warning("[HISTORY_DB] Dropped write during shutdown queue drain.")
            # Try to enqueue the sentinel now.
            try:
                db._queue.put_nowait(_SHUTDOWN_SENTINEL)
                break
            except queue.Full:
                continue
    except (RuntimeError, TypeError) as e:
        # RuntimeError can occur during interpreter shutdown if the
        log.debug("[HISTORY_DB] Could not enqueue shutdown sentinel: %s", e)
    # Wait for the writer to exit (it drains remaining items first).
    if db._writer_thread.is_alive():
        db._writer_thread.join(timeout=_WRITER_JOIN_TIMEOUT)
        if db._writer_thread.is_alive():
            log.warning(
                "[HISTORY_DB] Writer thread did not exit within %.1fs; "
                "it is a daemon and will be killed at process exit.",
                _WRITER_JOIN_TIMEOUT,
            )
