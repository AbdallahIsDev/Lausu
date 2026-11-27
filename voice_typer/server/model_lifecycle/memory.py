"""Private-memory guard for optional model preload.

Calibration from Round-5 measurements on this machine (2026-11-27):
translator ~1.8 GB private, TTS Magpie ~1.3 GB private, TTS Audio8 ~5.9 GB
private AFTER the first synthesis (a lazy-load health check reads only 2.6 MB,
so working set alone would understate it by >5 GB). ASR Parakeet is
UNVERIFIED at runtime; only the 740 MB file size is known.

HEADROOM_BYTES = 512 MiB covers the running app/UI, allocator overhead and a
concurrent dictation while leaving Magpie loadable on an 8 GB machine with
~3.4 GB free. A larger headroom would skip Magpie on the very machines the
preload is meant to help; a smaller one would not cover the app baseline.
Guard failure (unreadable memory) is a hard skip, never a guess.
"""

from __future__ import annotations

import ctypes
import logging
import os
from typing import Any

log = logging.getLogger(__name__)

HEADROOM_BYTES = 512 * 1024 * 1024


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def _windows_available_bytes() -> int | None:
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullAvailPhys)


def _posix_available_bytes() -> int | None:
    sysconf = getattr(os, "sysconf", None)  # resolved dynamically: absent on Windows
    if sysconf is None:
        return None
    try:
        pages = int(sysconf("SC_AVPHYS_PAGES"))
        page_size = int(sysconf("SC_PAGE_SIZE"))
    except (ValueError, OSError, AttributeError):
        return None
    if pages < 0 or page_size <= 0:
        return None
    return pages * page_size


def available_physical_bytes() -> int | None:
    """Read available physical RAM; ``None`` means the guard cannot read it."""
    try:
        if os.name == "nt":
            return _windows_available_bytes()
        return _posix_available_bytes()
    except Exception:
        log.debug("[LIFECYCLE] physical memory read unavailable", exc_info=True)
        return None


def memory_fits(policy: Any) -> bool:
    try:
        available = available_physical_bytes()
    except Exception:
        # A guard that cannot read memory must fail closed, never raise on a
        # startup thread (D3).
        log.debug("[LIFECYCLE] physical memory read failed; skipping preload", exc_info=True)
        return False
    if available is None or available <= 0:
        return False
    try:
        estimate = int(policy.estimate_private_bytes)
    except Exception:
        return False
    if estimate < 0:
        return False
    return available > estimate + HEADROOM_BYTES


__all__ = ["HEADROOM_BYTES", "available_physical_bytes", "memory_fits"]
