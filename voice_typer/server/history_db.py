"""SQLite database for storing transcription history.

Single-writer architecture: all write operations are
serialized through a single dedicated writer thread that owns the
*only* write-capable connection. Read operations use thread-local
read-only connections (WAL readers never block the writer).

Architecture overview::

    caller thread ──► HistoryDB.add_transcription ──► queue.Queue ──►
                                                                    │
                                                     writer thread (daemon)
                                                     owns 1 write conn
                                                     drains queue, runs
                                                     PRAGMA wal_checkpoint
                                                     every 300s
                                                     (controlled by
                                                     _WAL_CHECKPOINT_INTERVAL)

    caller thread ──► HistoryDB.get_recent ──► _get_read_conn (thread-local)
                                                PRAGMA query_only=1

Why this design exists (root cause from INV-A investigation):
- The previous thread-local-connections design had 3+ write-capable
  connections all contending for the same SQLite write lock. The
  retry helper (``_exec_with_retry``) compounded the problem: 5
  attempts × (busy_timeout + commit wait) + backoff ≈ 10s.
- A single writer thread eliminates in-process contention entirely.
  ``busy_timeout`` is now only a safety net for *external* writers
  (e.g. antivirus scans, external SQLite CLI), not for our own
  threads.
- ``add_transcription`` is fire-and-forget: it enqueues and returns
  immediately with a placeholder row_id, eliminating the user-reported
  5.5s ``store`` delay on the transcription pipeline's critical path.

Sentinel contract. Every public method returns a fixed
sentinel on error, matching the *success-shape* of the method's
normal return:

- List-returning methods (get_recent, search, get_favorites) → ``[]``
- Bool-returning methods (delete, clear_all, toggle_favorite,
  apply_retention) → ``False``
- Dict-returning methods (get_stats, get_today_stats) → empty dict
  (with the documented keys present, set to 0)
- add_transcription → ``-1`` (caller checks ``<= 0``)

Callers detect failure by checking the specific sentinel of the
method they called. Hard failures (corruption, locked DB) additionally
log at ``log.error`` level.
"""

import contextlib
import logging
import queue
import re
import sqlite3
import threading
import weakref
from pathlib import Path
from typing import Any

from voice_typer.server.history_db_internals import (  # noqa: F401, re-export surface: internals/tests resolve these through this module
    corruption_recovery,
    crud_writes,
    encryption,
    lifecycle,
    reader,
    retention,
    schema,
    search,
    writer,
)
from voice_typer.server.history_db_internals.decorators import (
    HistoryDBError,  # noqa: F401, re-exported: callers import HistoryDBError from this module
    _wrap_read,
    _wrap_write,
)
from voice_typer.server.history_db_internals.internal_api import HistoryDBInternals
from voice_typer.server.history_db_internals.retention import RetentionResult
from voice_typer.server.history_db_internals.write_payloads import (
    _BatchableInsert,  # noqa: F401, re-exported: tests build payloads via this name
)

log = logging.getLogger(__name__)


# O2: the SQLite history database lives under a dedicated ``db/``
DB_SUBDIR = "db"

_MAX_SEARCH_QUERY_CHARS = 200

# that never makes progress because of an external SQLite lock). 60s is
_WRITE_FUTURE_TOTAL_TIMEOUT = 60.0

#   _WAL_CHECKPOINT_INTERVAL, the writer thread runs
_WAL_CHECKPOINT_INTERVAL = 300.0  # 5 minutes, keeps WAL small with negligible overhead
_WRITE_FUTURE_TIMEOUT = 30.0
_WRITER_JOIN_TIMEOUT = 10.0
_WRITER_READY_TIMEOUT = 30.0
# clear_all uses a larger batch than retention because it unconditionally
_CLEAR_ALL_BATCH_SIZE = 1000

# PERF-5: maximum number of pending write closures enqueued on the
_WRITE_QUEUE_MAXSIZE = 10000

# Sentinel enqueued to ask the writer thread to drain and exit.
_SHUTDOWN_SENTINEL: Any = object()

# maximum number of transcription rows bundled into a single
_BATCH_INSERT_CAP = 100

# minimum number of pending _BatchableInsert items required to
_BATCH_INSERT_MIN = 1

# TTL (seconds) for the get_history_count cache.
_HISTORY_COUNT_CACHE_TTL_S = 60.0

