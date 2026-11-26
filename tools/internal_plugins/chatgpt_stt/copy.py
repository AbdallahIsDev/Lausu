"""User-facing copy and log vocabulary for the ChatGPT STT plugin.

No shared string may name a vendor: this module owns every OpenAI/ChatGPT word
the plugin shows, while the bridge owns only vendor-neutral transport wording.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

LOG_NAME = "voice_typer.internal_plugin.chatgpt_stt"
MODEL_LABEL = "chatgpt-web"
DISPLAY_NAME = "ChatGPT STT"

START_FAILURE_FALLBACK = "ChatGPT STT could not start. See log."
BRIDGE_UNAVAILABLE = "ChatGPT STT bridge unavailable (daemon did not start)."
STOP_FAILURE_FALLBACK = "ChatGPT STT stop failed. See log."

STOP_HINTS = {
    "browser-not-open": (
        "The ChatGPT browser closed while dictating; nothing was captured. Press the hotkey again to record."
    ),
    "page-not-ready": "The ChatGPT page did not answer. Nothing was pasted; press the hotkey again.",
    "bridge-timeout": "The ChatGPT page did not answer in time. Nothing was pasted; press the hotkey again.",
    "not-recording": "The ChatGPT page had already stopped. Nothing was pasted.",
}

START_HINTS = {
    "relaunches-exhausted": ("Chrome was closed {count} times while starting. Press the hotkey to try again."),
    "browser-closed": ("The ChatGPT dictation window closed - press the hotkey again to relaunch it."),
    "browser-not-open": (
        "The ChatGPT dictation window could not be started, or its extension is not loaded. "
        "Check the window, load the extension once if it is missing, then press the hotkey again."
    ),
    "wrong-platform": (
        "The connected ChatGPT tab is not the one this plugin owns. Open ChatGPT in the "
        "dictation profile, then press the hotkey again."
    ),
    "page-not-ready": "The ChatGPT tab is still loading. Wait a moment, then press the hotkey again.",
    "bridge-timeout": (
        "The ChatGPT page did not answer in time. Check that its window is open on ChatGPT, "
        "then press the hotkey again."
    ),
    "mic-missing": "ChatGPT STT could not find the dictation button on the ChatGPT page.",
    "no-recording-indicator": "The ChatGPT page never started recording.",
    "platform-not-recording": "The ChatGPT page did not start capturing audio.",
    "composer-dirty": "The ChatGPT prompt box would not clear - press the hotkey again.",
    "selectors-missing": (
        "ChatGPT's live stop/discard controls have not been discovered yet. Run the bridge probe "
        "while signed in, fill selectors/chatgpt.json, regenerate the extension and reload it."
    ),
    "signed-out": "The ChatGPT session is signed out - open the dictation window and sign in again.",
    "challenge": (
        "A security check is blocking the page - finish it in the dictation "
        "browser window, then press the hotkey again."
    ),
    "browser.down": (
        "The ChatGPT browser is not running. It is being reopened; press the hotkey again if it does not start."
    ),
    "tab.missing": "The ChatGPT tab was closed. It is being reopened; press the hotkey again if it does not appear.",
    "tab.discarded": "The ChatGPT tab was asleep. It is being reloaded; press the hotkey again in a moment.",
    "tab.wrong_url": "The dictation tab is on the wrong page. Open ChatGPT, then press the hotkey again.",
    "tab.crashed": "The ChatGPT tab stopped responding. Close and reopen it, then press the hotkey again.",
    "content_script.absent": "The ChatGPT page has not finished loading. Wait a moment, then press the hotkey again.",
    "control.missing": "ChatGPT's dictation button is not available. Check the page, then press the hotkey again.",
    "signed_in.no": "Not signed in to ChatGPT. Open the dictation window and sign in again.",
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
    """The Plugins page's notification switch; missing/invalid means on."""
    try:
        raw = json.loads(((directory or Path(__file__).resolve().parent) / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    value = raw.get("notify") if isinstance(raw, dict) else None
    return value if isinstance(value, bool) else True


log = logging.getLogger(LOG_NAME)
