"""Proves the Plugins page notification switch reaches the code that notifies.

The knob is declared in plugin.json and persisted to config.json by the app.
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
sys.modules[_spec.name] = plugin  # plugin.py binds its entry at import time
_spec.loader.exec_module(plugin)

_failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _failed
    if not ok:
        _failed += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -- ' + detail if detail else ''}")


def with_config(raw: str | None) -> pathlib.Path:
    directory = pathlib.Path(tempfile.mkdtemp(prefix="anthropic-stt-notify-"))
    if raw is not None:
        (directory / "config.json").write_text(raw, encoding="utf-8")
    return directory


check("no config.json means notifications are on", plugin._notify_enabled(with_config(None)))
check(
    "notify=false is honoured",
    not plugin._notify_enabled(with_config(json.dumps({"notify": False}))),
)
check(
    "notify=true is honoured",
    plugin._notify_enabled(with_config(json.dumps({"notify": True}))),
)
check(
    "an invalid value falls back to on",
    plugin._notify_enabled(with_config(json.dumps({"notify": "no"}))),
)
check("invalid JSON falls back to on", plugin._notify_enabled(with_config("{not json")))


class _Tray:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def notify(self, title: str, message: str) -> None:
        self.calls.append(message)


class _App:
    def __init__(self) -> None:
        self.tray = _Tray()


# The gate must be enforced by PluginSession._notify, not only by the helper.
# Patch the helper the session actually calls (it takes no directory argument),
# so the check tests the session's enforcement rather than config file lookup.
def delivered(enabled: bool) -> int:
    original = plugin._copy.notify_enabled
    plugin._copy.notify_enabled = lambda: enabled
    try:
        app = _App()
        plugin.PluginSession(app)._notify("empty transcript")
        return len(app.tray.calls)
    finally:
        plugin._copy.notify_enabled = original


check("a muted session sends no tray notification", delivered(False) == 0)
check("an unmuted session sends one", delivered(True) == 1)
check("a missing config.json still notifies", plugin._notify_enabled(with_config(None)))

print(f"\n{'all checks passed' if _failed == 0 else f'{_failed} check(s) failed'}")
raise SystemExit(1 if _failed else 0)