# Interval (seconds) at which the periodic read-conn prune daemon
_READ_CONN_PRUNE_INTERVAL_S: float = 60.0

# TTL (seconds) for the ``get_today_stats`` cache.
_TODAY_STATS_CACHE_TTL_S = 15.0

# maximum characters of ``text`` returned in list responses.
_HISTORY_TEXT_PREVIEW_LENGTH = 500

# At-rest encryption: number of pre-existing plaintext rows converted to
_ENCRYPTION_BACKFILL_BATCH = 100

# hard upper bound on the ``limit`` parameter for the public list
_MAX_LIST_LIMIT = 500

# regex used by ``HistoryDB._try_iterdump_recovery`` to
_INSERT_TRANSCRIPTIONS_RE = re.compile(
    r'^INSERT\s+INTO\s+"?transcriptions"?\b',
    re.IGNORECASE,
)


# Query + DB-safety helpers re-exported after the facade's own imports so
# ``history_db._sanitize_fts_query`` etc. keep resolving for callers/tests.
import voice_typer.server.history_db_internals.search as _search_helpers  # noqa: E402,F401, backward-compat re-export
from voice_typer.server.history_db_internals.corruption_recovery import (  # noqa: E402,F401, backward-compat re-export
    _maybe_migrate_legacy_db,
    _maybe_move_legacy_sidecar,
    _secure_copy_db_file,
)
from voice_typer.server.history_db_internals.schema import (  # noqa: E402,F401, backward-compat re-export so tests reading history_db._MIGRATIONS / _CURRENT_SCHEMA_VERSION keep working
    _CURRENT_SCHEMA_VERSION,
    _MIGRATION_V2,
    _MIGRATION_V3,
    _MIGRATION_V4,
    _MIGRATIONS,
)

_is_fts_compatible_query = _search_helpers.is_fts_compatible_query
_has_cjk_or_wide_chars = _search_helpers.has_cjk_or_wide_chars
_prepare_like_search_pattern = _search_helpers.prepare_like_search_pattern
_project_text_row = _search_helpers.project_text_row
_sanitize_fts_query = _search_helpers.sanitize_fts_query


# module-level WeakSet tracking all live HistoryDB instances. Tests
_LIVE_INSTANCES: "weakref.WeakSet[HistoryDB]" = weakref.WeakSet()


