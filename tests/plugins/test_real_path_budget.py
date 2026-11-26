"""REAL-PATH TEST RULE: budget must survive the actual start entry."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from tests.plugins.conftest import ready_snapshot

_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"


@pytest.fixture
def plugin(monkeypatch):
    name = "anthropic_stt_real_path_budget_under_test"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, _PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


def test_toggle_entry_passes_budget_to_browser_layer(plugin, monkeypatch):
    session = plugin.PluginSession(MagicMock())
    monkeypatch.setattr(session, "_ensure_daemon", lambda: True)
    seen = {}

    def fake_ensure_browser(timeout=None, *, force=False, budget=None, caller="hotkey-start"):
        seen["budget"] = budget
        seen["force"] = force
        seen["caller"] = caller
        return True

    monkeypatch.setattr(session, "_ensure_browser", fake_ensure_browser)
    states = iter([ready_snapshot(), ready_snapshot(), ready_snapshot()])
    monkeypatch.setattr(session, "_status", lambda: next(states, ready_snapshot()))
    monkeypatch.setattr(session, "_post", lambda path, timeout=None: {})
    monkeypatch.setattr(session, "_watch_platform", lambda: None)
    monkeypatch.setattr(plugin.time, "sleep", lambda *_: None)
    monkeypatch.setattr(session, "_session_events", lambda *, start: None)
    monkeypatch.setattr(session, "_duck", lambda: None)
    monkeypatch.setattr(session, "_restore_volume", lambda: None)

    class FakeMeter:
        def __init__(self, app):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(plugin, "LevelMeter", FakeMeter)

    session.toggle()

    assert seen.get("budget") is not None, "budget was dropped on the real entry path"
    assert seen.get("caller") == "hotkey-start"
    assert session.active is True
