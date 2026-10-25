"""Quiet offline probe misses: no traceback for expected cache misses."""

from __future__ import annotations

import logging
import threading

import pytest
import voice_typer.server.transcription_download as td
from huggingface_hub.errors import (
    CacheNotFound,
    IncompleteSnapshotError,
    LocalEntryNotFoundError,
)

_LOGGER = "voice_typer.server.transcription"


def _miss_records(caplog: pytest.LogCaptureFixture) -> list:
    return [r for r in caplog.records if "probe miss" in r.message or "probe failed" in r.message]


class TestProbeCacheQuietMiss:
    def test_incomplete_snapshot_logs_concise_line_without_traceback(self, caplog):
        def fake_snapshot(**kwargs):
            raise IncompleteSnapshotError("cached snapshot is incomplete: 1 files missing", snapshot_path="/x")

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            local_dir, integrity_failed = td.probe_cache(object(), fake_snapshot, "org/repo", "main", [], "tiny")
        assert (local_dir, integrity_failed) == (None, False)
        assert len(_miss_records(caplog)) == 1
        assert _miss_records(caplog)[0].exc_info is None
        assert "Traceback" not in caplog.text

    def test_unexpected_error_keeps_traceback(self, caplog):
        def fake_snapshot(**kwargs):
            raise RuntimeError("disk on fire")

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            assert td.probe_cache(object(), fake_snapshot, "org/repo", "main", [], "tiny") == (None, False)
        assert len(_miss_records(caplog)) == 1
        assert _miss_records(caplog)[0].exc_info is not None


class TestWhisperSizeCachedQuietMiss:
    def test_local_entry_miss_logs_concise_line_without_traceback(self, tmp_config_dir, monkeypatch, caplog):
        def fake_snapshot(**kwargs):
            raise LocalEntryNotFoundError("no cached snapshot")

        monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot)
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            assert td.whisper_size_cached(object(), "tiny") is False
        assert len(_miss_records(caplog)) == 1
        assert _miss_records(caplog)[0].exc_info is None
        assert "Traceback" not in caplog.text


class TestSnapshotCompleteQuietMiss:
    def test_incomplete_snapshot_logs_concise_line_without_traceback(self, tmp_config_dir, monkeypatch, caplog):
        from voice_typer.server.config import _config_dir

        repo_dir = _config_dir() / "huggingface" / "hub" / "models--Systran--faster-whisper-tiny"
        repo_dir.mkdir(parents=True)

        def fake_snapshot(**kwargs):
            raise IncompleteSnapshotError(
                "The cached snapshot is incomplete: 1 files are missing "
                "(vocabulary.json). Outgoing traffic is disabled ('local_files_only=True').",
                snapshot_path=str(repo_dir),
            )

        monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot)
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            assert td.is_model_snapshot_complete("Systran/faster-whisper-tiny") is False
        assert len(_miss_records(caplog)) == 1
        assert _miss_records(caplog)[0].exc_info is None
        assert "Traceback" not in caplog.text

    def test_cache_not_found_logs_concise_line_without_traceback(self, tmp_config_dir, monkeypatch, caplog):
        from voice_typer.server.config import _config_dir

        repo_dir = _config_dir() / "huggingface" / "hub" / "models--Systran--faster-whisper-tiny"
        repo_dir.mkdir(parents=True)

        def fake_snapshot(**kwargs):
            raise CacheNotFound("no cache entry", cache_dir=str(repo_dir))

        monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot)
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            assert td.is_model_snapshot_complete("Systran/faster-whisper-tiny") is False
        assert _miss_records(caplog)[0].exc_info is None
        assert "Traceback" not in caplog.text


class TestRepeatedOfflineMissDedupe:
    def test_same_key_and_exception_type_logs_once(self, caplog):
        def fake_snapshot(**kwargs):
            raise LocalEntryNotFoundError("no cached snapshot")

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            for _ in range(3):
                assert td.probe_cache(object(), fake_snapshot, "test/dedupe-same-key", "main", [], "tiny") == (
                    None,
                    False,
                )

        assert len(_miss_records(caplog)) == 1
        assert _miss_records(caplog)[0].exc_info is None

    def test_different_exception_type_for_same_key_logs_again(self, caplog):
        def fake_missing(**kwargs):
            raise LocalEntryNotFoundError("no cached snapshot")

        def fake_no_cache(**kwargs):
            raise CacheNotFound("no cache entry", cache_dir="/x")

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            td.probe_cache(object(), fake_missing, "test/dedupe-exc-type", "main", [], "tiny")
            td.probe_cache(object(), fake_no_cache, "test/dedupe-exc-type", "main", [], "tiny")

        assert len(_miss_records(caplog)) == 2

    def test_unexpected_error_is_never_deduped(self, caplog):
        def fake_snapshot(**kwargs):
            raise RuntimeError("disk on fire")

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            td.probe_cache(object(), fake_snapshot, "test/dedupe-unexpected", "main", [], "tiny")
            td.probe_cache(object(), fake_snapshot, "test/dedupe-unexpected", "main", [], "tiny")

        records = _miss_records(caplog)
        assert len(records) == 2
        assert all(r.exc_info is not None for r in records)

    def test_different_probe_kind_for_same_key_logs_again(self, tmp_config_dir, monkeypatch, caplog):
        from voice_typer.server.config import _config_dir

        repo_dir = _config_dir() / "huggingface" / "hub" / "models--test--dedupe-kind"
        repo_dir.mkdir(parents=True)

        def fake_snapshot(**kwargs):
            raise LocalEntryNotFoundError("no cached snapshot")

        monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot)
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            td.probe_cache(object(), fake_snapshot, "test/dedupe-kind", "main", [], "tiny")
            assert td.is_model_snapshot_complete("test/dedupe-kind") is False

        assert len(_miss_records(caplog)) == 2

    def test_concurrent_same_probe_logs_at_most_once(self, caplog):
        barrier = threading.Barrier(2)

        def fake_snapshot(**kwargs):
            barrier.wait(timeout=10)
            raise LocalEntryNotFoundError("no cached snapshot")

        results: list = []

        def run_probe() -> None:
            results.append(td.probe_cache(object(), fake_snapshot, "test/dedupe-threads", "main", [], "tiny"))

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            threads = [threading.Thread(target=run_probe) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)

        assert results == [(None, False), (None, False)]
        assert len(_miss_records(caplog)) == 1
