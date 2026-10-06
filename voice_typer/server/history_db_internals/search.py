"""History search (FTS router + LIKE fallback)."""

from __future__ import annotations

import contextlib
import logging
import time
from typing import TYPE_CHECKING

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.history_db_internals.search_projection import (  # noqa: F401, re-exported: the facade aliases + read paths resolve these here
    _LIST_COLUMNS_SQL,
    _LIST_COLUMNS_T_SQL,
    _decrypt_full_text,
    _finalize_text_rows,
    project_text_row,
)
from voice_typer.server.history_db_internals.search_query import (  # noqa: F401, re-exported: the facade aliases + read paths resolve these here
    _build_trigram_phrase,
    has_cjk_or_wide_chars,
    is_fts_compatible_query,
    is_trigram_cjk_query,
    prepare_like_search_pattern,
    sanitize_fts_query,
)

if TYPE_CHECKING:
    from voice_typer.server.history_db import HistoryDB

# Lazy proxy: ``history_db`` imports this package, so a direct import would be circular.
_hd = lazy_module("voice_typer.server.history_db")

log = logging.getLogger(__name__)

# Public read methods


def _assert_bounded_offset(offset: int) -> None:
    """Shared deep-OFFSET guard for every list path."""
    # Real raise, not assert: assert is stripped under python -O.
    from voice_typer.server.ipc.history_bounds import HISTORY_OFFSET_LIMIT, deep_offset_message

    if offset > HISTORY_OFFSET_LIMIT:
        raise ValueError(deep_offset_message(offset))


def get_recent(
    db: HistoryDB,
    limit: int = 50,
    offset: int = 0,
    *,
    before_timestamp: str | None = None,
    before_id: int | None = None,
) -> list[dict]:
    """Get recent transcriptions with offset-based pagination."""
    limit = min(max(limit, 1), _hd._MAX_LIST_LIMIT)
    conn = db._get_read_conn()
    with contextlib.closing(conn.cursor()) as cursor:
        use_cursor = before_timestamp is not None and before_id is not None
        if use_cursor:
            cursor.execute(
                f"""
                SELECT
                    {_LIST_COLUMNS_SQL}
                FROM transcriptions
                WHERE timestamp < ? OR (timestamp = ? AND id < ?)
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
            """,
                (
                    _hd._HISTORY_TEXT_PREVIEW_LENGTH,
                    before_timestamp,
                    before_timestamp,
                    before_id,
                    limit,
                ),
            )
        else:
            _assert_bounded_offset(offset)
            cursor.execute(
                f"""
                SELECT
                    {_LIST_COLUMNS_SQL}
                FROM transcriptions
                ORDER BY timestamp DESC, id DESC
                LIMIT ? OFFSET ?
            """,
                (_hd._HISTORY_TEXT_PREVIEW_LENGTH, limit, offset),
            )
        rows = cursor.fetchall()
    return _finalize_text_rows(conn, rows)


