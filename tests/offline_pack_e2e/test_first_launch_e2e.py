"""Local end-to-end: first launch, update, downgrade, dual instance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from voice_typer.server.service import offline_pack, update_check
from voice_typer.server.service.offline_pack import local_dev

from .fixtures import MANIFEST_NAME, WORKER_NAME, RecordingBus, serve_pack, worker_script

TERMINAL = {
    "offline_pack_verified",
    "offline_pack_corrupt",
    "offline_pack_download_failed",
}


@pytest.fixture
def local_dev_env(monkeypatch):
    monkeypatch.setenv(local_dev.ENV_LOCAL_PACK_DEV_SERVER, "1")
    return monkeypatch


def _check(server, root, bus, **kwargs) -> dict:
    return update_check.check_offline_pack_update(
        None,
        bus,
        manifest_url=server.url(MANIFEST_NAME),
        root=root,
        **kwargs,
    )


def test_first_launch_downloads_verifies_and_installs(tmp_path: Path, local_dev_env):
    root = tmp_path / "pack-root"
    server, zip_bytes, manifest = serve_pack(tmp_path, "101", padding=3 << 20, chunk_delay_s=0.22)
    bus = RecordingBus()
    try:
        local_dev_env.setenv("VT_PACK_MANIFEST_URL", server.url(MANIFEST_NAME))
        result = check = _check(server, root, bus)
        terminal = bus.wait_for(TERMINAL)
        assert terminal is not None
        assert terminal["type"] == "offline_pack_verified"
        assert check["update_available"] is True and check["download_triggered"] is True

        types = [event["type"] for event in bus.events]
        assert "offline_pack_download_started" in types
        assert "offline_pack_download_progress" in types
        assert "offline_pack_download_completed" in types

        installed = root / "101"
        assert (installed / WORKER_NAME).is_file()
        assert (installed / MANIFEST_NAME).is_file()
        written = json.loads((installed / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert written["sha256"] == manifest["sha256"]
        assert offline_pack.offline_pack_exists("101", root=root)
        assert offline_pack.verify_offline_pack_or_skip("101", root=root)
        assert update_check._local_offline_pack_version(root=root) == "101"
        assert not offline_pack.offline_pack_partial_path("101", root=root).exists()
        assert not Path(str(installed) + ".new").exists()
        assert result["remote_version"] == "101"
    finally:
        server.stop()


def test_update_n_to_n_plus_1_replaces_worker(tmp_path: Path, local_dev_env):
    root = tmp_path / "pack-root"
    first_dir = tmp_path / "first"
    first_dir.mkdir(parents=True)
    first, _, _ = serve_pack(first_dir, "5")
    bus1 = RecordingBus()
    try:
        assert _check(first, root, bus1)["download_triggered"] is True
        assert bus1.wait_for({"offline_pack_verified"}) is not None
        assert (root / "5" / WORKER_NAME).exists()

        second_dir = tmp_path / "second"
        second_dir.mkdir(parents=True)
        second, _, _ = serve_pack(second_dir, "6", tag="new-worker")
        bus2 = RecordingBus()
        assert _check(second, root, bus2)["download_triggered"] is True
        assert bus2.wait_for({"offline_pack_verified"}) is not None
        assert update_check._local_offline_pack_version(root=root) == "6"
        installed_worker = (root / "6" / WORKER_NAME).read_bytes()
        assert installed_worker == worker_script("new-worker")
        # Versions are separate dirs; the host pins the active version in
        # VOICE_TYPER_PACK_VERSION. The old dir may remain but is not active.
        assert update_check._local_offline_pack_version(root=root) == "6"
        assert offline_pack.verify_offline_pack_or_skip("5", root=root)
        assert not Path(str(root / "6") + ".trash").exists()
    finally:
        first.stop()
        second.stop()


def test_downgrade_is_refused_without_download(tmp_path: Path, local_dev_env):
    root = tmp_path / "pack-root"
    server, _, _ = serve_pack(tmp_path, "9")
    installer_bus = RecordingBus()
    try:
        assert _check(server, root, installer_bus)["download_triggered"] is True
        assert installer_bus.wait_for({"offline_pack_verified"}) is not None

        old_dir = tmp_path / "old"
        old_dir.mkdir(parents=True)
        downgrade, _, _ = serve_pack(old_dir, "4")
        downgrade_bus = RecordingBus()
        result = _check(downgrade, root, downgrade_bus, trigger_download=False)
        assert result["download_triggered"] is False
        assert result["update_available"] is False
        assert downgrade.path_hits[MANIFEST_NAME] == 1
        assert downgrade_bus.events == []
        assert update_check._local_offline_pack_version(root=root) == "9"
        downgrade.stop()
    finally:
        server.stop()


def test_two_instances_only_one_download_starts(tmp_path: Path, local_dev_env):
    root = tmp_path / "pack-root"
    server, _, _ = serve_pack(tmp_path, "7", padding=1 << 20, chunk_delay_s=0.25)
    buses = [RecordingBus(), RecordingBus()]
    try:
        results = [_check(server, root, buses[0]), _check(server, root, buses[1])]
        assert sorted(bool(result["download_triggered"]) for result in results) == [False, True]
        assert any(bus.wait_for({"offline_pack_verified"}) for bus in buses)
        started = [event for bus in buses for event in bus.of_type("offline_pack_download_started")]
        assert len(started) == 1, "two instances must not stream the same partial"
        assert server.path_hits["pack-7.zip"] == 1
        assert update_check._local_offline_pack_version(root=root) == "7"
    finally:
        server.stop()
