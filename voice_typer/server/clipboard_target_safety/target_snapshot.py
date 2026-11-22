"""Stop-time target snapshot: destination identity + caret context at dictation stop.

Captures a point-in-time snapshot of the foreground target (window handle,
process identity, and stop-time caret prefix context) at the exact moment the
user stops dictation. Post-transcription formatting and paste dispatch use this
snapshot as the sole source for destination decisions and never steal or refocus
any window.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any

import voice_typer.server.clipboard_target_safety as _pkg
from voice_typer.server.clipboard_target_safety import caret_text
from voice_typer.server.clipboard_target_safety.caret_text import _PrefixContext
from voice_typer.server.clipboard_target_safety.targets import (
    _invalidate_focused_atspi_cache,
)


@dataclass(frozen=True, slots=True)
class StopTimeTargetSnapshot:
    """Immutable foreground target + caret snapshot captured at stop time."""

    hwnd: int = 0
    pid: int | None = None
    process_name: str | None = None
    macos_pid: int | None = None
    prefix_context: _PrefixContext = field(
        default_factory=lambda: _PrefixContext(None, "unknown", False)
    )


def _win32_foreground_target_info() -> tuple[int, int | None, str | None]:
    """Read foreground HWND, PID, and process basename on Windows without mutating focus."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        raw_hwnd = user32.GetForegroundWindow()
        hwnd = int(raw_hwnd) if raw_hwnd else 0
        if not hwnd:
            return (0, None, None)

        pid_dword = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_dword))
        pid = int(pid_dword.value) if pid_dword.value else None
        if not pid:
            return (hwnd, None, None)

        process_query_limited_information = 0x1000
        h_process = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not h_process:
            return (hwnd, pid, None)

        try:
            size = wintypes.DWORD(512)
            buf = ctypes.create_unicode_buffer(512)
            if kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
                name = str(buf.value).rsplit("\\", 1)[-1].lower()
                return (hwnd, pid, name or None)
        finally:
            kernel32.CloseHandle(h_process)
        return (hwnd, pid, None)
    except (OSError, AttributeError, TypeError, ValueError):
        _pkg._log().debug(
            "[CLIPBOARD] stop-time Win32 target probe failed",
            exc_info=True,
        )
        return (0, None, None)


def _macos_frontmost_pid() -> int | None:
    """Read frontmost macOS application PID, returning None if unavailable."""
    try:
        import AppKit  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        if workspace is None:
            return None
        front_app = workspace.frontmostApplication()
        if front_app is None:
            return None
        pid = front_app.processIdentifier()
        return int(pid) if pid is not None else None
    except Exception:
        _pkg._log().debug(
            "[CLIPBOARD] stop-time macOS target probe failed",
            exc_info=True,
        )
        return None


def capture_stop_time_target_snapshot() -> StopTimeTargetSnapshot:
    """Capture fresh stop-time target window/process identity and caret context.

    Invalidates any stale AT-SPI role cache entry before reading so rapid
    back-to-back sessions across different windows never observe stale state.
    """
    _invalidate_focused_atspi_cache()

    hwnd = 0
    pid: int | None = None
    process_name: str | None = None
    macos_pid: int | None = None

    if _pkg.is_windows():
        hwnd, pid, process_name = _win32_foreground_target_info()
    elif _pkg.is_macos():
        macos_pid = _macos_frontmost_pid()
        pid = macos_pid

    try:
        prefix_context = caret_text._as_context(caret_text._char_before_caret())
    except Exception:
        _pkg._log().debug(
            "[CLIPBOARD] stop-time caret capture failed, defaulting to unknown",
            exc_info=True,
        )
        prefix_context = _PrefixContext(None, "unknown", False)

    return StopTimeTargetSnapshot(
        hwnd=hwnd,
        pid=pid,
        process_name=process_name,
        macos_pid=macos_pid,
        prefix_context=prefix_context,
    )


def accepts_kwarg(fn: object, name: str) -> bool:
    """Return True if ``fn`` accepts keyword argument ``name`` (or **kwargs)."""
    try:
        params = inspect.signature(fn).parameters.values()  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return any(p.kind == inspect.Parameter.VAR_KEYWORD or p.name == name for p in params)


def call_clipboard_paste(
    clipboard: Any,
    target_snapshot: StopTimeTargetSnapshot | None,
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Invoke ``clipboard.paste`` forwarding ``target_snapshot`` when accepted."""
    paste_kwargs = dict(kwargs)
    if target_snapshot is not None and accepts_kwarg(clipboard.paste, "target_snapshot"):
        paste_kwargs["target_snapshot"] = target_snapshot
    return bool(clipboard.paste(*args, **paste_kwargs))


__all__ = [
    "StopTimeTargetSnapshot",
    "accepts_kwarg",
    "call_clipboard_paste",
    "capture_stop_time_target_snapshot",
]
