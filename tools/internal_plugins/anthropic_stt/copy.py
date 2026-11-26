"""User-facing copy and log vocabulary for the Claude STT plugin.

One table for the daemon's failure slugs and the plugin's display names, so a
copy change lands in one place. The session and entry modules render from here
instead of carrying their own strings.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

LOG_NAME = "voice_typer.internal_plugin.anthropic_stt"
MODEL_LABEL = "anthropic-stt-web"
DISPLAY_NAME = "Claude STT"

START_FAILURE_FALLBACK = "Claude STT could not start. See log."
BRIDGE_UNAVAILABLE = "Claude STT bridge unavailable (daemon did not start)."
STOP_FAILURE_FALLBACK = "Claude STT stop failed. See log."

STOP_HINTS = {
    "browser-not-open": (
        "The Claude browser closed while dictating; nothing was captured. Press the hotkey again to record."
    ),
    "page-not-ready": "The Claude page did not answer. Nothing was pasted; press the hotkey again.",
    "bridge-timeout": "The Claude page did not answer in time. Nothing was pasted; press the hotkey again.",
    "not-recording": "The Claude page had already stopped. Nothing was pasted.",
}

# Daemon failure kinds → what the user is actually told. The daemon reports a
# slug; without this the toast said nothing useful and the log carried a
# 20-line urllib traceback that hid the reason entirely.
START_HINTS = {
    "browser-not-open": (
        "The Claude dictation window could not be started, or its extension is not loaded. "
        "Check the window, load the extension once if it is missing, then press the hotkey again."
    ),
    "page-not-ready": ("The Claude tab is still loading. Wait a moment, then press the hotkey again."),
    "bridge-timeout": (
        "The Claude page did not answer in time. Check that its window is open on the Claude tab, "
        "then press the hotkey again."
    ),
    "mic-missing": "Claude STT could not find the dictation button on the Claude page.",
    "no-recording-indicator": "The Claude page never started recording.",
    "platform-not-recording": "The Claude page did not start capturing audio.",
    "composer-dirty": "The Claude prompt box would not clear - press the hotkey again.",
    "signed-out": "The Claude session is signed out - open the Claude browser window and sign in again.",
    "challenge": (
        "Claude's security check is blocking the page - finish the check in the Claude "
        "browser window, then press the hotkey again."
    ),
    "relaunches-exhausted": ("Chrome was closed {count} times while starting. Press the hotkey to try again."),
    "browser.down": (
        "The Claude browser is not running. It is being reopened; press the hotkey again if it does not start."
    ),
    "tab.missing": "The Claude tab was closed. It is being reopened; press the hotkey again if it does not appear.",
    "tab.discarded": "The Claude tab was asleep. It is being reloaded; press the hotkey again in a moment.",
    "tab.wrong_url": "The dictation tab is on the wrong page. Open Claude, then press the hotkey again.",
    "tab.crashed": "The Claude tab stopped responding. Close and reopen it, then press the hotkey again.",
    "content_script.absent": "The Claude page has not finished loading. Wait a moment, then press the hotkey again.",
    "control.missing": "Claude's dictation button is not available. Check the page, then press the hotkey again.",
    "signed_in.no": "Not signed in to Claude. Open the dictation window and sign in again.",
}


def duration(seconds: float | None) -> str:
    """C-LOG-2 duration suffix (leading space included)."""
    from voice_typer.server.duration import format_duration

    return format_duration(0.0 if seconds is None else seconds)


def millis(value: Any) -> str:
    """Milliseconds as they came off the page, or ``n/a`` when unreported."""
    try:
        return f"{float(value):.0f}ms"
    except (TypeError, ValueError):
        return "n/a"


def notify_enabled(directory: Path | None = None) -> bool:
    """The Plugins page's notification switch; a missing or invalid value is on.

    The daemon's config.json is the single source: the Plugins page writes the
    `notify` key there through set_plugin_setting, so this must read the same
    file (C-CONF-1). An old settings.json is ignored.
    """
    try:
        raw = json.loads(((directory or Path(__file__).resolve().parent) / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    value = raw.get("notify") if isinstance(raw, dict) else None
    return value if isinstance(value, bool) else True


log = logging.getLogger(LOG_NAME)
