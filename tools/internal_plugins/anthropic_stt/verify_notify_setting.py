"""Proves the Plugins page notification switch reaches the code that notifies.

The knob is declared in plugin.json and persisted to settings.json by the app.
Before this guard existed, ``_notify`` fired unconditionally: the checkbox was
a write path with no read path (AGENTS.md C-UI-17).

Run: python verify_notify_setting.py
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile

PLUGIN_PATH = pathlib.Path(__file__).with_name("plugin.py")
_ROOT = PLUGIN_PATH.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_spec = importlib.util.spec_from_file_location("anthropic_stt_plugin", PLUGIN_PATH)
plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin)

_failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _failed
    if not ok:
        _failed += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -- ' + detail if detail else ''}")


def with_settings(raw: str | None) -> pathlib.Path:
    directory = pathlib.Path(tempfile.mkdtemp(prefix="anthropic-stt-notify-"))
    if raw is not None:
        (directory / "settings.json").write_text(raw, encoding="utf-8")
    return directory


check("no settings.json means notifications are on", plugin._notify_enabled(with_settings(None)))
check(
    "notify=false is honoured",
    not plugin._notify_enabled(with_settings(json.dumps({"notify": False}))),
)
check(
    "notify=true is honoured",
    plugin._notify_enabled(with_settings(json.dumps({"notify": True}))),
)
check(
    "an invalid value falls back to on",
    plugin._notify_enabled(with_settings(json.dumps({"notify": "no"}))),
)
check("invalid JSON falls back to on", plugin._notify_enabled(with_settings("{not json")))


class _Tray:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def notify(self, title: str, message: str) -> None:
        self.calls.append(message)


class _App:
    def __init__(self) -> None:
        self.tray = _Tray()


# The gate must be enforced by PluginSession._notify, not only by the helper.
def delivered(raw: str | None) -> int:
    directory = with_settings(raw)
    original = plugin.HERE
    plugin.HERE = directory
    try:
        app = _App()
        plugin.PluginSession(app)._notify("empty transcript")
        return len(app.tray.calls)
    finally:
        plugin.HERE = original


check("a muted session sends no tray notification", delivered(json.dumps({"notify": False})) == 0)
check("an unmuted session sends one", delivered(json.dumps({"notify": True})) == 1)
check("a missing settings.json still notifies", delivered(None) == 1)

print(f"\n{'all checks passed' if _failed == 0 else f'{_failed} check(s) failed'}")
raise SystemExit(1 if _failed else 0)
