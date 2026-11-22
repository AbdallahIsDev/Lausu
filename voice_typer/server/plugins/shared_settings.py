"""Shared plugin settings: canonical in the main config, projected to daemons.

The application ``config.json`` is the ONLY authority for ``plugin_visible``
and ``plugin_notify`` (C-CONF-1). Each plugin daemon is an external Node
process that reads its own ``config.json``, so this module writes those two
values there as a derived projection on every change and at startup. No
plugin owns a separate settings store and no plugin declares these in its
manifest.

``plugin_notify`` is read by the daemon on every notification, so a projection
is immediately effective. ``plugin_visible`` is read when Chrome is launched;
a change also applies to the running browser through the no-activation window
helper so the user sees the effect without a restart or a focus steal.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from voice_typer.server.plugins.registry import discover

log = logging.getLogger(__name__)

# Main config field <-> key in each plugin's own config.json.
CONFIG_KEYS: dict[str, str] = {"visible": "plugin_visible", "notify": "plugin_notify"}
MAX_CONFIG_BYTES = 64 * 1024

_write_lock = threading.Lock()


def values_from_config(config: Any) -> dict[str, bool]:
    return {key: bool(getattr(config, field, True)) for key, field in CONFIG_KEYS.items()}


def _write_projection(directory: str, values: dict[str, bool]) -> None:
    path = Path(directory) / "config.json"
    try:
        if path.stat().st_size > MAX_CONFIG_BYTES:
            log.warning("[PLUGINS] config too large to project settings: %s", directory)
            return
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return
    except (OSError, ValueError):
        return
    updated = dict(raw)
    updated.update(values)
    tmp = path.with_name("config.json.tmp")
    tmp.write_text(json.dumps(updated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sync_all(config: Any) -> None:
    """Project the canonical values into every installed plugin's config."""
    values = values_from_config(config)
    with _write_lock:
        for info in discover():
            _write_projection(info.directory, values)


def apply_live_visible(config: Any) -> None:
    """Apply `plugin_visible` to the active plugin's browser right now."""
    plugin_id = str(getattr(config, "active_plugin", "") or "")
    if not plugin_id:
        return
    info = next((p for p in discover() if p.id == plugin_id), None)
    if info is None:
        return
    try:
        from tools.internal_plugins._common.bridge import chrome_profile

        threading.Thread(
            target=chrome_profile.set_window_visible,
            args=(info.directory, bool(getattr(config, "plugin_visible", True))),
            kwargs={"wait_s": 1.0},
            name="plugin-visibility-apply",
            daemon=True,  # RACE-008: best-effort UI effect must not block exit.
        ).start()
    except Exception:
        log.debug("[PLUGINS] live visibility apply failed", exc_info=True)
