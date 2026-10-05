"""Discovery of installed plugins.

Plugins live OUTSIDE the package (``tools/internal_plugins/<id>/``) and are
gitignored: a public build ships none of them, so discovery returns an empty
list and the app behaves exactly as before. Nothing here imports a plugin - a
plugin is described by its ``plugin.json`` manifest, and the manifest is the
only thing the shipped app reads.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Declared inline rather than imported from ``handlers._log``: that module
# pulls in the handler package, which imports the plugin handler, which
# imports this one. A module logger keeps discovery import-cycle free.
log = logging.getLogger("voice_typer.server.plugins")

MANIFEST_NAME = "plugin.json"
MAX_MANIFEST_BYTES = 64 * 1024

# Plugins are identified by a lowercase slug; the same rule the
# ``active_plugin`` config validator enforces.
_PLUGIN_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")

_SETTING_TYPES = frozenset({"bool", "int", "float", "string", "enum"})


@dataclass(frozen=True)
class PluginSetting:
    """One user-tunable option a plugin exposes on its detail page."""

    key: str
    type: str
    label: str
    default: Any = None
    description: str = ""
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"key": self.key, "type": self.type, "label": self.label}
        if self.description:
            out["description"] = self.description
        if self.default is not None:
            out["default"] = self.default
        if self.choices:
            out["choices"] = list(self.choices)
        if self.minimum is not None:
            out["min"] = self.minimum
        if self.maximum is not None:
            out["max"] = self.maximum
        return out


@dataclass(frozen=True)
class PluginInfo:
    """A discovered plugin, as the Plugins page renders it."""

    id: str
    name: str
    description: str = ""
    vendor: str = ""
    icon: str = ""
    settings: tuple[PluginSetting, ...] = field(default_factory=tuple)
    directory: str = ""

    def to_dict(self, *, active: bool = False, values: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "vendor": self.vendor,
            "icon": self.icon,
            "active": active,
            "settings": [s.to_dict() for s in self.settings],
            "values": values or {},
        }


def plugins_dir() -> Path | None:
    """The plugin workspace, or ``None`` when this build has none."""
    override = os.environ.get("VOICE_TYPER_PLUGINS_DIR")
    if override:
        # A missing override is still "no workspace": returning the path
        # unconditionally would make the visibility gate report a workspace
        # that cannot exist.
        candidate = Path(override)
        return candidate if candidate.is_dir() else None
    # voice_typer/server/plugins/registry.py -> repo root is three levels up.
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "tools" / "internal_plugins"
    return candidate if candidate.is_dir() else None


def _valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and set(value) <= _PLUGIN_ID_CHARS
        and len(value) <= 64
    )


def _parse_setting(raw: object) -> PluginSetting | None:
    if not isinstance(raw, dict):
        return None
    key, stype, label = raw.get("key"), raw.get("type"), raw.get("label")
    if not (isinstance(key, str) and key) or stype not in _SETTING_TYPES or not isinstance(label, str):
        return None
    choices = raw.get("choices", [])
    if not isinstance(choices, list) or not all(isinstance(c, str) for c in choices):
        return None
    description = raw.get("description", "")
    return PluginSetting(
        key=key,
        type=stype,
        label=label,
        default=raw.get("default"),
        description=description if isinstance(description, str) else "",
        choices=tuple(choices),
        minimum=raw.get("min") if isinstance(raw.get("min"), (int, float)) else None,
        maximum=raw.get("max") if isinstance(raw.get("max"), (int, float)) else None,
    )


def _text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key, "")
    return value if isinstance(value, str) else ""


def _read_manifest(plugin_dir: Path) -> PluginInfo | None:
    manifest_path = plugin_dir / MANIFEST_NAME
    try:
        if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
            log.warning("[PLUGINS] manifest too large, skipping: %s", plugin_dir.name)
            return None
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("[PLUGINS] unreadable manifest in %s: %s", plugin_dir.name, exc)
        return None
    if not isinstance(raw, dict) or not _valid_id(raw.get("id")):
        log.warning("[PLUGINS] manifest without a valid id, skipping: %s", plugin_dir.name)
        return None
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        log.warning("[PLUGINS] manifest without a name, skipping: %s", plugin_dir.name)
        return None
    raw_settings = raw.get("settings", [])
    settings: tuple[PluginSetting, ...] = ()
    if isinstance(raw_settings, list):
        settings = tuple(s for s in (_parse_setting(item) for item in raw_settings) if s is not None)
    return PluginInfo(
        id=raw["id"],
        name=name,
        description=_text(raw, "description"),
        vendor=_text(raw, "vendor"),
        icon=_text(raw, "icon"),
        settings=settings,
        directory=str(plugin_dir),
    )


def discover() -> list[PluginInfo]:
    """Every plugin installed on this machine, sorted by display name.

    Returns ``[]`` for a build with no plugin workspace, which is the normal
    shipped case. A single broken manifest never hides the others.
    """
    workspace = plugins_dir()
    if workspace is None or not workspace.is_dir():
        return []
    found: list[PluginInfo] = []
    for entry in sorted(workspace.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "_")):
            continue
        info = _read_manifest(entry)
        if info is not None:
            found.append(info)
    found.sort(key=lambda p: p.name.lower())
    return found


def get_plugin(plugin_id: str) -> PluginInfo | None:
    for info in discover():
        if info.id == plugin_id:
            return info
    return None
