"""Resumable, cancellable, hash-verified wheel download.

Every artifact is pinned by URL + size + SHA256. A ``.part`` file survives a
cancel/crash so the next attempt continues with a ``Range`` request instead of
re-downloading hundreds of megabytes; the hash is recomputed over the resumed
prefix, so a corrupted partial is never accepted.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from voice_typer.server.cuda_install.manifest import Artifact

log = logging.getLogger(__name__)

_CHUNK_BYTES = 1024 * 1024
_READ_TIMEOUT_S = 60.0
_USER_AGENT = "lausu-cuda-installer/1"


class DownloadError(Exception):
    """Terminal download failure carrying a stable machine code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class CancelledError(DownloadError):
    def __init__(self) -> None:
        super().__init__("cancelled")


ProgressFn = Callable[[int], None]


def _hash_prefix(path: Path, limit: int, cancel: threading.Event) -> Any:
    digest = hashlib.sha256()
    remaining = limit
    with path.open("rb") as handle:
        while remaining > 0:
            if cancel.is_set():
                raise CancelledError()
            block = handle.read(min(_CHUNK_BYTES, remaining))
            if not block:
                break
            digest.update(block)
            remaining -= len(block)
    return digest


def _hash_file(path: Path, cancel: threading.Event) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            if cancel.is_set():
                raise CancelledError()
            block = handle.read(_CHUNK_BYTES)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def verify_file(artifact: Artifact, path: Path, cancel: threading.Event | None = None) -> bool:
    """True when ``path`` is byte-identical to the pinned artifact."""
    if cancel is None:
        cancel = threading.Event()
    try:
        if path.stat().st_size != artifact.size:
            return False
        return _hash_file(path, cancel) == artifact.sha256
    except (CancelledError, OSError):
        return False


def download(
    artifact: Artifact,
    dest_dir: Path,
    *,
    cancel: threading.Event,
    on_bytes: ProgressFn | None = None,
) -> Path:
    """Fetch + verify one artifact, resuming a previous partial transfer."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / artifact.filename
    if dest.is_file() and verify_file(artifact, dest, cancel):
        if on_bytes is not None:
            on_bytes(artifact.size)
        return dest

    part = dest.with_name(dest.name + ".part")
    written = part.stat().st_size if part.is_file() else 0
    if written > artifact.size:
        part.unlink(missing_ok=True)
        written = 0

    digest = hashlib.sha256()
    if written:
        try:
            digest = _hash_prefix(part, written, cancel)
        except (CancelledError, OSError):
            part.unlink(missing_ok=True)
            written = 0

    headers = {"User-Agent": _USER_AGENT}
    if written:
        headers["Range"] = f"bytes={written}-"
    request = urllib.request.Request(artifact.url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=_READ_TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and written:
            part.unlink(missing_ok=True)
            return download(artifact, dest_dir, cancel=cancel, on_bytes=on_bytes)
        raise DownloadError("network", f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise DownloadError("network", str(exc)) from exc

    try:
        status = getattr(response, "status", 200)
        if written and status != 206:
            # Server ignored the range: restart cleanly instead of appending
            # a second copy onto the partial.
            written = 0
            digest = hashlib.sha256()
        mode = "ab" if written else "wb"
        with response, part.open(mode) as handle:
            while True:
                if cancel.is_set():
                    raise CancelledError()
                block = response.read(_CHUNK_BYTES)
                if not block:
                    break
                handle.write(block)
                digest.update(block)
                written += len(block)
                if on_bytes is not None:
                    on_bytes(written)
    except (CancelledError, DownloadError):
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise DownloadError("network", str(exc)) from exc

    if written != artifact.size:
        raise DownloadError("size_mismatch", f"{written} != {artifact.size}")
    if digest.hexdigest() != artifact.sha256:
        part.unlink(missing_ok=True)
        raise DownloadError("checksum_mismatch", artifact.filename)
    os.replace(part, dest)
    log.info("[CUDA] verified %s (%d bytes)", artifact.filename, written)
    return dest
