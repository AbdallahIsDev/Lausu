"""Schema-v6 optional history metadata: fresh DB, upgrade, round-trip."""

from __future__ import annotations

import sqlite3

import pytest
from voice_typer.server.history_db import HistoryDB
from voice_typer.server.history_db_internals.schema import _CURRENT_SCHEMA_VERSION

NEW_COLUMNS = (
    "kind",
    "source_type",
    "source_title",
    "source_url",
    "file_name",
    "thumbnail_url",
    "media_duration_seconds",
    "processing_seconds",
    "download_seconds",
    "method",
)


def _columns(conn: sqlite3.Connection) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(transcriptions)").fetchall()}


def _version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()
    return int(row[0]) if row else 1


def _make_v5_db(db_path) -> None:
    """A pre-v6 DB with one old row (no metadata columns)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE transcriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            duration REAL DEFAULT 0,
            model TEXT DEFAULT '',
            device TEXT DEFAULT '',
            word_count INTEGER DEFAULT 0,
            char_count INTEGER DEFAULT 0,
            favorite INTEGER DEFAULT 0,
            language TEXT DEFAULT '',
            text_is_encrypted BOOLEAN DEFAULT 0
        )
        """
    )
    conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO schema_meta (key, value) VALUES ('version', '5')")
    conn.execute("INSERT INTO transcriptions (text, duration, model) VALUES ('an old dictation', 2.5, 'small.en')")
    conn.commit()
    conn.close()


class TestSchemaV6Migration:
    def test_fresh_db_has_all_metadata_columns_and_keeps_fts_triggers(self, tmp_path):
        db_path = tmp_path / "fresh.db"
        db = HistoryDB(db_path=db_path)
        assert db._init_error is None
        db.close()

        conn = sqlite3.connect(str(db_path))
        try:
            assert _version(conn) == _CURRENT_SCHEMA_VERSION == 6
            assert set(NEW_COLUMNS) <= _columns(conn)
            triggers = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
            }
            assert {"transcriptions_ai_fts", "transcriptions_ad_fts", "transcriptions_au_fts"} <= triggers
        finally:
            conn.close()

    def test_upgrade_v5_old_rows_read_as_dictation(self, tmp_path):
        db_path = tmp_path / "upgrade.db"
        _make_v5_db(db_path)
        db = HistoryDB(db_path=db_path)
        assert db._init_error is None, db._init_error
        rows = db.get_recent(limit=10)
        assert len(rows) == 1
        row = rows[0]
        assert row["kind"] == "dictation"
        for name in NEW_COLUMNS:
            if name == "kind":
                continue
            assert row[name] is None, f"{name} should be NULL on an old row, got {row[name]!r}"
        # The generic duration is preserved, not replaced by media metadata.
        assert row["duration"] == 2.5
        db.close()

        conn = sqlite3.connect(str(db_path))
        try:
            assert _version(conn) == _CURRENT_SCHEMA_VERSION
            assert set(NEW_COLUMNS) <= _columns(conn)
        finally:
            conn.close()


class TestMetadataRoundTrip:
    @pytest.fixture
    def db(self, tmp_path):
        instance = HistoryDB(db_path=tmp_path / "metadata.db")
        yield instance
        instance.close()

    def test_full_media_metadata_survives_insert_and_projection(self, db):
        row_id = db.add_transcription(
            "hello from a video",
            duration=42.0,
            model="whisper/small.en",
            device="cuda",
            kind="media",
            source_type="youtube",
            source_title="A talk",
            source_url="https://www.youtube.com/watch?v=abc",
            file_name=None,
            thumbnail_url="data:image/jpeg;base64,AAAA",
            media_duration_seconds=42.0,
            processing_seconds=8.25,
            download_seconds=3.5,
            method="transcription",
        )
        assert row_id > 0
        db.flush()
        row = db.get_recent(limit=1)[0]
        expected = {
            "kind": "media",
            "source_type": "youtube",
            "source_title": "A talk",
            "source_url": "https://www.youtube.com/watch?v=abc",
            "file_name": None,
            "thumbnail_url": "data:image/jpeg;base64,AAAA",
            "media_duration_seconds": 42.0,
            "processing_seconds": 8.25,
            "download_seconds": 3.5,
            "method": "transcription",
        }
        for key, value in expected.items():
            assert row[key] == value, f"{key}: {row[key]!r} != {value!r}"
        # Shared word-count helper keeps History and the event on one source.
        assert row["word_count"] == 4

    def test_omitted_metadata_defaults_to_dictation_and_nulls(self, db):
        db.add_transcription("plain dictation", duration=1.0, model="small.en")
        db.flush()
        row = db.get_recent(limit=1)[0]
        assert row["kind"] == "dictation"
        for name in NEW_COLUMNS:
            if name == "kind":
                continue
            assert row[name] is None, f"{name}: {row[name]!r}"
