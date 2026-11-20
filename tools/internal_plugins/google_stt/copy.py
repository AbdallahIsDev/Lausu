"""User-facing copy and log vocabulary for the Google STT plugin.

No shared string may name a vendor: this module owns every Google/Gemini word
the plugin shows, while the bridge owns only vendor-neutral transport wording.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

LOG_NAME = "voice_typer.internal_plugin.google_stt"
MODEL_LABEL = "google-stt-web"
DISPLAY_NAME = "Google STT"

START_FAILURE_FALLBACK = "Google STT could not start. See log."
BRIDGE_UNAVAILABLE = "Google STT bridge unavailable (daemon did not start)."
STOP_FAILURE_FALLBACK = "Google STT stop failed. See log."

START_HINTS = {
    "browser-closed": (
        "The Gemini dictation window closed - press the hotkey again to relaunch it."
    ),
    "browser-not-open": (
        "The Gemini dictation window could not be started, or its extension is not loaded. "
        "Check the window, load the extension once if it is missing, then press the hotkey again."
    ),
    "wrong-platform": (
        "The connected Gemini tab is not the one this plugin owns. Open Gemini in the "
        "dictation profile, then press the hotkey again."
    ),
    "page-not-ready": "The Gemini tab is still loading. Wait a moment, then press the hotkey again.",
    "bridge-timeout": (
        "The Gemini page did not answer in time. Check that its window is open on Gemini, "
        "then press the hotkey again."
    ),
    "mic-missing": "Google STT could not find the dictation button on the Gemini page.",
    "no-recording-indicator": "The Gemini page never started recording.",
    "platform-not-recording": "The Gemini page did not start capturing audio.",
    "composer-dirty": "The Gemini prompt box would not clear - press the hotkey again.",
    "selectors-missing": (
        "Gemini's live stop/discard controls have not been discovered yet. Run the bridge probe "
        "while signed in, fill selectors/gemini.json, regenerate the extension and reload it."
    ),
    "signed-out": "The Gemini session is signed out - open the dictation window and sign in again.",
    "challenge": (
        "A Google security check is blocking the page - finish it in the dictation "
        "browser window, then press the hotkey again."
    ),
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
