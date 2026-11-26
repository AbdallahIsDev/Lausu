"""Dev channel enters the REAL wrapped hotkey entry (no key injection)."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from voice_typer.server import plugin_dev_driver


def test_dev_watcher_is_absent_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert plugin_dev_driver.enabled(SimpleNamespace()) is False


def test_dev_channel_executes_real_toggle_once(tmp_path, monkeypatch):
    from voice_typer.server import internal_plugin_hook

    root = tmp_path / "plugins"
    root.mkdir(parents=True, exist_ok=True)
    (root / "DEVELOPER_DIAGNOSTICS").write_text("dev", encoding="utf-8")
    monkeypatch.setattr("voice_typer.server.plugins.registry.plugins_dir", lambda: root)
    monkeypatch.setenv("VOICE_TYPER_INTERNAL_PLUGINS", "1")
    monkeypatch.setattr(internal_plugin_hook, "internal_surface_enabled", lambda _config: True)

    calls = []
    app = SimpleNamespace(
        config=SimpleNamespace(developer_mode=True),
        _thread_registry=SimpleNamespace(spawn_and_register=lambda **kwargs: None),
        toggle_dictation=lambda: calls.append("toggle"),
        _stop_dictation=lambda: calls.append("stop"),
        _cancel_dictation=lambda: calls.append("cancel"),
        tray=SimpleNamespace(_state=None),
    )
    directory = plugin_dev_driver.command_dir(app)
    payload = {"seq": 7, "cmd": "toggle"}
    (directory / "command.json").write_text(json.dumps(payload), encoding="utf-8")

    class OnePollStop:
        def __init__(self):
            self.calls = 0

        def is_set(self):
            self.calls += 1
            return self.calls > 1

        def wait(self, _seconds):
            return None

    monkeypatch.setattr(plugin_dev_driver, "enabled", lambda _app: True)
    plugin_dev_driver.run_watcher(app, OnePollStop())

    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    assert result["seq"] == 7 and result["ok"] is True
    assert calls == ["toggle"], "must enter through the real toggle_dictation wrapper"
