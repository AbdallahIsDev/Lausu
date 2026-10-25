"""Segmented planning must compare manifest pins against LFS content ids.

The Hub reports ``blob_id`` as the sha1 of the LFS pointer file for every
LFS-tracked weight, so pinning on it silently sent every big file back to
the classic single-stream path.
"""

import logging
from types import SimpleNamespace

from voice_typer.server import segmented_download as segdl

LFS_SHA256 = "e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da"
POINTER_BLOB_ID = "c849f26401bf079fdea48ac9f7461fdff2e743ea"
REPO_ID = "dropbox-dash/faster-whisper-large-v3-turbo"
REVISION = "0a363e91"
MODEL_SIZE = 1_618_000_000
SEGDL_LOGGER = "voice_typer.server.segmented_download"


def _fake_hf_api(monkeypatch, entries):
    class FakeHfApi:
        def list_repo_tree(self, repo_id, revision=None, recursive=False):
            return list(entries)

    monkeypatch.setattr("huggingface_hub.HfApi", FakeHfApi)


def _lfs_entry(path="model.bin", size=MODEL_SIZE):
    return SimpleNamespace(
        path=path,
        size=size,
        blob_id=POINTER_BLOB_ID,
        lfs=SimpleNamespace(sha256=LFS_SHA256, size=size, pointer_size=134),
    )


def _plan(**over):
    kwargs = dict(
        repo_id=REPO_ID,
        revision=REVISION,
        allow_patterns=["*.bin"],
        file_hashes={"model.bin": LFS_SHA256},
        threshold_bytes=100,
    )
    kwargs.update(over)
    return segdl.plan_segmented_files(**kwargs)


class TestDefaultListFilesContentId:
    def test_lfs_sha256_replaces_pointer_blob_id(self, monkeypatch):
        _fake_hf_api(monkeypatch, [_lfs_entry()])
        assert segdl._default_list_files(REPO_ID, REVISION) == [("model.bin", MODEL_SIZE, LFS_SHA256)]

    def test_non_lfs_entry_keeps_blob_id(self, monkeypatch):
        _fake_hf_api(monkeypatch, [SimpleNamespace(path="config.json", size=1234, blob_id="0" * 40, lfs=None)])
        assert segdl._default_list_files(REPO_ID, REVISION) == [("config.json", 1234, "0" * 40)]

    def test_entry_without_path_is_skipped(self, monkeypatch):
        _fake_hf_api(monkeypatch, [SimpleNamespace(size=1, blob_id="x", lfs=None)])
        assert segdl._default_list_files(REPO_ID, REVISION) == []


class TestLfsPlanning:
    def test_hub_listing_plans_big_lfs_file_without_warning(self, monkeypatch, caplog):
        _fake_hf_api(monkeypatch, [_lfs_entry()])
        with caplog.at_level(logging.WARNING, logger=SEGDL_LOGGER):
            plan = _plan()
        assert plan == [
            segdl.PlannedFile(filename="model.bin", size=MODEL_SIZE, blob_id=LFS_SHA256, sha256=LFS_SHA256),
        ]
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

    def test_genuine_mismatch_warns_and_stays_classic(self, caplog):
        with caplog.at_level(logging.WARNING, logger=SEGDL_LOGGER):
            plan = _plan(list_files=lambda: [("model.bin", MODEL_SIZE, "f" * 64)])
        assert plan == []
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert f"[SEGDL] manifest pin != tree blob_id for {REPO_ID}:model.bin" in warnings[0].getMessage()


class TestPlanningFailureLog:
    def test_failure_logs_one_debug_line_without_traceback(self, caplog):
        def unreachable():
            raise ConnectionError("[Errno 11001] getaddrinfo failed")

        with caplog.at_level(logging.DEBUG, logger=SEGDL_LOGGER):
            plan = _plan(list_files=unreachable)
        assert plan is None
        records = [r for r in caplog.records if r.name == SEGDL_LOGGER]
        assert len(records) == 1
        assert records[0].levelno == logging.DEBUG
        assert records[0].exc_info is None
        assert "getaddrinfo failed" in records[0].getMessage()
