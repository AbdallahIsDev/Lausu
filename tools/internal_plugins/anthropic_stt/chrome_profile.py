"""Starts the owner's dictation Chrome profile, with plain flags only.

This module is the one place allowed to start a browser. It may pass exactly
three arguments: the user-data-dir, the profile directory and the URL.
Automation flags are what got the old Playwright session flagged as a bot, so
every other switch is rejected before Chrome is spawned; the guard lives in
``_assert_plain`` and is pinned by ``verify_profile_launch.py``.

The window stays the owner's: nothing here moves, resizes, minimizes or
re-focuses it after launch.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger("voice_typer.internal_plugin.anthropic_stt.profile")

PROFILE_DIRECTORY = "Default"

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

# A test seam: the verifier replaces this to inspect the exact command line.
_popen = subprocess.Popen


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


def launch(profile_dir: str, url: str, *, chrome_path: str | None = None) -> bool:
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
        _assert_plain(args)
        _popen(
            [exe, *args],
            env=_browser_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError):
        log.exception("[PLUGIN] opening the dictation profile failed")
        return False
    log.info("[PLUGIN] opening the dictation profile: %s", profile_dir)
    return True
