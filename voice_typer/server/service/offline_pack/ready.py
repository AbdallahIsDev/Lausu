"""Publish ``offline_pack_ready`` once worker + pack are both up.

Single purpose only: join the two prerequisites the renderer already waits
for (``worker_started`` + pack verified/prewarmed) into the terminal
``offline_pack_ready`` event. Mirrors the ``offline_pack_verified``
publish pattern in ``install.py``; best-effort, never raises.
"""

from __future__ import annotations

import logging
import threading
from types import ModuleType

from .events import _publish_event

log = logging.getLogger(__name__)

_lock = threading.Lock()
_worker_pid_by_version: dict[str, int] = {}
_verified_versions: set[str] = set()
_published_pairs: set[tuple[str, int]] = set()


def _valid_version(value: object) -> bool:
    return isinstance(value, str) and len(value) > 0


def _valid_pid(value: object) -> bool:
    return type(value) is int and value >= 0


def _try_publish(version: str, event_bus: ModuleType | None) -> bool:
    pid = _worker_pid_by_version.get(version)
    if pid is None or version not in _verified_versions:
        return False
    if (version, pid) in _published_pairs:
        return False
    _published_pairs.add((version, pid))
    _publish_event(
        event_bus,
        "offline_pack_ready",
        {"version": version, "worker_pid": pid},
    )
    log.info("[PACK] pack %s ready (worker pid=%d)", version, pid)
    return True


def note_worker_started(pid: object, version: object, event_bus: ModuleType | None) -> bool:
    """Record a ``worker_started``; publish ready when the pack is verified."""
    if not _valid_pid(pid) or not _valid_version(version):
        return False
    ver = str(version)
    with _lock:
        _worker_pid_by_version[ver] = int(pid)  # type: ignore[arg-type]
        return _try_publish(ver, event_bus)


def note_pack_verified(version: object, event_bus: ModuleType | None) -> bool:
    """Record pack verified (install or background checksum); publish when worker is up."""
    if not _valid_version(version):
        return False
    ver = str(version)
    with _lock:
        _verified_versions.add(ver)
        return _try_publish(ver, event_bus)


def note_prewarm_complete(version: object, event_bus: ModuleType | None) -> bool:
    """Prewarm done means the pack can serve; same gate as verified."""
    return note_pack_verified(version, event_bus)


def reset_for_tests() -> None:
    """Clear join state; no production callers."""
    with _lock:
        _worker_pid_by_version.clear()
        _verified_versions.clear()
        _published_pairs.clear()
