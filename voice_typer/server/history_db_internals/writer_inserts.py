"""Batchable-INSERT path of the history writer thread.

Builds the INSERT statements, encrypts freshly inserted rows at rest, and
drains pending ``_BatchableInsert`` payloads into one transaction.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import logging
import queue
import sqlite3
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from voice_typer.server.history_db import HistoryDB

log = logging.getLogger(__name__)

def _encrypt_batch_rows(
    cursor: sqlite3.Cursor,
    batch: list[Any],
    last_row_id: int | None,
) -> None:
    """At-rest-encryption write side (ADR §2/§6; cipher module
    ``voice_typer/server/_text_crypto.py``). The rows were just inserted
    """
    from voice_typer.server import _text_crypto

    dek = _text_crypto.get_dek_cached()
    if dek is None or last_row_id is None:
        # absent, C-DATA-1 / ADR §9.1).
        return
    n = len(batch)
    for i, it in enumerate(batch):
        row_id = last_row_id - n + 1 + i
        cipher = _text_crypto.encrypt_text(it.text, dek)
        cursor.execute(
            "UPDATE transcriptions SET text = ?, text_is_encrypted = 1 WHERE id = ?",
            (cipher, row_id),
        )
        if cursor.rowcount != 1:
            log.error(
                "[HISTORY_DB] encryption flag-flip UPDATE matched %d rows for "
                "id=%d (expected 1), row may remain PLAINTEXT on disk",
                cursor.rowcount,
                row_id,
            )


# Single source for the transcription INSERT SQL (multi-row batch path
_INSERT_SQL_COLUMNS = "(text, duration, model, device, word_count, char_count, language)"
_INSERT_SQL_ROW_PLACEHOLDERS = "(?, ?, ?, ?, ?, ?, ?)"


def _build_insert_sql(row_count: int) -> str:
    """``row_count == 1`` yields the exact statement the single-row
    fallback executes; ``row_count >= 2`` yields the multi-row form
    """
    values = ",".join([_INSERT_SQL_ROW_PLACEHOLDERS] * row_count)
    return f"INSERT INTO transcriptions {_INSERT_SQL_COLUMNS} VALUES {values}"


def _drain_batchable_inserts(
    db: HistoryDB,
    conn: sqlite3.Connection,
    first_item: Any,
) -> None:
    """Called from :meth:`_writer_loop` (and :meth:`_drain_remaining`
    during shutdown) when the writer pulls a ``_BatchableInsert``
    """
    from voice_typer.server import history_db as _hd

    _SHUTDOWN_SENTINEL = _hd._SHUTDOWN_SENTINEL  # noqa: N806
    _BatchableInsert = _hd._BatchableInsert  # noqa: N806
    _BATCH_INSERT_CAP = _hd._BATCH_INSERT_CAP  # noqa: N806
    _BATCH_INSERT_MIN = _hd._BATCH_INSERT_MIN  # noqa: N806

    batch: list[Any] = [first_item]
    while len(batch) < _BATCH_INSERT_CAP:
        try:
            item = db._queue.get_nowait()
        except queue.Empty:
            break
        if item is _SHUTDOWN_SENTINEL:
            # Put the sentinel back so the main loop sees it and
            with contextlib.suppress(queue.Full):
                db._queue.put_nowait(item)
            break
        if isinstance(item, _BatchableInsert):
            batch.append(item)
        else:
            # Non-batchable item, put it back for the main loop.
            with contextlib.suppress(queue.Full):
                db._queue.put_nowait(item)
            break

    try:
        with contextlib.closing(conn.cursor()) as cursor:
            if len(batch) >= _BATCH_INSERT_MIN:
                # multi-row INSERT inside one transaction.
                params: list[Any] = []
                for it in batch:
                    params.extend(
                        (
                            it.text,
                            it.duration,
                            it.model,
                            it.device,
                            it.word_count,
                            it.char_count,
                            it.language,
                        )
                    )
                # The INSERT always carries PLAINTEXT (the FTS AFTER-INSERT
                cursor.execute(
                    _build_insert_sql(len(batch)),
                    params,
                )
                last_row_id = cursor.lastrowid
                _encrypt_batch_rows(cursor, batch, last_row_id)
                conn.commit()
                # Each future must resolve with ITS OWN row id. The rows were
                # inserted contiguously, so the batch's ids are
                # ``last_row_id - n + 1 ..= last_row_id`` (same arithmetic the
                # encrypt-batch helper uses).
                batch_size = len(batch)
                for offset, it in enumerate(batch):
                    if it.future is None:
                        continue
                    row_id = last_row_id - batch_size + 1 + offset if last_row_id is not None else -1
                    with contextlib.suppress(concurrent.futures.InvalidStateError):
                        it.future.set_result(row_id)
                log.debug(
                    "[HISTORY_DB] batched %d transcription INSERTs into one transaction",
                    len(batch),
                )
            else:
                # Below the batching threshold, insert each row
                for it in batch:
                    cursor.execute(
                        _build_insert_sql(1),
                        (
                            it.text,
                            it.duration,
                            it.model,
                            it.device,
                            it.word_count,
                            it.char_count,
                            it.language,
                        ),
                    )
                    row_id = cursor.lastrowid
                    _encrypt_batch_rows(cursor, [it], row_id)
                    conn.commit()
                    if it.future is not None:
                        with contextlib.suppress(concurrent.futures.InvalidStateError):
                            it.future.set_result(row_id if row_id is not None else -1)
                    if row_id is not None:
                        log.debug("Added transcription %d: %d chars", row_id, it.char_count)
    except BaseException as e:  # noqa: BLE001, propagate to futures
        # Resolve all futures with the exception so wait=True
        for it in batch:
            if it.future is not None:
                with contextlib.suppress(concurrent.futures.InvalidStateError):
                    it.future.set_exception(e)
        # Re-raise so the caller (_writer_loop / _drain_remaining)
        raise
