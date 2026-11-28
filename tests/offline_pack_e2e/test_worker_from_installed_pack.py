"""Spawn the worker payload from the installed pack directory.

The pack holds a test-only launcher script. A real release holds a frozen
exe and the Rust host spawns it directly; here Python spawns the installed
path (the supported dev seam) because no frozen worker is built locally.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest
from voice_typer.server.service import offline_pack, update_check
from voice_typer.server.service.offline_pack import local_dev
from voice_typer.server.worker_protocol import port_from_worker_started

from .fixtures import MANIFEST_NAME, WORKER_NAME, RecordingBus
from .pack_server import LoopbackPackServer

LAUNCHER = (
    b"import json, os, sys\n"
    b"print(json.dumps({'event': 'worker_started', 'port': int(sys.argv[1]), "
    b"'protocol': 1, 'version': '21', 'pid': os.getpid()}), flush=True)\n"
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def local_dev_env(monkeypatch):
    monkeypatch.setenv(local_dev.ENV_LOCAL_PACK_DEV_SERVER, "1")
    return monkeypatch


def test_installed_worker_launcher_handshake_and_ready(tmp_path: Path, local_dev_env):
    root = tmp_path / "pack-root"
    archive = tmp_path / "pack-21.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(WORKER_NAME, LAUNCHER)
    from scripts.release.build_pack_manifest import build_pack_manifest

    manifest = dict(build_pack_manifest(archive, version="21"))
    server = LoopbackPackServer(
        {
            MANIFEST_NAME: json.dumps(manifest).encode("utf-8"),
            "pack-21.zip": archive.read_bytes(),
        }
    ).start()
    bus = RecordingBus()
    proc = None
    try:
        update_check.check_offline_pack_update(None, bus, manifest_url=server.url(MANIFEST_NAME), root=root)
        assert bus.wait_for({"offline_pack_verified"}) is not None

        installed_worker = root / "21" / WORKER_NAME
        assert installed_worker.read_bytes() == LAUNCHER
        port = _free_port()
        env = dict(os.environ)
        env["VOICE_TYPER_CONFIG_DIR"] = str(tmp_path / "cfg")
        proc = subprocess.Popen(
            [sys.executable, str(installed_worker), str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        deadline = time.monotonic() + 10.0
        handshake = None
        while time.monotonic() < deadline and proc.stdout is not None:
            line = proc.stdout.readline().strip()
            if not line:
                continue
            payload = json.loads(line)
            if payload.get("event") == "worker_started":
                handshake = payload
                break
        assert handshake is not None, "installed worker never emitted a handshake"
        assert port_from_worker_started(handshake) == port
        assert handshake["version"] == "21"

        offline_pack.reset_ready_for_tests()
        ready_bus = RecordingBus()
        assert offline_pack.note_worker_started(proc.pid, "21", ready_bus) is False
        assert offline_pack.note_pack_verified("21", ready_bus) is True
        ready = ready_bus.of_type("offline_pack_ready")
        assert ready and ready[0]["data"] == {"version": "21", "worker_pid": proc.pid}
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        server.stop()


def test_real_worker_dev_seam_is_available(tmp_path: Path):
    """The real worker module boots in a source checkout (no frozen exe)."""
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["VOICE_TYPER_CONFIG_DIR"] = str(tmp_path / "cfg")
    env["PYTHONPATH"] = str(repo)
    proc = subprocess.run(
        [sys.executable, "-m", "voice_typer.worker", "--version"],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "voice_typer.worker" in (proc.stdout + proc.stderr)
