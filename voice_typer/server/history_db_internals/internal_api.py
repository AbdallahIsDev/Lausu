"""Private delegation seams of the :class:`HistoryDB` facade.

``HistoryDB`` inherits these so the per-method monkeypatch surface the
internals and tests rely on keeps resolving; the public API stays on the
facade class.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from voice_typer.server.history_db_internals import (
    corruption_recovery,
    encryption,
    reader,
    retention,
    schema,
    search,
    writer,
)
from voice_typer.server.history_db_internals.write_payloads import _BatchableInsert

if TYPE_CHECKING:
    # Self-type only: these seams are invoked on a HistoryDB and hand ``self``
    # to free functions typed ``db: HistoryDB``. Never imported at runtime.
    from voice_typer.server.history_db import HistoryDB


class HistoryDBInternals:
    """Private delegation seams of the :class:`HistoryDB` facade.

    Requires the host's private state, declared as class-level annotations
    on ``HistoryDB``: ``db_path``, ``_queue``, ``_shutdown``,
    ``_writer_thread``, ``_writer_ready``, ``_init_error``, ``_read_local``,
    ``_all_read_connections``, ``_connections_lock``, ``_read_conn_*``,
    ``_retention_*``, ``_today_stats_cache*``, ``_history_count_cache*``,
    ``_fts5_rebuild_*``, ``_encryption_status``. Each method annotates
    ``self`` as ``HistoryDB`` so the delegation calls type-check.
    """

    def _start_read_conn_prune_thread(self: HistoryDB) -> None:
        """Start the prune daemon: see internals.reader._start_read_conn_prune_thread."""
        reader._start_read_conn_prune_thread(self)

    # Back-compat alias for the previous name (kept so external code
    _start_periodic_read_conn_prune = _start_read_conn_prune_thread

    def _stop_read_conn_prune_thread(self: HistoryDB) -> None:
        """Stop the prune daemon: see internals.reader._stop_read_conn_prune_thread."""
        reader._stop_read_conn_prune_thread(self)

    # Back-compat alias for the previous name.
    _stop_periodic_read_conn_prune = _stop_read_conn_prune_thread

    def _periodic_read_conn_prune_loop(self: HistoryDB) -> None:
        """Prune loop body (daemon thread): see internals.reader._periodic_read_conn_prune_loop."""
        reader._periodic_read_conn_prune_loop(self)

    def _writer_loop(self: HistoryDB) -> None:
        """Drain the write queue serially: see internals.writer._writer_loop."""
        writer._writer_loop(self)

    def _execute_write_item(
        self: HistoryDB,
        conn: sqlite3.Connection,
        callable_: Callable[[sqlite3.Connection], Any],
        future: concurrent.futures.Future | None,
    ) -> None:
        """Execute one write closure, resolve its future, see internals.writer._execute_write_item."""
        writer._execute_write_item(self, conn, callable_, future)

    def _drain_batchable_inserts(
        self: HistoryDB,
        conn: sqlite3.Connection,
        first_item: _BatchableInsert,
    ) -> None:
        """Drain batchable INSERTs into one transaction, see internals.writer._drain_batchable_inserts."""
        writer._drain_batchable_inserts(self, conn, first_item)

    def _drain_remaining(self, conn: sqlite3.Connection) -> None:
        """Drain queued items before shutdown: see internals.writer._drain_remaining."""
        writer._drain_remaining(self, conn)

    def _run_checkpoint(self, conn: sqlite3.Connection) -> None:
        """Passive WAL checkpoint on the checkpoint-interval cadence, see internals.writer._run_checkpoint."""
        writer._run_checkpoint(self, conn)

    def _open_write_conn(self: HistoryDB) -> sqlite3.Connection:
        """Open the writer connection: see internals.schema.open_write_conn."""
        return schema.open_write_conn(self.db_path)

    def _check_wal_mode(self, conn: sqlite3.Connection) -> None:
        """Verify WAL mode is enabled (warn on fallback), see internals.schema.check_wal_mode."""
        schema.check_wal_mode(conn, self.db_path)

    def _init_db_schema(
        self: HistoryDB,
        conn: sqlite3.Connection,
        _is_recovery: bool = False,
    ) -> sqlite3.Connection:
        """Initialize schema + migrations, then the FTS5 startup sweep.

        Delegates to internals.schema.init_schema; on success runs the
        best-effort :meth:`_fts5_startup_rebuild` once. The FTS5 gate
        stays in the facade: the corruption-recovery path
        (``_apply_recovered_inserts``) calls ``init_schema`` directly
        with ``_is_recovery=True`` and must NOT trigger an extra sweep.
        """
        new_conn = schema.init_schema(self, conn, _is_recovery=_is_recovery)
        if self._init_error is None:
            with contextlib.suppress(Exception):
                self._fts5_startup_rebuild(new_conn)
        return new_conn

    def _fts5_startup_rebuild(self, conn: sqlite3.Connection) -> None:
        """Best-effort FTS5 'rebuild' on a persisted failure flag, see internals.writer._fts5_startup_rebuild."""
        writer._fts5_startup_rebuild(self, conn)

    def _init_encryption(self, conn: sqlite3.Connection) -> None:
        """Resolve the DEK once per process + kick the backfill, see internals.encryption._init_encryption."""
        encryption._init_encryption(self, conn)

    def _has_encrypted_rows(self, conn: sqlite3.Connection) -> bool:
        """Report whether any row is flagged encrypted, see internals.encryption._has_encrypted_rows."""
        return encryption._has_encrypted_rows(self, conn)

    def _has_plaintext_rows(self, conn: sqlite3.Connection) -> bool:
        """Report whether any non-empty row is still plaintext, see internals.encryption._has_plaintext_rows."""
        return encryption._has_plaintext_rows(self, conn)

    def _enqueue_backfill_step(self: HistoryDB) -> None:
        """Queue one backfill batch: see internals.encryption._enqueue_backfill_step."""
        encryption._enqueue_backfill_step(self)

    def _encrypt_backfill_step(self, conn: sqlite3.Connection) -> int:
        """Encrypt one bounded backfill batch: see internals.encryption._encrypt_backfill_step."""
        return encryption._encrypt_backfill_step(self, conn)

    def _enqueue_reindex_step(self: HistoryDB) -> None:
        """Queue one bounded decrypt-aware FTS re-index batch, see internals.encryption._enqueue_reindex_step."""
        encryption._enqueue_reindex_step(self)

    def _reindex_encrypted_fts_step(self, conn: sqlite3.Connection) -> int:
        """Restore plaintext FTS tokens for encrypted rows, see internals.encryption._reindex_encrypted_fts_step."""
        return encryption._reindex_encrypted_fts_step(self, conn)

    def _mark_fts5_rebuild_failed(self, conn: sqlite3.Connection) -> None:
        """Persist the fts5_rebuild_failed flag: see internals.encryption._mark_fts5_rebuild_failed."""
        encryption._mark_fts5_rebuild_failed(self, conn)

    def _backup_before_migration(self, current_version: int) -> None:
        """Best-effort pre-migration backup: see internals.corruption_recovery._backup_before_migration."""
        corruption_recovery._backup_before_migration(self, current_version)

    def _maybe_recover_from_corruption(
        self: HistoryDB,
        conn: sqlite3.Connection,
    ) -> sqlite3.Connection | None:
        """Corruption gate + fresh DB: see internals.corruption_recovery._maybe_recover_from_corruption."""
        return corruption_recovery._maybe_recover_from_corruption(self, conn)

    def _try_iterdump_recovery(self, old_db_path: Path) -> list[str]:
        """Recover user-data INSERTs from the corrupt DB, see internals.corruption_recovery._try_iterdump_recovery."""
        return corruption_recovery._try_iterdump_recovery(self, old_db_path)

    def _apply_recovered_inserts(
        self: HistoryDB,
        conn: sqlite3.Connection,
        inserts: list[str],
    ) -> int:
        """Replay recovered INSERTs on the fresh DB, see internals.corruption_recovery._apply_recovered_inserts."""
        return corruption_recovery._apply_recovered_inserts(self, conn, inserts)

    def _notify_corruption_recovered(
        self: HistoryDB,
        corrupt_main: Path,
        recovered_count: int,
    ) -> None:
        """Surface the corruption event to the user, see internals.corruption_recovery._notify_corruption_recovered."""
        corruption_recovery._notify_corruption_recovered(self, corrupt_main, recovered_count)

    def _get_read_conn(self: HistoryDB) -> sqlite3.Connection:
        """Get a thread-local READ-ONLY connection, see internals.reader._get_read_conn."""
        return reader._get_read_conn(self)

    def _prune_dead_read_connections_locked(self: HistoryDB) -> None:
        """Close dead-thread read connections: see internals.reader._prune_dead_read_connections_locked."""
        reader._prune_dead_read_connections_locked(self)

    def _get_conn(self: HistoryDB) -> sqlite3.Connection:
        """Backwards-compat alias for ``_get_read_conn``, delegates to internals.reader._get_conn."""
        return reader._get_conn(self)

    def _drop_oldest_for_overflow(self, current_future: concurrent.futures.Future | None) -> None:
        """Drop oldest queued item to make room: see internals.writer._drop_oldest_for_overflow."""
        writer._drop_oldest_for_overflow(self, current_future)

    def _submit_write(
        self: HistoryDB,
        fn: Callable[[sqlite3.Connection], Any],
        *,
        wait: bool = True,
        allow_after_shutdown: bool = False,
    ) -> Any | None:
        """submit a write closure to the writer thread, delegates to internals.writer._submit_write."""
        return writer._submit_write(self, fn, wait=wait, allow_after_shutdown=allow_after_shutdown)

    def _close_writer(self: HistoryDB) -> None:
        """Writer-teardown portion of :meth:`close`: delegates to internals.writer._close_writer."""
        writer._close_writer(self)

    def _stop_periodic_retention(self: HistoryDB) -> None:
        """Signal + join the periodic retention thread, see internals.retention.stop_periodic_retention."""
        retention.stop_periodic_retention(self)

    def _invalidate_today_stats_cache(self: HistoryDB) -> None:
        """Drop the cached today-stats dict: see internals.search.invalidate_today_stats_cache."""
        search.invalidate_today_stats_cache(self)

    def _invalidate_history_count_cache(self: HistoryDB) -> None:
        """drop the cached total-count int, delegates to internals.search.invalidate_history_count_cache."""
        search.invalidate_history_count_cache(self)
