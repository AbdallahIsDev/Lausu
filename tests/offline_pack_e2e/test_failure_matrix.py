"""Local end-to-end failure matrix for the pack downloader."""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from voice_typer.server.service import offline_pack, update_check
from voice_typer.server.service.offline_pack import gates, local_dev

from .fixtures import MANIFEST_NAME, RecordingBus, build_pack, corrupt_archive, serve_pack, sha256

TERMINAL = {
    "offline_pack_verified",
    "offline_pack_corrupt",
    "offline_pack_download_failed",
}


@pytest.fixture
def local_dev_env(monkeypatch):
    monkeypatch.setenv(local_dev.ENV_LOCAL_PACK_DEV_SERVER, "1")
    return monkeypatch


def _check(url: str, root: Path, bus: RecordingBus, **kwargs) -> dict:
    return update_check.check_offline_pack_update(None, bus, manifest_url=url, root=root, **kwargs)


def _reason(bus: RecordingBus, event_type: str) -> str:
    events = bus.of_type(event_type)
    assert events, f"no {event_type} event: {[e['type'] for e in bus.events]}"
    return str(events[0]["data"].get("reason"))


def _wait_until(predicate, timeout_s: float = 10.0) -> None:
    """Wait for a positive filesystem condition; deadline-based, no fixed sleep."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition never became true before the deadline")


def _no_installed_pack(root: Path, version: str) -> None:
    """A pre-created empty version dir is expected; no manifest means no pack."""
    assert not (root / version / MANIFEST_NAME).exists()
    assert not offline_pack.verify_offline_pack_or_skip(version, root=root)
    assert update_check._local_offline_pack_version(root=root) is None


def test_manifest_404_explicit_url_reports_failure(tmp_path: Path, local_dev_env):
    server = None
    from .pack_server import LoopbackPackServer

    server = LoopbackPackServer({}).start()
    root = tmp_path / "pack-root"
    bus = RecordingBus()
    try:
        result = _check(server.url(MANIFEST_NAME), root, bus)
        assert result["success"] is False and result["reason"] == "fetch_failed"
        assert _reason(bus, "offline_pack_download_failed") == "manifest_unavailable"
        assert not root.exists() or not any(root.iterdir())
    finally:
        server.stop()


def test_manifest_404_default_candidates_stays_benign(tmp_path: Path, local_dev_env):
    server = None
    from .pack_server import LoopbackPackServer

    server = LoopbackPackServer({}).start()
    local_dev_env.delenv("VT_PACK_MANIFEST_URL", raising=False)
    urls = [server.url(MANIFEST_NAME), server.url("other-manifest.json")]
    local_dev_env.setattr(update_check, "pack_manifest_url_candidates", lambda _manifest_url=None: urls)
    bus = RecordingBus()
    result = update_check.check_offline_pack_update(None, bus, root=tmp_path / "pack-root")
    assert result["success"] is True and result["reason"] == "no_remote_manifest"
    assert bus.events == []
    server.stop()


def test_server_down_publishes_manifest_failure(tmp_path: Path, local_dev_env):
    bus = RecordingBus()
    result = _check("http://127.0.0.1:1/pack-manifest.json", tmp_path / "pack-root", bus)
    assert result["success"] is False
    assert _reason(bus, "offline_pack_download_failed") == "manifest_unavailable"


def test_drop_mid_download_deletes_partial_and_installs_nothing(tmp_path: Path, local_dev_env):
    root = tmp_path / "pack-root"
    server, _zip_bytes, _ = serve_pack(tmp_path, "11", drop_path="pack-11.zip", drop_after=len(b"x") * 16)
    bus = RecordingBus()
    try:
        _check(server.url(MANIFEST_NAME), root, bus)
        terminal = bus.wait_for(TERMINAL)
        assert terminal is not None and terminal["type"] == "offline_pack_corrupt"
        assert _reason(bus, "offline_pack_corrupt") == "sha256_mismatch"
        _wait_until(lambda: not offline_pack.offline_pack_partial_path("11", root=root).exists())
        _no_installed_pack(root, "11")
    finally:
        server.stop()


def test_resume_from_partial_uses_range_and_finishes(tmp_path: Path, local_dev_env):
    root = tmp_path / "pack-root"
    server, zip_bytes, _ = serve_pack(tmp_path, "12")
    (root / "12").mkdir(parents=True)
    partial = offline_pack.offline_pack_partial_path("12", root=root)
    partial.write_bytes(zip_bytes[:128])
    bus = RecordingBus()
    try:
        _check(server.url(MANIFEST_NAME), root, bus)
        assert bus.wait_for({"offline_pack_verified"}) is not None
        assert server.range_requests == [128]
        assert offline_pack.verify_offline_pack_or_skip("12", root=root)
        assert (root / "12" / "lausu-worker-x86_64-pc-windows-msvc.exe").is_file()
        assert not partial.exists()  # install consumes the verified archive
    finally:
        server.stop()


def test_hash_mismatch_installs_nothing(tmp_path: Path, local_dev_env):
    root = tmp_path / "pack-root"
    server, _, manifest = serve_pack(tmp_path, "13")
    bad_manifest = {**manifest, "sha256": "0" * 64}
    server._files[MANIFEST_NAME] = json.dumps(bad_manifest).encode("utf-8")
    bus = RecordingBus()
    try:
        _check(server.url(MANIFEST_NAME), root, bus)
        assert bus.wait_for(TERMINAL)["type"] == "offline_pack_corrupt"
        assert _reason(bus, "offline_pack_corrupt") == "sha256_mismatch"
        _wait_until(lambda: not offline_pack.offline_pack_partial_path("13", root=root).exists())
        _no_installed_pack(root, "13")
    finally:
        server.stop()


def test_zip_corruption_removes_bad_partial_and_installs_nothing(tmp_path: Path, local_dev_env):
    root = tmp_path / "pack-root"
    zip_bytes, manifest, _ = build_pack(tmp_path, "14")
    bad_bytes = corrupt_archive(zip_bytes)
    manifest["sha256"] = sha256(bad_bytes)
    from .pack_server import LoopbackPackServer

    server = LoopbackPackServer(
        {
            MANIFEST_NAME: json.dumps(manifest).encode("utf-8"),
            "pack-14.zip": bad_bytes,
        }
    ).start()
    bus = RecordingBus()
    try:
        _check(server.url(MANIFEST_NAME), root, bus)
        terminal = bus.wait_for(TERMINAL)
        assert terminal is not None and terminal["type"] == "offline_pack_download_failed"
        assert _reason(bus, "offline_pack_download_failed") == "install_failed"
        _wait_until(lambda: not offline_pack.offline_pack_partial_path("14", root=root).exists())
        _no_installed_pack(root, "14")
        assert not Path(str(root / "14") + ".new").exists()
    finally:
        server.stop()


def test_disk_full_gate_refuses_before_any_download(tmp_path: Path, local_dev_env, monkeypatch):
    root = tmp_path / "pack-root"
    server, _, _ = serve_pack(tmp_path, "15")
    monkeypatch.setattr(gates.shutil, "disk_usage", lambda _path: SimpleNamespace(free=1 << 20))
    bus = RecordingBus()
    try:
        _check(server.url(MANIFEST_NAME), root, bus)
        event = bus.wait_for({"offline_pack_download_failed"})
        assert event is not None
        assert _reason(bus, "offline_pack_download_failed") == "disk_full"
        assert server.path_hits["pack-15.zip"] == 0
        _no_installed_pack(root, "15")
    finally:
        server.stop()


def test_lock_contention_reports_busy_without_second_stream(tmp_path: Path, local_dev_env, monkeypatch):
    root = tmp_path / "pack-root"
    server, _, _ = serve_pack(tmp_path, "16")
    real_lock = offline_pack.OfflinePackLock

    def short_lock(version: str, *, root: Path | None = None):
        return real_lock(version, root=root, timeout_s=0.2)

    monkeypatch.setattr(update_check.offline_pack, "OfflinePackLock", short_lock)
    blocker = real_lock("16", root=root)
    blocker.acquire()
    bus = RecordingBus()
    try:
        _check(server.url(MANIFEST_NAME), root, bus)
        assert bus.wait_for({"offline_pack_download_failed"}) is not None
        assert _reason(bus, "offline_pack_download_failed") == "locked"
        assert server.path_hits["pack-16.zip"] == 0
    finally:
        blocker.release()
        server.stop()
