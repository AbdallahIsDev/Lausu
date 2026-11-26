"""Starts the owner's dictation Chrome profile, with plain flags only.

This module is the one place allowed to start a browser. It may pass exactly
three arguments: the user-data-dir, the profile directory and the URL.
Automation flags are what got the old Playwright session flagged as a bot, so
every other switch is rejected before Chrome is spawned; the guard lives in
``_assert_plain`` and is pinned by ``verify_profile_launch.py``.

The window stays the owner's: nothing here moves, resizes or re-focuses it.
The optional "hidden" mode never adds a command-line flag either — it only
calls Win32 ``ShowWindow(SW_HIDE)`` on the spawned process's window after the
launch, which removes the taskbar entry without changing Chrome's fingerprint.
True headless is deliberately NOT used: it disables the microphone.

On non-Windows platforms visibility control is a no-op (the profile still
launches normally); the setting is accepted but has no effect there.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tools.internal_plugins._common.bridge.install_paths import PROFILE_DIRECTORY, profile_dir

log = logging.getLogger("voice_typer.internal_plugin.bridge.profile")

PID_FILE = "chrome_pid.json"
# The one profile both platforms share, resolved from the same install
# authority as the sync step and the verifier. Never rename it: that would
# orphan the owner's sign-ins and the installed unpacked extension.
PROFILE_DIR = str(profile_dir()).replace("\\", "/")

# The complete set of switches a launch may carry (the URL has no prefix).
ALLOWED_PREFIXES = ("--user-data-dir=", "--profile-directory=")

# Any of these recreates the automation fingerprint that lost the session.
FORBIDDEN_MARKERS = (
    "--remote-debugging",
    "--enable-automation",
    "--disable-blink-features",
    "--headless",
    "--auto-",
    "--user-agent",
    "--proxy",
    "--no-sandbox",
    "--disable-gpu",
    "--window-position",
    "--window-size",
    "--start-maximized",
    "--start-minimized",
    "--kiosk",
    "--app=",
)

# A test seam: the verifier replaces these to inspect calls without a real OS.
_popen = subprocess.Popen
_set_window_visible_fn = None

SW_HIDE = 0
SW_SHOW = 5
SW_SHOWNOACTIVATE = 4
BROWSER_CLASS = "Chrome_WidgetWin_1"
_HWND = ctypes.c_void_p
_LPARAM = ctypes.c_ssize_t
_WNDENUMPROC = ctypes.CFUNCTYPE(ctypes.c_int, _HWND, _LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def find_chrome(env: dict[str, str] | None = None) -> str | None:
    """The installed branded Chrome, or None. Playwright's Chromium is never used.

    Reads the backfilled browser environment, not ``os.environ``: the sidecar is
    spawned with a trimmed environment (``PROGRAMFILES`` and ``LOCALAPPDATA`` are
    absent), so a raw read finds nothing inside the app and only works from a
    full shell.
    """
    resolved = _browser_env() if env is None else env
    candidates = (
        resolved.get("LUASU_CHROME_PATH", ""),
        os.path.join(resolved.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(resolved.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(resolved.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def profile_args(profile_dir: str, url: str) -> list[str]:
    return [f"--user-data-dir={profile_dir}", f"--profile-directory={PROFILE_DIRECTORY}", url]


def _assert_plain(args: list[str]) -> None:
    for arg in args:
        lowered = arg.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker in lowered:
                raise ValueError(f"refusing to launch Chrome with {arg!r}")
        if lowered.startswith("--") and not lowered.startswith(ALLOWED_PREFIXES):
            raise ValueError(f"refusing to launch Chrome with {arg!r}")


def _browser_env() -> dict[str, str]:
    """The sidecar's environment is trimmed, so put the Windows paths back."""
    env = dict(os.environ)
    home = os.path.expanduser("~")
    for key, fallback in (
        ("SYSTEMROOT", r"C:\Windows"),
        ("PROGRAMFILES", r"C:\Program Files"),
        ("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        ("LOCALAPPDATA", os.path.join(home, "AppData", "Local")),
        ("APPDATA", os.path.join(home, "AppData", "Roaming")),
        ("USERPROFILE", home),
    ):
        if not env.get(key):
            env[key] = fallback
    return env


def _pid_file(plugin_dir: str | None) -> Path | None:
    return Path(plugin_dir) / PID_FILE if plugin_dir else None


def _record_pid(plugin_dir: str | None, pid: int) -> None:
    path = _pid_file(plugin_dir)
    if path is None:
        return
    try:
        path.write_text(json.dumps({"pid": pid}), encoding="utf-8")
    except OSError:
        log.debug("[PLUGIN] could not record the profile pid", exc_info=True)


def _read_pid(plugin_dir: str | None) -> int | None:
    path = _pid_file(plugin_dir)
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("pid")
        return int(value) if isinstance(value, int) and value > 0 else None
    except (OSError, ValueError, AttributeError):
        return None


def _windows_for_pid(pid: int) -> list[int]:
    """Top-level window handles owned by *pid* (Windows only, fixed ctypes types)."""
    handles: list[int] = []

    def _enum(hwnd: int, _lparam: int) -> int:
        owner = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(_HWND(hwnd), ctypes.byref(owner))
        if owner.value == pid:
            handles.append(hwnd)
        return 1

    ctypes.windll.user32.EnumWindows(_WNDENUMPROC(_enum), 0)
    return handles


def _window_info(hwnd: int) -> dict[str, Any]:
    """Class/title/rect/visibility used to tell the real browser from helpers."""
    u32 = ctypes.windll.user32
    name = ctypes.create_unicode_buffer(256)
    title = ctypes.create_unicode_buffer(512)
    u32.GetClassNameW(_HWND(hwnd), name, 256)
    u32.GetWindowTextW(_HWND(hwnd), title, 512)
    rect = RECT()
    u32.GetWindowRect(_HWND(hwnd), ctypes.byref(rect))
    return {
        "hwnd": hwnd,
        "class": name.value,
        "title": title.value,
        "rect": (rect.left, rect.top, rect.right, rect.bottom),
        "visible": bool(u32.IsWindowVisible(_HWND(hwnd))),
    }


def _is_browser_window(info: dict[str, Any]) -> bool:
    """Only the painted top-level Chrome frame is a browser window.

    Chrome owns several zero-size helper windows (Base_PowerMessageWindow,
    Chrome_WidgetWin_0, MSCTFIME UI, IME). Revealing those produced the blank
    extra window the owner saw.
    """
    left, top, right, bottom = info["rect"]
    return info["class"] == BROWSER_CLASS and (bool(info["title"].strip()) or (right - left > 0 and bottom - top > 0))


def _trace_window(hwnd: int, visible: bool, switch: int) -> None:
    info = _window_info(hwnd)
    image = process_image_name(_pid_of_hwnd(hwnd))
    log.debug(
        "[FOCUS] ShowWindow pid=%d hwnd=%s class=%s title=%r rect=%s visible_before=%s switch=%d image=%s",
        _pid_of_hwnd(hwnd),
        hex(hwnd),
        info["class"],
        info["title"][:80],
        info["rect"],
        info["visible"],
        switch,
        image,
    )


def _pid_of_hwnd(hwnd: int) -> int:
    owner = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(_HWND(hwnd), ctypes.byref(owner))
    return int(owner.value)


def _process_rows(*, strict: bool = False) -> list[dict[str, str]]:
    """pid/image/cmdline for chrome.exe via WMI, without trusting Popen's pid."""
    if sys.platform != "win32":
        return []
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
        'ForEach-Object { "$($_.ProcessId)|$($_.Name)|$($_.CommandLine)" }'
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        if strict:
            raise
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3 and parts[0].strip().isdigit():
            rows.append({"pid": parts[0].strip(), "image": parts[1].strip(), "cmdline": parts[2]})
    return rows


def process_image_name(pid: int) -> str:
    for row in _process_rows():
        if int(row["pid"]) == pid:
            return row["image"]
    return ""


def _profile_in_cmdline(cmdline: str, profile_dir: str) -> bool:
    wanted = f"--user-data-dir={profile_dir}".replace("\\", "/").lower()
    return wanted in cmdline.replace("\\", "/").lower()


def resolve_browser_pids(profile_dir: str, *, strict: bool = False) -> list[int]:
    return [
        int(row["pid"])
        for row in _process_rows(strict=strict)
        if row["image"].lower() == "chrome.exe" and _profile_in_cmdline(row["cmdline"], profile_dir)
    ]


def browser_liveness(profile_dir: str, *, samples: int = 3, interval: float = 0.2) -> bool:
    """Debounced liveness: a single empty WMI sample is NOT a dead profile.

    WMI can transiently enumerate zero chrome.exe rows right after Popen or
    during a reload. A failed enumeration is UNKNOWN, never death, so the
    launch cooldown is not bypassed by an enumeration glitch.
    """
    for index in range(max(1, samples)):
        try:
            if resolve_browser_pids(profile_dir, strict=True):
                return True
        except Exception:
            return True
        if index + 1 < samples:
            time.sleep(interval)
    return False


def resolve_browser_pid(profile_dir: str) -> int | None:
    """The chrome.exe owning this profile AND a painted browser window."""
    candidates = resolve_browser_pids(profile_dir)
    if sys.platform != "win32":
        return candidates[0] if candidates else None
    for pid in candidates:
        for hwnd in _windows_for_pid(pid):
            if _is_browser_window(_window_info(hwnd)):
                return pid
    return None


def resolve_browser_pid_after_launch(profile_dir: str, *, wait_s: float = 5.0, poll_s: float = 0.15) -> int | None:
    """Resolve the browser pid once Chrome has actually painted its window.

    ``Popen`` returns before Chrome creates a top-level ``Chrome_WidgetWin_1``,
    so a single ``resolve_browser_pid`` call right after launch reports a
    false failure and leaves the per-plugin pid file stale. Poll briefly
    instead; on a healthy start this returns on the first or second attempt.
    """
    deadline = time.monotonic() + wait_s
    while True:
        pid = resolve_browser_pid(profile_dir)
        if pid is not None:
            return pid
        if time.monotonic() >= deadline:
            return None
        time.sleep(poll_s)


def is_valid_browser_pid(pid: int, profile_dir: str) -> bool:
    return pid > 0 and pid in resolve_browser_pids(profile_dir)


def set_window_visible(plugin_dir: str | None, visible: bool, *, wait_s: float = 5.0) -> bool:
    """Show/hide the dictation profile's window without any launch flags.

    Uses the PID recorded at launch. Chrome creates its top-level window a
    moment after Popen returns, so a hidden launch polls briefly. Returns True
    when at least one window was found and toggled.
    """
    if sys.platform != "win32":
        log.debug("[PLUGIN] profile visibility control is Windows-only")
        return False
    pid = _read_pid(plugin_dir)
    if pid is None:
        return False
    if _set_window_visible_fn is not None:
        return bool(_set_window_visible_fn(pid, visible, wait_s))
    deadline = time.monotonic() + (wait_s if not visible else 0.5)
    found = False
    while True:
        # Hiding targets every handle; showing targets ONLY the real frame and
        # never activates it. Helper windows caused the blank third window.
        handles = [h for h in _windows_for_pid(pid) if not visible or _is_browser_window(_window_info(h))]
        if handles:
            for hwnd in handles:
                _trace_window(hwnd, visible, SW_SHOWNOACTIVATE if visible else SW_HIDE)
                ctypes.windll.user32.ShowWindow(_HWND(hwnd), SW_SHOWNOACTIVATE if visible else SW_HIDE)
            found = True
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    if not found:
        log.warning("[PLUGIN] dictation profile window not found for pid=%d", pid)
    return found


def launch(
    profile_dir: str,
    url: str,
    *,
    chrome_path: str | None = None,
    visible: bool = True,
    plugin_dir: str | None = None,
) -> bool:
    """Start the profile and return immediately; False means it never spawned."""
    if not profile_dir:
        log.error("[PLUGIN] no profileDir configured; cannot open the dictation window")
        return False
    exe = chrome_path or find_chrome()
    if not exe:
        log.error("[PLUGIN] chrome.exe was not found; install Chrome or set LUASU_CHROME_PATH")
        return False
    args = profile_args(profile_dir, url)
    try:
        from tools.internal_plugins._common.bridge import profile_state

        profile_state.apply_before_launch(profile_dir, PROFILE_DIRECTORY, resolve_browser_pids)
        _assert_plain(args)
        proc = _popen(
            [exe, *args],
            env=_browser_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError):
        log.exception("[PLUGIN] opening the dictation profile failed")
        return False
    resolved = resolve_browser_pid_after_launch(profile_dir)
    if resolved is None:
        log.warning(
            "[PLUGIN] launched Chrome but could not resolve its profile window pid (waited %.1fs)",
            5.0,
        )
    else:
        _record_pid(plugin_dir, resolved)
    if not visible:
        set_window_visible(plugin_dir, False)
    log.info(
        "[PLUGIN] opening the dictation profile: %s (visible=%s, pid=%d)",
        profile_dir,
        visible,
        resolved or proc.pid,
    )
    return True
