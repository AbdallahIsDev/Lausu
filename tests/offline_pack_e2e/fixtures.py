"""Shared builders for the local pack E2E tests."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import zipfile
from pathlib import Path

from scripts.release.build_pack_manifest import build_pack_manifest

from .pack_server import LoopbackPackServer

MANIFEST_NAME = "pack-manifest.json"
WORKER_NAME = "lausu-worker-x86_64-pc-windows-msvc.exe"


class RecordingBus:
    """Event bus with a condition, so tests wait on real events, not sleeps."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self._cond = threading.Condition()

    def publish(self, event: dict) -> None:
        with self._cond:
            self.events.append(event)
            self._cond.notify_all()

    def of_type(self, event_type: str) -> list[dict]:
        return [event for event in self.events if event.get("type") == event_type]

    def wait_for(self, event_types: set[str], timeout_s: float = 20.0) -> dict | None:
        deadline = time.monotonic() + timeout_s
        with self._cond:
            while True:
                for event in self.events:
                    if event.get("type") in event_types:
                        return event
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)


def worker_script(tag: str) -> bytes:
    """Test-only worker payload; the real harness uses a Python launcher."""
    return (f"#!/usr/bin/env python3\nWORKER_TAG = {tag!r}\nprint('worker ready')\n").encode()


def build_pack(tmp_path: Path, version: str, *, tag: str = "v1", padding: int = 0) -> tuple[bytes, dict, bytes]:
    """Return ``(zip_bytes, manifest, worker_bytes)`` built by the real builder."""
    worker = worker_script(tag)
    archive = tmp_path / f"pack-{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(WORKER_NAME, worker)
        if padding:
            # Incompressible: a stored deflate of zeros would collapse to KB
            # and the progress event would never cross its 0.5 s threshold.
            zf.writestr("payload.bin", os.urandom(padding))
    manifest = dict(build_pack_manifest(archive, version=version))
    return archive.read_bytes(), manifest, worker


def serve_pack(
    tmp_path: Path,
    version: str,
    *,
    tag: str = "v1",
    padding: int = 0,
    **server_kwargs,
) -> tuple[LoopbackPackServer, bytes, dict]:
    """Build a pack, serve it on loopback, return server + bytes + manifest."""
    zip_bytes, manifest, _worker = build_pack(tmp_path, version, tag=tag, padding=padding)
    files = {
        MANIFEST_NAME: json.dumps(manifest).encode("utf-8"),
        f"pack-{version}.zip": zip_bytes,
    }
    return LoopbackPackServer(files, **server_kwargs).start(), zip_bytes, manifest


def corrupt_archive(bytes_in: bytes) -> bytes:
    """Truncate a zip so extraction fails while the archive hash still matches."""
    return bytes_in[: max(1, len(bytes_in) // 2)]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
