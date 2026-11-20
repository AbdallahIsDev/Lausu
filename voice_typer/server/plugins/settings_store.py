"""Persistence for manifest-declared plugin settings.

Settings live in ``<plugin dir>/config.json`` next to the manifest: that file
is the single source of truth the plugin daemon itself loads, so a write from
the Plugins page is effective without an intermediate copy. Writes are
validated against the manifest declaration first, so an IPC caller cannot
store an unknown key or a mistyped/out-of-range value, and reads drop entries
the manifest no longer declares.

The daemon's own keys (profileDir, relayToken, hotkeys, ...) are NOT managed
by the manifest. Every write is a read-modify-write of the whole file, so
those keys survive unchanged (C-CONF-1: one authority, no parallel store).
"""

from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path
from typing import Any

from voice_typer.server.plugins.registry import PluginInfo, PluginSetting

CONFIG_NAME = "config.json"
MAX_SETTINGS_BYTES = 64 * 1024
_MAX_STRING_LEN = 8192

_write_lock = threading.Lock()


class PluginSettingError(ValueError):
    """Rejected plugin setting write (unknown plugin/key, wrong type/range)."""


def _path(info: PluginInfo) -> Path:
    return Path(info.directory) / CONFIG_NAME


def _coerce(spec: PluginSetting, value: object) -> Any:
    if spec.type == "bool":
        if not isinstance(value, bool):
            raise PluginSettingError(f"{spec.key} must be a boolean")
        return value
    if spec.type in ("int", "float"):
        # bool is an int subclass; a toggle must not arrive as a number.
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise PluginSettingError(f"{spec.key} must be a number")
        if spec.type == "int" and not isinstance(value, int):
            raise PluginSettingError(f"{spec.key} must be an integer")
        if isinstance(value, float) and not math.isfinite(value):
            raise PluginSettingError(f"{spec.key} must be finite")
        if spec.minimum is not None and value < spec.minimum:
            raise PluginSettingError(f"{spec.key} must be >= {spec.minimum}")
        if spec.maximum is not None and value > spec.maximum:
            raise PluginSettingError(f"{spec.key} must be <= {spec.maximum}")
        return value
    if spec.type == "enum":
        if not isinstance(value, str) or value not in spec.choices:
            raise PluginSettingError(f"{spec.key} must be one of {list(spec.choices)}")
        return value
    if not isinstance(value, str):
        raise PluginSettingError(f"{spec.key} must be a string")
    if len(value) > _MAX_STRING_LEN:
        raise PluginSettingError(f"{spec.key} is too long")
    return value


def _read_raw(info: PluginInfo) -> dict[str, Any]:
    path = _path(info)
    try:
        if path.stat().st_size > MAX_SETTINGS_BYTES:
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_values(info: PluginInfo) -> dict[str, Any]:
    """Stored values for the settings this plugin still declares."""
    raw = _read_raw(info)
    by_key = {spec.key: spec for spec in info.settings}
    values: dict[str, Any] = {}
    for key, value in raw.items():
        spec = by_key.get(key)
        if spec is None:
            continue
        try:
            values[key] = _coerce(spec, value)
        except PluginSettingError:
            continue
    return values


def set_value(info: PluginInfo, key: str, value: object) -> Any:
    """Validate and persist one setting; returns the stored value."""
    spec = next((s for s in info.settings if s.key == key), None)
    if spec is None:
        raise PluginSettingError(f"unknown setting {key!r}")
    coerced = _coerce(spec, value)
    with _write_lock:
        # Read the WHOLE config so daemon-owned keys survive the rewrite.
        current = _read_raw(info)
        current[key] = coerced
        path = _path(info)
        tmp = path.with_name(CONFIG_NAME + ".tmp")
        # Atomic replace: a crash mid-write must never truncate the store.
        tmp.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    return coerced


__all__ = ["PluginSettingError", "load_values", "set_value"]
