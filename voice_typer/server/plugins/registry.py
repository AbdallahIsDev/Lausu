"""Discovery of installed plugins.

Plugins live OUTSIDE the package (``tools/internal_plugins/<id>/``): the
source is tracked in the repository, and a packaged build ships that same
tree as data files while keeping the surface locked (a developer-mode flag
the owner unlocks in-app). ``resolve_plugins_dir`` owns where the workspace
actually is - checkout, seeded per-user copy, or an override. Nothing here
imports a plugin: a plugin is described by its ``plugin.json`` manifest, and
the manifest is the only thing the app reads.

Settings are NOT declared here. Both plugins share the same user settings in
the main application config (``plugin_visible`` / ``plugin_notify``), so a
manifest only describes identity, not configuration.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
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


@dataclass(frozen=True)
class PluginInfo:
    """A discovered plugin, as the Plugins page renders it."""

    id: str
    name: str
    description: str = ""
    vendor: str = ""
    icon: str = ""
    directory: str = ""

    def to_dict(self, *, active: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "vendor": self.vendor,
            "icon": self.icon,
            "active": active,
        }


def plugins_dir() -> Path | None:
    """The plugin workspace, or ``None`` when this install has none.

    Resolution (checkout vs packaged, and the writable per-user copy a
    packaged build seeds on unlock) lives in
    :mod:`voice_typer.server.plugins.workspace`.
    """
    from voice_typer.server.plugins.workspace import resolve_plugins_dir

    return resolve_plugins_dir()


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(value) and set(value) <= _PLUGIN_ID_CHARS and len(value) <= 64


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
    return PluginInfo(
        id=raw["id"],
        name=name,
        description=_text(raw, "description"),
        vendor=_text(raw, "vendor"),
        icon=_text(raw, "icon"),
        directory=str(plugin_dir),
    )


def discover() -> list[PluginInfo]:
    """Every plugin installed on this machine, sorted by display name.

    Returns ``[]`` when there is no usable workspace - a packaged install
    that was never unlocked has none. A single broken manifest never hides
    the others.
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
