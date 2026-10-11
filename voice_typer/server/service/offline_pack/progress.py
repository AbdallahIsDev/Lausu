"""In-memory download progress for the runtime pack (§8.1).

Single purpose only: remember the latest ``offline_pack_download_progress``
percent so ``get_status`` can report honest progress without a new IPC
command. The push event stays the live channel; this store is the
mount catch-up PK-2 reads.
"""

from __future__ import annotations

import contextlib
import threading

_lock = threading.Lock()
_progress: int | None = None
_version: str | None = None
_downloaded_bytes = 0
_total_bytes: int | None = None


def _clamp_pct(value: object) -> int:
    try:
        pct = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, pct))


def record_download_started(version: str, total_bytes: int | None) -> None:
    """Reset to 0% when a download (re)starts; never raises."""
    global _progress, _version, _downloaded_bytes, _total_bytes
    with _lock:
        _version = version if isinstance(version, str) else None
        _progress = 0
        _downloaded_bytes = 0
        _total_bytes = total_bytes if isinstance(total_bytes, int) else None


def record_download_progress(
    version: str,
    progress: object,
    downloaded_bytes: object = 0,
    total_bytes: object = None,
) -> None:
    """Store the latest percent (clamped 0-100); never raises."""
    global _progress, _version, _downloaded_bytes, _total_bytes
    with _lock:
        _version = version if isinstance(version, str) else _version
        _progress = _clamp_pct(progress)
        with contextlib.suppress(TypeError, ValueError):
            _downloaded_bytes = int(downloaded_bytes)  # type: ignore[arg-type]
        if isinstance(total_bytes, int):
            _total_bytes = total_bytes


def record_download_completed(version: str) -> None:
    """Pin 100% when bytes land; verify step reads it until cleared."""
    global _progress, _version
    with _lock:
        _version = version if isinstance(version, str) else _version
        _progress = 100


def record_download_failed(version: str | None = None) -> None:
    """Clear to None so a stale percent never poses as live progress."""
    global _progress, _version
    with _lock:
        if version is None or version == _version:
            _progress = None


def reset_download_progress() -> None:
    """Test isolation hook; no production callers."""
    global _progress, _version, _downloaded_bytes, _total_bytes
    with _lock:
        _progress = None
        _version = None
        _downloaded_bytes = 0
        _total_bytes = None


def get_download_progress() -> int | None:
    """Latest percent 0-100, None when no download is active."""
    with _lock:
        return _progress


def get_download_snapshot() -> dict[str, object]:
    """Full snapshot for ``get_status``; keys stay stable for PK-2."""
    with _lock:
        return {
            "download_progress": _progress,
            "download_version": _version,
            "downloaded_bytes": _downloaded_bytes,
            "total_bytes": _total_bytes,
        }
