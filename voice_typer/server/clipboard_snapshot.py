"""Multi-format clipboard snapshot/restore.

ADR-0010 §4: standalone module that captures and restores **all** clipboard
formats. Platform-dispatched. No dependency on ``pyperclip`` (which is
text-only).

Design principles (ADR-0010 §3):

* DP1, every borrow is paired with a restore.
* DP4, snapshots are passed as values, not stored as instance state.
* DP5, capture all formats on Windows and macOS; text-only on Linux
  (X11 and Wayland). Linux limitations are documented, not hidden.

The per-platform implementations live in ``clipboard_snapshot_win32``,
``clipboard_snapshot_macos`` and ``clipboard_snapshot_linux`` (mixins),
with the Win32 format tables / capture caps in
``clipboard_snapshot_formats``; every moved name is re-exported here so
the historical import path keeps resolving. This facade owns the
snapshot type, its thread-serialized ``restore()`` dispatch, and the
module-level ``log`` the per-platform mixins resolve at call time.

The snapshot is an immutable ``@dataclass``. ``capture()`` is a classmethod
returning a new instance (or ``None``). ``restore()`` dispatches on
``self.platform``: the platform tag is captured at creation time and travels
with the snapshot, so no global state is consulted at restore time.

Cross-platform safety: every platform branch is wrapped so that an import
failure or API misuse on a non-target platform logs and returns ``None``
rather than crashing the caller. The transcription pipeline treats
``None`` as "no snapshot to restore": a degraded but safe mode.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any

from voice_typer.server.clipboard_snapshot_formats import (  # noqa: F401  # facade re-export
    _BUILTIN_FORMAT_NAMES,
    _MAX_FORMAT_BYTES,
    _MAX_TOTAL_SNAPSHOT_BYTES,
    _NON_RESTORABLE_FORMATS,
    _REGISTERED_FORMAT_MIN,
    _builtin_format_name,
)
from voice_typer.server.clipboard_snapshot_linux import LinuxClipboardMixin
from voice_typer.server.clipboard_snapshot_macos import MacosClipboardMixin
from voice_typer.server.clipboard_snapshot_win32 import WindowsClipboardMixin
from voice_typer.server.platform_utils import is_macos, is_windows

log = logging.getLogger(__name__)


# Platform clipboard APIs are NOT thread-safe:
_restore_lock = threading.Lock()


@dataclass
class ClipboardSnapshot(WindowsClipboardMixin, MacosClipboardMixin, LinuxClipboardMixin):
    """A captured snapshot of clipboard content at a point in time.

    Captures all formats (text, RTF, HTML, image, file lists) on Windows
    and macOS. Captures text-only on Linux (X11 and Wayland) due to CLI
    tool limitations: see ADR-0010 §4.5 and §4.6.

    Usage::

        snap = ClipboardSnapshot.capture()
        if snap is not None:
            try:
                pyperclip.copy(transcription_text)
                send_paste_keystroke()
                time.sleep(0.15)
            finally:
                snap.restore()

    The dataclass is intentionally simple, ``items`` is a list of
    platform-specific tuples (the platform knows how to interpret them).
    No methods on the dataclass mutate state; ``restore()`` only reads
    ``self.platform`` and ``self.items``.
    """

    platform: str  # "windows" | "macos" | "linux-x11" | "linux-wayland"
    items: list[tuple[Any, ...]] = field(default_factory=list)
    captured_at: float = 0.0

    @classmethod
    def capture(cls) -> ClipboardSnapshot | None:
        """Capture the current clipboard across all formats.

        Returns ``None`` if the clipboard cannot be opened (another app
        holds the lock) or if no formats are present. The caller treats
        ``None`` as "no snapshot to restore": a degraded but safe mode.
        """
        try:
            if is_windows():
                return cls._capture_windows()
            if is_macos():
                return cls._capture_macos()
            # Linux: dispatch on XDG_SESSION_TYPE (default x11).
            session = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
            if session == "wayland":
                snap = cls._capture_wayland()
                # XWayland fallback: if wl-paste fails (e.g. running under
                if snap is None or not snap.items:
                    snap = cls._capture_x11()
                return snap
            return cls._capture_x11()
        except Exception:
            log.exception("[CLIPBOARD-SNAPSHOT] capture failed")
            return None

    def restore(self) -> bool:
        """Restore all captured formats.

                Returns ``True`` if the restore completed without raising,
                ``False`` on failure. Best-effort: per-item failures are logged
                but do not abort the loop (we restore as many formats as we can).

        the entire platform-dispatched restore is
                serialized across threads by ``_restore_lock``. Platform
                clipboard APIs are not thread-safe (Win32 ``OpenClipboard``
                fails on the second concurrent opener; macOS
                ``NSPasteboard.clearContents`` / ``writeObjects_`` is
                main-thread-only; Linux ``xclip`` / ``wl-copy`` subprocesses
                race on selection ownership). The lock prevents the daemon
                thread for cycle A's ``snapshot_A.restore()`` from racing the
                atexit handler's ``snapshot_B.restore()`` (or another daemon's
                ``snapshot_C.restore()``) on the platform clipboard APIs.

                The lock is held for the duration of the platform restore
                (Open/Empty/Set/Close on Windows; clearContents/writeObjects on
                macOS; subprocess.run on Linux). This is correct: the platform
                call sequence is the critical section. Per-item failures inside
                ``_restore_windows`` etc. are still logged-and-continue (best
                effort), the lock is not released between items because
                releasing between items would re-open the race window mid-loop.
        """
        with _restore_lock:
            if self.platform == "windows":
                return self._restore_windows()
            if self.platform == "macos":
                return self._restore_macos()
            if self.platform == "linux-x11":
                return self._restore_x11()
            if self.platform == "linux-wayland":
                return self._restore_wayland()
            log.warning("[CLIPBOARD-SNAPSHOT] unknown platform: %s", self.platform)
            return False
