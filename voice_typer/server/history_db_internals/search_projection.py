"""Row projection and at-rest decryption for history read paths.

Turns raw SQLite rows into the renderer-facing dict shape (500-char text
preview + truncation flags) and decrypts flagged rows in Python.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3

log = logging.getLogger(__name__)


# Shared list projection
_LIST_COLUMNS_SQL = """id,
    SUBSTR(text, 1, ?) AS text,
    LENGTH(text) AS text_full_length,
    text_is_encrypted,
    timestamp,
    duration,
    model,
    device,
    word_count,
    char_count,
    favorite,
    language"""

_LIST_COLUMNS_T_SQL = """t.id,
    SUBSTR(t.text, 1, ?) AS text,
    LENGTH(t.text) AS text_full_length,
    t.text_is_encrypted,
    t.timestamp,
    t.duration,
    t.model,
    t.device,
    t.word_count,
    t.char_count,
    t.favorite,
    t.language"""


def project_text_row(row: sqlite3.Row | tuple) -> dict:
    """Post-process a SQLite row from get_recent/search/get_favorites."""
    from voice_typer.server import history_db as _hd

    d = dict(row)
    full_length = d.get("text_full_length")
    if full_length is None:
        full_length_int = 0
        truncated = False
    else:
        full_length_int = int(full_length)
        truncated = full_length_int > _hd._HISTORY_TEXT_PREVIEW_LENGTH
    d["text_truncated"] = truncated
    d["text_full_length"] = full_length_int
    d.pop("text_is_encrypted", None)
    return d


def _finalize_text_rows(conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[dict]:
    """Project rows and decrypt flagged-encrypted text in Python."""
    from voice_typer.server import _text_crypto, history_db as _hd

    # Capture the encryption flag from the RAW rows before projection —
    out: list[dict] = []
    flagged_ids: list[int] = []
    for row in rows:
        raw = dict(row)
        if raw.get("text_is_encrypted"):
            flagged_ids.append(int(raw["id"]))
        out.append(project_text_row(row))
    if not flagged_ids:
        # Common case (plaintext mode): zero extra work.
        return out
    dek = _text_crypto.get_dek_cached()
    flagged_set = set(flagged_ids)
    if dek is None:
        _text_crypto.log_key_unavailable_error()
        placeholder = _text_crypto.DECRYPTION_FAILED_PLACEHOLDER
        for d in out:
            if d["id"] in flagged_set:
                d["text"] = placeholder
                d["text_full_length"] = len(placeholder)
                d["text_truncated"] = False
        return out
    # Re-fetch the FULL ciphertext for the flagged rows only (the list
    full_texts: dict[int, str] = {}
    try:
        with contextlib.closing(conn.cursor()) as cursor:
            placeholders = ",".join(["?"] * len(flagged_ids))
            cursor.execute(
                f"SELECT id, text FROM transcriptions WHERE id IN ({placeholders})",
                flagged_ids,
            )
            full_texts = {int(r[0]): r[1] for r in cursor.fetchall()}
    except sqlite3.Error as e:
        log.warning(
            "[HISTORY] re-fetching encrypted row texts for decryption failed: %s",
            e,
        )
    preview_len = _hd._HISTORY_TEXT_PREVIEW_LENGTH
    for d in out:
        if d["id"] in flagged_set:
            plaintext = _text_crypto.decrypt_text(full_texts.get(d["id"], ""), dek)
            d["text"] = plaintext[:preview_len]
            d["text_full_length"] = len(plaintext)
            d["text_truncated"] = len(plaintext) > preview_len
    return out


def _decrypt_full_text(blob: str) -> str:
    """Decrypt a single flagged row's full text (never raises)."""
    from voice_typer.server import _text_crypto

    dek = _text_crypto.get_dek_cached()
    if dek is None:
        _text_crypto.log_key_unavailable_error()
        return _text_crypto.DECRYPTION_FAILED_PLACEHOLDER
    return _text_crypto.decrypt_text(blob, dek)
