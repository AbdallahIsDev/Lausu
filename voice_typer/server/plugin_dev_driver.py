"""Dev-only command channel into the REAL dictation entry points.

Never present in a frozen/frozen-install build and never staged into the
packaged plugin bundle: the workspace marker is gitignored and the stager
skips it. Commands call the same wrapped methods the hotkey calls; no OS key
injection is involved (C-HOOK-1).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def enabled(app: Any) -> bool:
    from voice_typer.server.internal_plugin_hook import internal_surface_enabled
    from voice_typer.server.plugins.registry import plugins_dir

    if os.environ.get("VOICE_TYPER_FROZEN") == "1":
        return False
    if getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None):
        return False
    if not internal_surface_enabled(getattr(app, "config", None)):
        return False
    root = plugins_dir()
    return root is not None and (
        os.environ.get("VOICE_TYPER_PLUGIN_DIAGNOSTICS") == "1" or (root / "DEVELOPER_DIAGNOSTICS").is_file()
    )


def command_dir(app: Any) -> Path:
    from voice_typer.server.plugins.registry import plugins_dir

    root = plugins_dir()
    assert root is not None
    path = root / "debug" / "dev-command"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_atomic(path: Path, payload: dict) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def run_watcher(app: Any, stop_event: threading.Event) -> None:
    """One command per poll; fakes only at OS boundary in tests."""
    last_seq = 0
    while not stop_event.is_set():
        if not enabled(app):
            return
        directory = command_dir(app)
        command = _read_json(directory / "command.json")
        seq = command.get("seq") if command else None
        if command and isinstance(seq, int) and seq > last_seq:
            last_seq = seq
            result = _execute(app, command)
            result["seq"] = seq
            _write_atomic(directory / "result.json", result)
        stop_event.wait(0.05)


def _execute(app: Any, command: dict) -> dict:
    name = command.get("cmd")
    try:
        if name == "toggle":
            app.toggle_dictation()
        elif name == "stop":
            app._stop_dictation()
        elif name == "cancel":
            app._cancel_dictation()
        elif name != "status":
            return {"ok": False, "error": "unknown_command"}
    except Exception as exc:
        return {"ok": False, "error": exc.__class__.__name__.lower()}
    tray = getattr(app, "tray", None)
    return {
        "ok": True,
        "state": str(getattr(getattr(tray, "_state", None), "value", "unknown")),
        "recording": bool(getattr(getattr(app, "recorder", None), "recording", False)),
    }


def start_watcher(app: Any) -> threading.Event | None:
    if not enabled(app):
        return None
    stop_event = threading.Event()
    registry = getattr(app, "_thread_registry", None)
    if registry is None:
        return None
    # RACE-008: daemon=True so a dev-only watcher never holds process exit;
    # stop_event is checked every poll and on teardown.
    registry.spawn_and_register(
        name="dev-command-watcher",
        target=run_watcher,
        args=(app, stop_event),
        stop_event=stop_event,
        join_timeout=1.0,
    )
    return stop_event
