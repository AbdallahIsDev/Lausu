"""Shared authority resolution for the stable extension install path.

The relative paths and identity live in ``install.json`` next to this file;
the Node sync step and this Python verifier both resolve them from LOCALAPPDATA.
Nothing in the repo tree is ever used as an install location.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

AUTHORITY = Path(__file__).resolve().parent / "install.json"
_CFG = json.loads(AUTHORITY.read_text(encoding="utf-8"))

EXTENSION_ID = str(_CFG["extensionId"])
PORT = int(_CFG["relayPort"])
PROFILE_DIRECTORY = str(_CFG["profileDirectory"])
EXTENSION_RELATIVE_PATH = str(_CFG["extensionRelativePath"])
PROFILE_RELATIVE_PATH = str(_CFG["profileRelativePath"])


def data_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata).parent
    return Path.home() / "AppData" / "Local"


def stable_extension_dir() -> Path:
    return data_root() / Path(EXTENSION_RELATIVE_PATH)


def profile_dir() -> Path:
    return data_root() / Path(PROFILE_RELATIVE_PATH)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def points_into_repo(candidate: str | Path | None) -> bool:
    if not candidate:
        return False
    resolved = Path(candidate).resolve()
    root = repo_root().resolve()
    return resolved == root or root in resolved.parents


def _settings(secure_preferences: Path) -> dict:
    try:
        data = json.loads(secure_preferences.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    settings = (((data or {}).get("extensions") or {}).get("settings") or {})
    return settings if isinstance(settings, dict) else {}


def _same_path(left: str, right: Path) -> bool:
    try:
        return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(
            str(right.resolve())
        )
    except (OSError, ValueError):
        return False


def read_registered_extension_path(
    secure_preferences: Path, *, target: Path | None = None
) -> str | None:
    """Read our registration path out of a Secure Preferences file.

    Chrome derives an unpacked extension's id from the path SPELLING it was
    loaded with, so loading the same folder twice (or after a path/spelling
    change) leaves the id from ``install.json`` unregistered while a second id
    points at our folder. Identity is therefore matched by PATH first and only
    falls back to the recorded id. Never writes to the profile.
    """
    settings = _settings(secure_preferences)
    if target is not None:
        for entry in settings.values():
            path = entry.get("path") if isinstance(entry, dict) else None
            if isinstance(path, str) and _same_path(path, target):
                return path
    entry = settings.get(EXTENSION_ID)
    if isinstance(entry, dict) and isinstance(entry.get("path"), str):
        return entry["path"]
    return None


def duplicate_registration_count(secure_preferences: Path, target: Path) -> int:
    """How many ids point at our folder (2+ means a stale duplicate entry)."""
    return sum(
        1
        for entry in _settings(secure_preferences).values()
        if isinstance(entry, dict)
        and isinstance(entry.get("path"), str)
        and _same_path(entry["path"], target)
    )


def registered_extension_path(profile: Path | None = None) -> str | None:
    root = profile or profile_dir()
    return read_registered_extension_path(
        root / PROFILE_DIRECTORY / "Secure Preferences",
        target=stable_extension_dir(),
    )


def install_hint() -> str:
    return (
        "The dictation extension is not connected. Open chrome://extensions in the dictation "
        "profile, enable Developer mode, choose \"Load unpacked\", and select "
        f"{stable_extension_dir()}. Then reload the tab and press the hotkey again."
    )


__all__ = [
    "EXTENSION_ID",
    "PORT",
    "PROFILE_DIRECTORY",
    "repo_root",
    "data_root",
    "stable_extension_dir",
    "profile_dir",
    "points_into_repo",
    "read_registered_extension_path",
    "registered_extension_path",
    "install_hint",
]
