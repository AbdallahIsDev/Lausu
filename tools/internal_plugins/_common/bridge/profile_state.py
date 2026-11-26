"""Runtime profile hygiene for the dedicated dictation Chrome profile.

Two fixes happen BEFORE launch, and only while no Chrome process owns the
profile (Chrome overwrites Preferences while running):

1. mark a clean exit so Chrome does not show "Restore pages?" after an
   unclean kill;
2. pre-grant the microphone for exactly the three platform origins, so a
   first-use permission bubble cannot swallow a dictation start.

No launch flag is added: the plain three-argument contract stays intact.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("voice_typer.internal_plugin.profile_state")

MIC_ORIGINS = (
    "https://chatgpt.com:443,*",
    "https://claude.ai:443,*",
    "https://gemini.google.com:443,*",
)


def _preferences_path(profile_dir: str, profile_directory: str) -> Path:
    return Path(profile_dir) / profile_directory / "Preferences"


def prepare_profile(profile_dir: str, profile_directory: str = "Default") -> bool:
    """Return True when Preferences was changed; never raise on bad runtime state."""
    path = _preferences_path(profile_dir, profile_directory)
    try:
        if not path.is_file():
            return False
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return False
        changed = False
        profile = raw.get("profile")
        if not isinstance(profile, dict):
            profile = {}
            raw["profile"] = profile
            changed = True
        if profile.get("exit_type") != "Normal":
            profile["exit_type"] = "Normal"
            changed = True
        if profile.get("exited_cleanly") is not True:
            profile["exited_cleanly"] = True
            changed = True
        content = raw.get("content_settings")
        if not isinstance(content, dict):
            content = {}
            raw["content_settings"] = content
            changed = True
        exceptions = content.get("exceptions")
        if not isinstance(exceptions, dict):
            exceptions = {}
            content["exceptions"] = exceptions
            changed = True
        mic = exceptions.get("media_stream_mic")
        if not isinstance(mic, dict):
            mic = {}
            exceptions["media_stream_mic"] = mic
            changed = True
        for origin in MIC_ORIGINS:
            entry = mic.get(origin)
            if not isinstance(entry, dict) or entry.get("setting") != 1:
                # Never override an explicit Block (setting 2).
                if isinstance(entry, dict) and entry.get("setting") == 2:
                    continue
                mic[origin] = {"setting": 1, "last_modified": "0"}
                changed = True
        if not changed:
            return False
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(raw, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)
        return True
    except Exception:
        log.debug("[PLUGIN] profile Preferences hygiene skipped", exc_info=True)
        return False


def apply_before_launch(profile_dir: str, profile_directory: str, pids: Any) -> None:
    """Only touch Preferences when the profile is not currently running."""
    try:
        if pids(profile_dir):
            log.debug("[PLUGIN] profile is running; Preferences left untouched")
            return
        if prepare_profile(profile_dir, profile_directory):
            log.info("[PLUGIN] dictation profile prepared (clean exit, microphone granted)")
    except Exception:
        log.debug("[PLUGIN] profile preparation failed", exc_info=True)
