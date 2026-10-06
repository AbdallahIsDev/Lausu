"""History writer-thread helpers."""

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
from voice_typer.server.history_db_internals.writer_inserts import (  # noqa: F401, re-exported: the facade + _drain_remaining resolve these through this module
    _INSERT_SQL_COLUMNS,
    _INSERT_SQL_ROW_PLACEHOLDERS,
    _build_insert_sql,
    _drain_batchable_inserts,
    _encrypt_batch_rows,
)
from voice_typer.server.history_db_internals.writer_submit import (  # noqa: F401, re-exported: the facade resolves these through this module
    _close_writer,
    _drop_oldest_for_overflow,
    _submit_write,
    flush,
)

if TYPE_CHECKING:
    from voice_typer.server.history_db import HistoryDB

# Lazy proxy: ``history_db`` imports this package, so a direct import would be circular.
_hd = lazy_module("voice_typer.server.history_db")

log = logging.getLogger(__name__)

#: Guards the one-time ``[HISTORY] FTS5 startup rebuild succeeded
_announced_fts5_skip_paths: set[str] = set()


def _reset_fts5_skip_paths() -> None:
    """Test seam, clear the per-path FTS5-skip log guard."""
    _announced_fts5_skip_paths.clear()


def _writer_loop(db: HistoryDB) -> None:
    """History DB writer-thread internals (queue drain, WAL, FTS rebuild)."""
    _SHUTDOWN_SENTINEL = _hd._SHUTDOWN_SENTINEL  # noqa: N806
    _BatchableInsert = _hd._BatchableInsert  # noqa: N806
    _WAL_CHECKPOINT_INTERVAL = _hd._WAL_CHECKPOINT_INTERVAL  # noqa: N806

    conn: sqlite3.Connection | None = None
    try:
        conn = db._open_write_conn()
        db._check_wal_mode(conn)
        # _init_db_schema may return a fresh connection
        conn = db._init_db_schema(conn)
    except BaseException as e:  # noqa: BLE001, surface to __init__
        db._init_error = e
        db._writer_ready.set()
        if conn is not None:
            with contextlib.suppress(sqlite3.Error):
                conn.close()
        return
    # At-rest encryption: resolve the DEK (one keyring read, bounded by
    if db._init_error is None:
        with contextlib.suppress(Exception):
            db._init_encryption(conn)
    db._writer_ready.set()
    # if schema init set _init_error (e.g. migration
    if db._init_error is not None:
        log.error(
            "[HISTORY_DB] Skipping writer loop, schema init failed: %s",
            db._init_error,
        )
        with contextlib.suppress(sqlite3.Error):
            conn.close()
        return

    last_checkpoint = time.monotonic()
    while True:
        now = time.monotonic()
        wait_for = _WAL_CHECKPOINT_INTERVAL - (now - last_checkpoint)
        if wait_for <= 0:
            db._run_checkpoint(conn)
            last_checkpoint = time.monotonic()
            wait_for = _WAL_CHECKPOINT_INTERVAL
        try:
            item = db._queue.get(timeout=wait_for)
        except queue.Empty:
            db._run_checkpoint(conn)
            last_checkpoint = time.monotonic()
            continue
        if item is _SHUTDOWN_SENTINEL:
            db._drain_remaining(conn)
            break
        # structured batchable INSERT payload, drain pending
        if isinstance(item, _BatchableInsert):
            db._drain_batchable_inserts(conn, item)
            # Post-write cleanup (same as the end of _execute_write_item):
            with contextlib.suppress(sqlite3.Error):
                conn.rollback()
            continue
        callable_, future = item
        db._execute_write_item(conn, callable_, future)
    # Drain loop exited. Close the writer's connection.
    try:
        conn.close()
    except sqlite3.Error as e:
        log.warning("[HISTORY_DB] Error closing writer connection: %s", e)


def _run_checkpoint(db: HistoryDB, conn: sqlite3.Connection) -> None:
    """PASSIVE mode doesn't block, it checkpoints as much as
    possible without forcing readers/writers to wait. Called every
    ``_WAL_CHECKPOINT_INTERVAL`` seconds by the writer thread.
    """
    wal_checkpoint_interval = _hd._WAL_CHECKPOINT_INTERVAL  # noqa: N806

    # Clear any lingering transaction from the previous checkpoint cycle
    try:
        conn.rollback()
        result = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        if result is not None:
            status, pages_checkpointed, total_pages = result
            # cadence (_WAL_CHECKPOINT_INTERVAL). Tiny checkpoints
            if pages_checkpointed >= 100:
                if status == 0:
                    log.debug(
                        "[HISTORY_DB] WAL checkpointed %d pages",
                        pages_checkpointed,
                    )
                else:
                    log.debug(
                        "[HISTORY_DB] WAL checkpoint partial: %d/%d pages (status=%d)",
                        pages_checkpointed,
                        total_pages,
                        status,
                    )
    except sqlite3.OperationalError as e:
        # attempt (after _WAL_CHECKPOINT_INTERVAL) will retry.
        log.debug(
            "[HISTORY_DB] WAL checkpoint skipped (will retry in %.0fs): %s",
            wal_checkpoint_interval,
            e,
        )
    except sqlite3.Error as e:
        log.warning(
            "[HISTORY_DB] WAL checkpoint failed unexpectedly: %s",
            e,
        )


