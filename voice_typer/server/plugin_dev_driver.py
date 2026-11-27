"""Dev-only command channel into the REAL dictation entry points.

Never active in a frozen/frozen-install build and never staged into the
packaged plugin bundle: the workspace marker is gitignored and the stager
skips it. Commands call the same wrapped methods the hotkey calls; no OS key
injection is involved (C-HOOK-1). A command written before this process
started is stale and is never executed.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_START_COMMANDS = frozenset({"toggle", "hotkey", "button", "tray", "start"})
_OTHER_COMMANDS = frozenset({"stop", "cancel", "status"})
_ORIGIN_FOR_COMMAND = {"hotkey": "hotkey", "button": "button", "tray": "tray"}


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
    # Two overlapping dev processes can replace the same result file; a short
    # bounded retry keeps a dev-only watcher from crashing the host thread.
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05 * (attempt + 1))
    tmp.unlink(missing_ok=True)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _claim(directory: Path, started_at: float, last_seq: int) -> tuple[Path, dict, int] | None:
    """Take ownership of one fresh command before it can be overwritten."""
    source = directory / "command.json"
    try:
        if source.stat().st_mtime < started_at:
            # A command from a previous process is never a request in THIS one.
            source.unlink(missing_ok=True)
            return None
    except OSError:
        return None
    command = _read_json(source)
    seq = command.get("seq") if command else None
    if not command or not isinstance(seq, int) or seq <= last_seq:
        return None
    if command.get("cmd") not in _START_COMMANDS | _OTHER_COMMANDS:
        return None
    claimed = directory / f"command.json.{seq}.claimed"
    try:
        os.replace(source, claimed)
    except OSError:
        return None
    return claimed, command, seq


def run_watcher(app: Any, stop_event: threading.Event, started_at: float | None = None) -> None:
    """One fresh command per poll; fakes only at OS boundary in tests."""
    if not enabled(app):
        return
    if started_at is None:
        started_at = time.time()
    last_seq = 0
    while not stop_event.is_set():
        directory = command_dir(app)
        claim = _claim(directory, started_at, last_seq)
        if claim is not None:
            claimed, command, seq = claim
            last_seq = seq
            try:
                result = _execute(app, command)
                result["seq"] = seq
                _write_atomic(directory / "result.json", result)
            finally:
                # Consumed commands never survive to the next app launch.
                claimed.unlink(missing_ok=True)
        stop_event.wait(0.05)


def _execute(app: Any, command: dict) -> dict:
    from voice_typer.server import dictation_origin

    name = command.get("cmd")
    origin = _ORIGIN_FOR_COMMAND.get(name, "dev-driver") if name in _START_COMMANDS else ""
    try:
        if name in _START_COMMANDS:
            with dictation_origin.user_action(origin):
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
        args=(app, stop_event, time.time()),
        stop_event=stop_event,
        join_timeout=1.0,
    )
    return stop_event