def get_latest_text(db: HistoryDB) -> str:
    """Return the most recent transcription text, or ``""`` if DB empty."""
    try:
        conn = db._get_read_conn()
        with contextlib.closing(conn.cursor()) as cur:
            cur.execute("SELECT text, text_is_encrypted FROM transcriptions ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
        if row is None:
            return ""
        if row[1]:
            return _decrypt_full_text(row[0] or "")
        return row[0] if row else ""
    except Exception as e:
        log.exception("[HISTORY] Failed to get latest transcription: %s", e)
        return ""


def search(
    db: HistoryDB,
    query: str,
    limit: int = 50,
    offset: int = 0,
    *,
    before_timestamp: str | None = None,
    before_id: int | None = None,
) -> list[dict]:
    """Search transcriptions by text with offset-based pagination."""
    limit = min(max(limit, 1), _hd._MAX_LIST_LIMIT)
    conn = db._get_read_conn()
    with contextlib.closing(conn.cursor()) as cursor:
        capped = query[: _hd._MAX_SEARCH_QUERY_CHARS]
        use_cursor = before_timestamp is not None and before_id is not None
        # CJK / fullwidth queries: the unicode61 index cannot substring-
        use_fts = bool(capped) and is_fts_compatible_query(capped) and not has_cjk_or_wide_chars(capped)
        use_trigram_cjk = bool(capped) and not use_fts and is_trigram_cjk_query(capped)
        if use_trigram_cjk:
            # Availability gate: on SQLite builds without the trigram
            from voice_typer.server.history_db_internals.schema import cjk_trigram_table_exists

            use_trigram_cjk = cjk_trigram_table_exists(conn)
        if use_trigram_cjk:
            trigram_query = _build_trigram_phrase(capped)
            if use_cursor:
                # Cursor path: no LIMIT push-down (the cursor WHERE
                cursor.execute(
                    f"""
                    SELECT
                        {_LIST_COLUMNS_T_SQL}
                    FROM transcriptions t
                    JOIN transcriptions_fts_cjk AS f ON f.rowid = t.id
                    WHERE transcriptions_fts_cjk MATCH ?
                      AND (t.timestamp < ? OR (t.timestamp = ? AND t.id < ?))
                    ORDER BY t.timestamp DESC, t.id DESC
                    LIMIT ?
                """,
                    (
                        _hd._HISTORY_TEXT_PREVIEW_LENGTH,
                        trigram_query,
                        before_timestamp,
                        before_timestamp,
                        before_id,
                        limit,
                    ),
                )
            else:
                # No-cursor path: push LIMIT (+ OFFSET) into the trigram
                _assert_bounded_offset(offset)
                fts_subquery_limit = limit + offset
                cursor.execute(
                    f"""
                    SELECT
                        {_LIST_COLUMNS_T_SQL}
                    FROM (
                        SELECT rowid
                        FROM transcriptions_fts_cjk
                        WHERE transcriptions_fts_cjk MATCH ?
                        ORDER BY rowid DESC
                        LIMIT ?
                    ) AS f
                    JOIN transcriptions t ON t.id = f.rowid
                    ORDER BY t.timestamp DESC, t.id DESC
                    LIMIT ? OFFSET ?
                """,
                    (
                        _hd._HISTORY_TEXT_PREVIEW_LENGTH,
                        trigram_query,
                        fts_subquery_limit,
                        limit,
                        offset,
                    ),
                )
        elif use_fts:
            fts_query = sanitize_fts_query(capped)
            if use_cursor:
                # Cursor path: cannot push LIMIT into FTS because the
                cursor.execute(
                    f"""
                    SELECT
                        {_LIST_COLUMNS_T_SQL}
                    FROM transcriptions t
                    JOIN transcriptions_fts AS f ON f.rowid = t.id
                    WHERE transcriptions_fts MATCH ?
                      AND (t.timestamp < ? OR (t.timestamp = ? AND t.id < ?))
                    ORDER BY t.timestamp DESC, t.id DESC
                    LIMIT ?
                """,
                    (
                        _hd._HISTORY_TEXT_PREVIEW_LENGTH,
                        fts_query,
                        before_timestamp,
                        before_timestamp,
                        before_id,
                        limit,
                    ),
                )
            else:
                # No-cursor path: push LIMIT (+ OFFSET) into the FTS
                _assert_bounded_offset(offset)
                fts_subquery_limit = limit + offset
                cursor.execute(
                    f"""
                    SELECT
                        {_LIST_COLUMNS_T_SQL}
                    FROM (
                        SELECT rowid
                        FROM transcriptions_fts
                        WHERE transcriptions_fts MATCH ?
                        ORDER BY rowid DESC
                        LIMIT ?
                    ) AS f
                    JOIN transcriptions t ON t.id = f.rowid
                    ORDER BY t.timestamp DESC, t.id DESC
                    LIMIT ? OFFSET ?
                """,
                    (
                        _hd._HISTORY_TEXT_PREVIEW_LENGTH,
                        fts_query,
                        fts_subquery_limit,
                        limit,
                        offset,
                    ),
                )
        else:
            # LIKE fallback.
            pattern = prepare_like_search_pattern(query)
            if use_cursor:
                cursor.execute(
                    f"""
                    SELECT
                        {_LIST_COLUMNS_SQL}
                    FROM transcriptions
                    WHERE text LIKE ? ESCAPE '\\'
                      AND (timestamp < ? OR (timestamp = ? AND id < ?))
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                """,
                    (
                        _hd._HISTORY_TEXT_PREVIEW_LENGTH,
                        pattern,
                        before_timestamp,
                        before_timestamp,
                        before_id,
                        limit,
                    ),
                )
            else:
                # LIKE fallback, OFFSET branch: same bounded-offset
                _assert_bounded_offset(offset)
                cursor.execute(
                    f"""
                    SELECT
                        {_LIST_COLUMNS_SQL}
                    FROM transcriptions
                    WHERE text LIKE ? ESCAPE '\\'
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ? OFFSET ?
                """,
                    (_hd._HISTORY_TEXT_PREVIEW_LENGTH, pattern, limit, offset),
                )
        rows = cursor.fetchall()
    return _finalize_text_rows(conn, rows)


def get_favorites(
    db: HistoryDB,
    limit: int = 50,
    offset: int = 0,
    *,
    before_timestamp: str | None = None,
    before_id: int | None = None,
) -> list[dict]:
    """Get favorited transcriptions with offset-based pagination."""
    limit = min(max(limit, 1), _hd._MAX_LIST_LIMIT)
    conn = db._get_read_conn()
    with contextlib.closing(conn.cursor()) as cursor:
        use_cursor = before_timestamp is not None and before_id is not None
        if use_cursor:
            cursor.execute(
                f"""
                SELECT
                    {_LIST_COLUMNS_SQL}
                FROM transcriptions
                WHERE favorite = 1
                  AND (timestamp < ? OR (timestamp = ? AND id < ?))
                ORDER BY timestamp DESC, id DESC
                LIMIT ?
            """,
                (
                    _hd._HISTORY_TEXT_PREVIEW_LENGTH,
                    before_timestamp,
                    before_timestamp,
                    before_id,
                    limit,
                ),
            )
        else:
            # Same bounded-offset contract as ``get_recent`` / ``search``:
            _assert_bounded_offset(offset)
            cursor.execute(
                f"""
                SELECT
                    {_LIST_COLUMNS_SQL}
                FROM transcriptions
                WHERE favorite = 1
                ORDER BY timestamp DESC, id DESC
                LIMIT ? OFFSET ?
            """,
                (_hd._HISTORY_TEXT_PREVIEW_LENGTH, limit, offset),
            )
        rows = cursor.fetchall()
    return _finalize_text_rows(conn, rows)


def get_today_stats(db: HistoryDB) -> dict:
    """Get statistics for today's transcriptions."""
    # check the cache first.
    now = time.monotonic()
    with db._today_stats_cache_lock:
        if db._today_stats_cache is not None and (now - db._today_stats_cache_ts) < _hd._TODAY_STATS_CACHE_TTL_S:
            # Return a shallow copy so callers can mutate the returned
            return dict(db._today_stats_cache)
    conn = db._get_read_conn()
    with contextlib.closing(conn.cursor()) as cursor:
        # Sargable predicate. ``DATE(timestamp) = DATE('now')`` applies
        cursor.execute("""
            SELECT
                COUNT(*) as count,
                SUM(char_count) as chars,
                SUM(word_count) as word_count,
                SUM(duration) as duration
            FROM transcriptions
            WHERE timestamp >= DATETIME('now', 'localtime', 'start of day', 'utc')
              AND timestamp < DATETIME('now', 'localtime', 'start of day', '+1 day', 'utc')
        """)
        row = cursor.fetchone()
    result = {
        "count": row[0] or 0,
        "chars": row[1] or 0,
        "word_count": row[2] or 0,
        "duration": row[3] or 0,
    }
    # store the result in the cache (under the lock so a concurrent
    with db._today_stats_cache_lock:
        db._today_stats_cache = result
        db._today_stats_cache_ts = time.monotonic()
    # Return a shallow copy on the cache-miss path too.
    return dict(result)


def invalidate_today_stats_cache(db: HistoryDB) -> None:
    """Drop the cached today-stats dict."""
    with db._today_stats_cache_lock:
        db._today_stats_cache = None
        db._today_stats_cache_ts = 0.0


def get_transcription_text(
    db: HistoryDB,
    transcription_id: int,
    *,
    raise_on_error: bool = False,
) -> dict:
    """Return the FULL ``text`` of a single transcription row."""
    try:
        conn = db._get_read_conn()
        with contextlib.closing(conn.cursor()) as cursor:
            cursor.execute(
                "SELECT text, text_is_encrypted FROM transcriptions WHERE id = ?",
                (transcription_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return {"id": transcription_id, "text": ""}
        text = row[0] or ""
        if row[1]:
            text = _decrypt_full_text(text)
        return {"id": transcription_id, "text": text}
    except Exception as e:
        log.exception(
            "[HISTORY] Failed to get transcription text for id=%s: %s",
            transcription_id,
            e,
        )
        if raise_on_error:
            raise _hd.HistoryDBError(str(e)) from e
        return {"id": transcription_id, "text": ""}


def get_history_count(
    db: HistoryDB,
    *,
    raise_on_error: bool = False,
) -> int:
    """Return the total number of transcription rows."""
    now = time.monotonic()
    with db._history_count_cache_lock:
        if db._history_count_cache is not None and (now - db._history_count_cache_ts) < _hd._HISTORY_COUNT_CACHE_TTL_S:
            return db._history_count_cache
    try:
        conn = db._get_read_conn()
        with contextlib.closing(conn.cursor()) as cursor:
            cursor.execute("SELECT COUNT(*) FROM transcriptions")
            row = cursor.fetchone()
        count = int(row[0]) if row is not None else 0
        with db._history_count_cache_lock:
            db._history_count_cache = count
            db._history_count_cache_ts = time.monotonic()
        return count
    except Exception as e:
        log.exception("[HISTORY] Failed to get history count: %s", e)
        if raise_on_error:
            raise _hd.HistoryDBError(str(e)) from e
        return 0


def invalidate_history_count_cache(db: HistoryDB) -> None:
    """Drop the cached total-count int."""
    with db._history_count_cache_lock:
        db._history_count_cache = None
        db._history_count_cache_ts = 0.0
