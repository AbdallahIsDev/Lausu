"""Resumable downloader: resume, size mismatch, checksum mismatch, cancel.

``urllib`` is replaced with an in-memory fake that honours ``Range``, so
these tests never touch the network and never download a real wheel.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import pytest
from voice_typer.server.cuda_install import downloader
from voice_typer.server.cuda_install.downloader import (
    CancelledError,
    DownloadError,
    download,
    verify_file,
)
from voice_typer.server.cuda_install.manifest import Artifact

PAYLOAD = bytes(range(256)) * 40  # 10 240 bytes, deterministic


class _FakeResponse:
    """Minimal ``http.client.HTTPResponse`` stand-in."""

    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self._offset = 0
        self.status = status

    def read(self, size: int = -1) -> bytes:
        end = self._offset + size if size >= 0 else None
        chunk = self._body[self._offset : end]
        self._offset += len(chunk)
        return chunk

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _artifact(payload: bytes = PAYLOAD) -> Artifact:
    return Artifact(
        key="cudart",
        filename="fake-1.0-py3-none-win_amd64.whl",
        url="https://example.invalid/fake.whl",
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
    )


def _install_fake_transport(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    *,
    honour_range: bool = True,
    seen: list[dict[str, str]] | None = None,
) -> None:
    def fake_urlopen(request, timeout=None):  # noqa: ANN001, ARG001
        headers = dict(getattr(request, "headers", {}) or {})
        if seen is not None:
            seen.append(headers)
        range_header = headers.get("Range")
        if honour_range and range_header:
            start = int(range_header.split("=")[1].split("-")[0])
            return _FakeResponse(payload[start:], status=206)
        return _FakeResponse(payload, status=200)

    monkeypatch.setattr(downloader.urllib.request, "urlopen", fake_urlopen)


def test_download_writes_and_verifies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_transport(monkeypatch, PAYLOAD)
    artifact = _artifact()
    seen_bytes: list[int] = []
    path = download(artifact, tmp_path, cancel=threading.Event(), on_bytes=seen_bytes.append)
    assert path.read_bytes() == PAYLOAD
    assert seen_bytes and seen_bytes[-1] == len(PAYLOAD)
    # No stray partial left behind.
    assert not path.with_name(path.name + ".part").exists()


def test_resume_sends_range_and_keeps_the_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = PAYLOAD[:4096]
    part = tmp_path / (_artifact().filename + ".part")
    part.write_bytes(prefix)
    seen: list[dict[str, str]] = []
    _install_fake_transport(monkeypatch, PAYLOAD, seen=seen)

    path = download(_artifact(), tmp_path, cancel=threading.Event())

    assert seen[0].get("Range") == f"bytes={len(prefix)}-"
    assert path.read_bytes() == PAYLOAD


def test_server_ignoring_range_restarts_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    part = tmp_path / (_artifact().filename + ".part")
    part.write_bytes(PAYLOAD[:4096])
    _install_fake_transport(monkeypatch, PAYLOAD, honour_range=False)

    path = download(_artifact(), tmp_path, cancel=threading.Event())
    # Appending the full body to the prefix would have produced a 14 kB
    # file that fails the size check; the clean restart is what passes.
    assert path.read_bytes() == PAYLOAD


def test_oversized_partial_is_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    part = tmp_path / (_artifact().filename + ".part")
    part.write_bytes(PAYLOAD + b"trailing junk")
    _install_fake_transport(monkeypatch, PAYLOAD)
    path = download(_artifact(), tmp_path, cancel=threading.Event())
    assert path.read_bytes() == PAYLOAD


def test_size_mismatch_is_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = _artifact()
    _install_fake_transport(monkeypatch, PAYLOAD[:-10])
    with pytest.raises(DownloadError) as excinfo:
        download(artifact, tmp_path, cancel=threading.Event())
    assert excinfo.value.code == "size_mismatch"


def test_checksum_mismatch_is_terminal_and_drops_the_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = _artifact()
    corrupt = bytes(len(PAYLOAD))
    _install_fake_transport(monkeypatch, corrupt)
    with pytest.raises(DownloadError) as excinfo:
        download(artifact, tmp_path, cancel=threading.Event())
    assert excinfo.value.code == "checksum_mismatch"
    assert not (tmp_path / (artifact.filename + ".part")).exists()


def test_cancel_stops_mid_transfer_and_keeps_the_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = _artifact()
    cancel = threading.Event()

    def fake_urlopen(request, timeout=None):  # noqa: ANN001, ARG001
        cancel.set()  # user cancels while the first chunk is in flight
        return _FakeResponse(PAYLOAD, status=200)

    monkeypatch.setattr(downloader.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(CancelledError):
        download(artifact, tmp_path, cancel=cancel)
    # The ``.part`` survives so the next attempt resumes.
    assert (tmp_path / (artifact.filename + ".part")).exists()


def test_verified_cache_short_circuits_the_transfer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = _artifact()
    (tmp_path / artifact.filename).write_bytes(PAYLOAD)

    def explode(*_a, **_k):
        raise AssertionError("a verified cached wheel must not be re-fetched")

    monkeypatch.setattr(downloader.urllib.request, "urlopen", explode)
    path = download(artifact, tmp_path, cancel=threading.Event())
    assert path.read_bytes() == PAYLOAD


def test_verify_file_rejects_wrong_size_and_hash(tmp_path: Path) -> None:
    artifact = _artifact()
    good = tmp_path / "good.whl"
    good.write_bytes(PAYLOAD)
    assert verify_file(artifact, good) is True

    short = tmp_path / "short.whl"
    short.write_bytes(PAYLOAD[:-1])
    assert verify_file(artifact, short) is False

    wrong = tmp_path / "wrong.whl"
    wrong.write_bytes(bytes(len(PAYLOAD)))
    assert verify_file(artifact, wrong) is False

    assert verify_file(artifact, tmp_path / "missing.whl") is False


def test_altered_url_cannot_swap_the_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Security: pointing an artifact at another host cannot change bytes.

    The URL is pinned in the reviewed manifest and the SHA256 is pinned
    alongside it, so an altered URL serves a payload that fails the hash
    check — the download is rejected rather than installed.
    """
    artifact = Artifact(
        key="cudart",
        filename="fake-1.0-py3-none-win_amd64.whl",
        url="https://evil.example/fake.whl",
        sha256=hashlib.sha256(PAYLOAD).hexdigest(),
        size=len(PAYLOAD),
    )
    # The alternate host serves different bytes of the same length.
    _install_fake_transport(monkeypatch, bytes(len(PAYLOAD)))

    with pytest.raises(DownloadError) as excinfo:
        download(artifact, tmp_path, cancel=threading.Event())
    assert excinfo.value.code == "checksum_mismatch"


def test_bad_pinned_hash_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Security: a manifest whose SHA256 does not match its wheel is refused."""
    good = _artifact()
    tampered = Artifact(
        key=good.key,
        filename=good.filename,
        url=good.url,
        sha256="0" * 64,
        size=good.size,
    )
    _install_fake_transport(monkeypatch, PAYLOAD)

    with pytest.raises(DownloadError) as excinfo:
        download(tampered, tmp_path, cancel=threading.Event())
    assert excinfo.value.code == "checksum_mismatch"