def _fts5_startup_rebuild(db: HistoryDB, conn: sqlite3.Connection) -> None:
    """The ``delete``, ``clear_all``, and ``apply_retention`` paths
    each issue the FTS5 ``'rebuild'`` (or ``'optimize'`` for
    """
    # Read the persisted fts5_rebuild_failed flag from
    try:
        with contextlib.closing(conn.cursor()) as cursor:
            cursor.execute("SELECT value FROM schema_meta WHERE key = 'fts5_rebuild_failed'")
            row = cursor.fetchone()
            flag_value = row[0] if row is not None else None
    except sqlite3.Error as e:
        # If schema_meta itself is unreadable, fall through to
        log.debug(
            "[HISTORY] Could not read fts5_rebuild_failed flag from schema_meta: %s, running rebuild",
            e,
        )
        flag_value = None

    # Steady-state skip: flag is explicitly '0' (previous
    if flag_value == "0":
        key = str(getattr(db, "db_path", ""))
        if key not in _announced_fts5_skip_paths:
            _announced_fts5_skip_paths.add(key)
            log.debug(
                "[HISTORY] FTS5 startup rebuild succeeded "
                "(skipped, previous rebuild succeeded, no failure recorded since)"
            )
        return

    try:
        with contextlib.closing(conn.cursor()) as cursor:
            # Both FTS5 shadow indexes (unicode61 + trigram CJK) in
            from voice_typer.server.history_db_internals.schema import cjk_trigram_table_exists

            cursor.execute("INSERT INTO transcriptions_fts(transcriptions_fts) VALUES('rebuild')")
            if cjk_trigram_table_exists(conn):
                cursor.execute("INSERT INTO transcriptions_fts_cjk(transcriptions_fts_cjk) VALUES('rebuild')")
        conn.commit()
        # Persist the success state so subsequent launches skip
        with contextlib.suppress(sqlite3.Error):
            with contextlib.closing(conn.cursor()) as flag_cursor:
                flag_cursor.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('fts5_rebuild_failed', '0')"
                )
            conn.commit()
        log.debug("[HISTORY] FTS5 startup rebuild succeeded")
        # A rebuild re-tokenizes every row from the CONTENT table —
        db._fts5_rebuild_ran = True
    except sqlite3.Error as e:
        log.warning(
            "[HISTORY] FTS5 startup rebuild failed: %s, segments from failed deletes may persist",
            e,
        )
        # Persist the failure state so the next launch retries.
        with contextlib.suppress(sqlite3.Error):
            with contextlib.closing(conn.cursor()) as flag_cursor:
                flag_cursor.execute(
                    "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('fts5_rebuild_failed', '1')"
                )
            conn.commit()


def _execute_write_item(
    db: HistoryDB,
    conn: sqlite3.Connection,
    callable_: Callable[[sqlite3.Connection], Any],
    future: concurrent.futures.Future | None,
) -> None:
    """verbatim between ``_writer_loop`` and ``_drain_remaining``,
    with one critical divergence, ``_drain_remaining`` was
    """
    try:
        result = callable_(conn)
        if future is not None:
            future.set_result(result)
    except BaseException as e:  # noqa: BLE001, propagate to future
        # Rollback any uncommitted transaction left behind by the failure,
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        if future is not None:
            # (session-2): Suppress InvalidStateError on
            with contextlib.suppress(concurrent.futures.InvalidStateError):
                future.set_exception(e)
        else:
            # Fire-and-forget write failed, log so it's visible.
            log.exception("[HISTORY_DB] Fire-and-forget write failed: %s", e)
    else:
        # After a SUCCESSFUL write, roll back to end the implicit
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()


def _drain_remaining(db: HistoryDB, conn: sqlite3.Connection) -> None:
    """Called after the shutdown sentinel is received. Ensures
    fire-and-forget writes submitted before close() are persisted.
    """
    _SHUTDOWN_SENTINEL = _hd._SHUTDOWN_SENTINEL  # noqa: N806
    _BatchableInsert = _hd._BatchableInsert  # noqa: N806

    while True:
        try:
            item = db._queue.get_nowait()
        except queue.Empty:
            break
        if item is _SHUTDOWN_SENTINEL:
            continue
        # route batchable inserts through the batching path.
        if isinstance(item, _BatchableInsert):
            try:
                db._drain_batchable_inserts(conn, item)
            except BaseException as e:  # noqa: BLE001
                with contextlib.suppress(sqlite3.Error):
                    conn.rollback()
                log.exception(
                    "[HISTORY_DB] Fire-and-forget batched insert failed during shutdown drain: %s",
                    e,
                )
            else:
                with contextlib.suppress(sqlite3.Error):
                    conn.rollback()
            continue
        callable_, future = item
        # (DRY): route through the same _execute_write_item
        _execute_write_item(db, conn, callable_, future)