class HistoryDB(HistoryDBInternals):
    """Thread-safe SQLite database for transcription history.

    Single-writer architecture: a dedicated writer thread owns
    the only write-capable connection and drains a bounded queue of
    write closures serially; reads use thread-local read-only
    connections (WAL, readers never block the writer).
    ``add_transcription`` is fire-and-forget; other write methods block
    on a ``Future`` so callers see the result.

    Method bodies live in ``history_db_internals.*`` (free functions
    taking the instance); this class keeps the public/patch surface —
    every delegate reads its implementation through the module
    attribute at call time, so monkeypatching keeps working.
    """

    # Assigned by history_db_internals.lifecycle.initialize_state (from
    db_path: Path
    _read_local: threading.local
    _all_read_connections: list[tuple[int, sqlite3.Connection]]
    _connections_lock: threading.Lock
    _read_conn_generation: int
    _queue: "queue.Queue[Any]"
    _writer_ready: threading.Event
    _shutdown: threading.Event
    _init_error: BaseException | None
    _retention_lock: threading.Lock
    _retention_stop_event: threading.Event | None
    _retention_thread: threading.Thread | None
    _history_count_cache: int | None
    _history_count_cache_ts: float
    _history_count_cache_lock: threading.Lock
    _today_stats_cache: dict | None
    _today_stats_cache_ts: float
    _today_stats_cache_lock: threading.Lock
    _fts5_rebuild_failures: int
    _fts5_rebuild_ran: bool
    _fts_reindex_watermark: int
    _encryption_status: str
    _read_conn_prune_stop_event: threading.Event | None
    _read_conn_prune_thread: threading.Thread | None

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            from voice_typer.server.config import _config_dir

            config_dir = _config_dir()
            # O2: one-time legacy root-DB migration into db/ BEFORE the
            _maybe_migrate_legacy_db(config_dir)
            db_path = config_dir / DB_SUBDIR / "history.db"

        self.db_path = db_path
        # Stateful attribute setup (lifecycle.initialize_state reads
        lifecycle.initialize_state(self)
        # Start the writer thread last, it signals _writer_ready once
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="HistoryDBWriter",
            daemon=True,
        )
        self._writer_thread.start()
        lifecycle.wait_for_writer_ready(self)

    def encryption_status(self) -> str:
        """At-rest-encryption state of this DB: see internals.encryption.encryption_status."""
        return encryption.encryption_status(self)

    def flush(self) -> None:
        """block until all queued writes have been processed, delegates to internals.writer.flush."""
        writer.flush(self)

    def __del__(self):
        """Close read connections on GC to prevent ResourceWarning.

        Lifecycle note: does NOT call ``close()`` (which joins the writer thread
        with a 10s timeout). If a HistoryDB instance was GC'd while the
        writer was stuck mid-VACUUM or blocked by an antivirus-locked
        WAL, the GC pause blocked for up to 10s. The writer is a daemon
        thread and will exit at process termination regardless; here we
        only signal ``_shutdown`` so its inner loop exits on the next
        iteration, and close the read connections (the ResourceWarning
        we actually care about). ``close()`` (called explicitly by the
        app shutdown path) still does the full writer drain + join.
        """
        with contextlib.suppress(Exception):
            # Signal the writer to exit on its next iteration. The
            self._shutdown.set()
            # Sweep _all_read_connections (thread-local first). Never
            lifecycle.gc_close_read_connections(self)

    def close(self):
        """Shut down the writer thread and close all connections (idempotent).

        Delegates to internals.lifecycle.close_db (retention thread +
        prune daemon stop, shutdown sentinel, writer drain + join,
        read-connection teardown).
        """
        lifecycle.close_db(self)

    def add_transcription(
        self,
        text: str,
        duration: float = 0,
        model: str = "",
        device: str = "",
        language: str = "",
    ) -> int:
        """Add a transcription (fire-and-forget): enqueue + placeholder row_id.

        Delegates to internals.crud_writes.add_transcription (writer
        liveness guard included).
        """
        return crud_writes.add_transcription(
            self,
            text,
            duration=duration,
            model=model,
            device=device,
            language=language,
        )

    @_wrap_write(False, "delete transcription", "delete")
    def delete(self, transcription_id: int, *, raise_on_error: bool = False) -> bool:
        """Delete a transcription by ID.

        ``raise_on_error=True`` raises ``HistoryDBError`` instead of
        returning ``False``. Delegates to
        internals.crud_writes.submit_delete (DELETE + FTS5 'optimize'
        purge, cache invalidation).
        """
        return crud_writes.submit_delete(self, transcription_id)

    @_wrap_write(-1, "restore transcription", "restore")
    def restore(
        self,
        record: dict,
        *,
        raise_on_error: bool = False,
    ) -> int:
        """Re-insert a previously-deleted transcription record (Undo toast).

        ``record`` is the dict shape returned by ``get_recent``.
        Delegates to internals.crud_writes.submit_restore.
        """
        return crud_writes.submit_restore(self, record)

    @_wrap_write(False, "clear transcriptions", "clear_all")
    def clear_all(self, *, raise_on_error: bool = False) -> bool:
        """Clear all transcriptions (GDPR Art. 17 irreversible wipe).

        Delegates to internals.crud_writes.submit_clear_all (chunked
        DELETE + VACUUM + FTS5 'rebuild', cache invalidation).
        """
        return crud_writes.submit_clear_all(self)

    @_wrap_write(False, "toggle favorite", "toggle_favorite")
    def toggle_favorite(self, transcription_id: int, *, raise_on_error: bool = False) -> bool:
        """Toggle the favorite status of a transcription.

        Delegates to internals.crud_writes.submit_toggle_favorite.
        """
        return crud_writes.submit_toggle_favorite(self, transcription_id)

    def apply_retention(
        self,
        retention_days: int = 0,
        max_entries: int = 0,
        retention_count: int = 0,
    ) -> "RetentionResult":
        """Apply retention policy: delete old entries.

        Returns a :class:`RetentionResult`: an ``int`` subclass whose
        value is the deleted-row count and whose ``fts5_rebuild_ok``
        attribute reports the post-sweep FTS5 rebuild outcome.
        Delegates to internals.retention.apply_retention.
        """
        return retention.apply_retention(
            self,
            retention_days=retention_days,
            max_entries=max_entries,
            retention_count=retention_count,
        )

    def schedule_periodic_retention(
        self,
        interval_s: float = 600.0,
        app: Any = None,
        *,
        retention_days: int = 0,
        max_entries: int = 0,
        retention_count: int = 0,
    ) -> None:
        """Spawn the periodic retention daemon thread, see internals.retention.schedule_periodic_retention."""
        retention.schedule_periodic_retention(
            self,
            interval_s=interval_s,
            app=app,
            retention_days=retention_days,
            max_entries=max_entries,
            retention_count=retention_count,
        )

    @_wrap_read([], "get recent transcriptions")
    def get_recent(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        raise_on_error: bool = False,
        before_timestamp: str | None = None,
        before_id: int | None = None,
    ) -> list[dict]:
        """Get recent transcriptions with pagination.

        ``raise_on_error=True`` raises ``HistoryDBError`` instead of
        returning ``[]``; rows carry a 500-char ``text`` preview plus
        ``text_truncated`` / ``text_full_length``. Delegates to
        internals.search.get_recent (keyset cursor args).
        """
        return search.get_recent(self, limit, offset, before_timestamp=before_timestamp, before_id=before_id)

    def get_latest_text(self) -> str:
        """Return the most recent transcription text ("" when empty).

        Ordered by the autoincrement PK (DESC); call ``flush()`` after
        ``add_transcription()``. Delegates to
        internals.search.get_latest_text.
        """
        return search.get_latest_text(self)

    @_wrap_read([], "search transcriptions")
    def search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        *,
        raise_on_error: bool = False,
        before_timestamp: str | None = None,
        before_id: int | None = None,
    ) -> list[dict]:
        """Search transcriptions by text with pagination.

        Delegates to internals.search.search (FTS5 for tokenizable
        queries, LIKE fallback for separator-only and CJK/fullwidth
        queries).
        """
        return search.search(self, query, limit, offset, before_timestamp=before_timestamp, before_id=before_id)

    @_wrap_read([], "get favorites")
    def get_favorites(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        raise_on_error: bool = False,
        before_timestamp: str | None = None,
        before_id: int | None = None,
    ) -> list[dict]:
        """get favorited transcriptions with pagination, delegates to internals.search.get_favorites."""
        return search.get_favorites(self, limit, offset, before_timestamp=before_timestamp, before_id=before_id)

    @_wrap_read(lambda: {"count": 0, "chars": 0, "word_count": 0, "duration": 0}, "get today stats")
    def get_today_stats(self, *, raise_on_error: bool = False) -> dict:
        """get statistics for today's transcriptions (15s TTL cache), delegates to internals.search.get_today_stats."""
        return search.get_today_stats(self)

    def get_transcription_text(
        self,
        transcription_id: int,
        *,
        raise_on_error: bool = False,
    ) -> dict:
        """Return the FULL ``text`` of a single transcription row.

        Companion to the 500-char preview in list responses; returns
        ``{"id": int, "text": str}``. Delegates to
        internals.search.get_transcription_text.
        """
        return search.get_transcription_text(self, transcription_id, raise_on_error=raise_on_error)

    def get_history_count(self, *, raise_on_error: bool = False) -> int:
        """Return the total number of transcription rows (60s TTL cache).

        Invalidated on delete/clear_all/restore/apply_retention but NOT
        on fire-and-forget ``add_transcription``. Delegates to
        internals.search.get_history_count.
        """
        return search.get_history_count(self, raise_on_error=raise_on_error)

    def checkpoint(self, truncate: bool = True) -> bool:
        """Run ``PRAGMA wal_checkpoint(TRUNCATE|RESTART)`` (GDPR delete/export).

        Returns ``True`` when the checkpoint completed without error.
        Delegates to internals.crud_writes.submit_checkpoint.
        """
        return crud_writes.submit_checkpoint(self, truncate)

    def health_check(self) -> dict:
        """Return a health status dict for diagnostics.

        ``{"ok": bool, "error": str | None}``: ``ok`` is True only if
        the writer is alive, schema init succeeded, and init finished.
        Delegates to internals.lifecycle.health_check.
        """
        return lifecycle.health_check(self)
