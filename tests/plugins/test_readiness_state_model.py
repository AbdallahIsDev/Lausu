"""One-call readiness state, truthful transitions and real recovery (A3)."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from tools.internal_plugins._common.bridge.daemon_client import DaemonClient

_PLUGIN_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"


@pytest.fixture
def plugin(monkeypatch):
    name = "anthropic_stt_state_model_under_test"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, _PLUGIN_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ensure_daemon", lambda: True)
    return module


def _ready(**overrides):
    base = {
        "browser": "connected",
        "page": "ok",
        "hasTab": True,
        "micCount": 1,
        "selectorsReady": True,
        "readiness": {
            "browser": "up",
            "tab": "ready",
            "content_script": "present",
            "control": "present",
            "signed_in": "unknown",
            "document_ready": True,
            "control_stable": True,
            "tab_quiet_ms": 500,
            "reason": "ready",
        },
    }
    base.update(overrides)
    return base


def _missing():
    return _ready(
        page="unknown",
        micCount=0,
        selectorsReady=False,
        readiness={
            "browser": "up",
            "tab": "missing",
            "content_script": "absent",
            "control": "missing",
            "signed_in": "unknown",
            "document_ready": False,
            "control_stable": False,
            "tab_quiet_ms": 0,
            "reason": "tab.missing",
        },
    )


def test_readiness_state_uses_the_extension_tuple():
    state = DaemonClient.readiness_state(_missing())
    assert state["tab"] == "missing" and state["reason"] == "tab.missing"
    assert state["document_ready"] is False and state["control_stable"] is False
    # A legacy extension without the field still gets a truthful fallback.
    legacy = _ready()
    legacy.pop("readiness")
    assert DaemonClient.readiness_state(legacy)["reason"] == "readiness.incomplete"


class _SessionHarness:
    def __init__(self, plugin, monkeypatch, snapshots):
        self.session = plugin.PluginSession(MagicMock())
        self.posts: list[str] = []
        self.notes: list[str] = []
        self.snapshots = snapshots
        monkeypatch.setattr(self.session, "_ensure_daemon", lambda: True)
        monkeypatch.setattr(self.session, "_ensure_browser", lambda timeout=None: True)
        monkeypatch.setattr(self.session, "_status", lambda: next(self.snapshots, _ready()))
        monkeypatch.setattr(self.session, "_watch_platform", lambda: None)
        monkeypatch.setattr(self.session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(self.session, "_duck", lambda: None)
        monkeypatch.setattr(self.session, "_restore_volume", lambda: None)
        monkeypatch.setattr(self.session, "_notify", self.notes.append)
        monkeypatch.setattr(self.session, "_post", self._post)
        monkeypatch.setattr(plugin.time, "sleep", lambda *_: None)

        class FakeMeter:
            def __init__(self, app):
                pass

            def start(self):
                pass

            def stop(self):
                pass

        monkeypatch.setattr(plugin, "LevelMeter", FakeMeter)

    def _post(self, path, timeout=None):
        self.posts.append(path)
        return {}


def test_closed_tab_is_repaired_by_one_ensure_then_ready(plugin, monkeypatch):
    harness = _SessionHarness(plugin, monkeypatch, iter([_missing(), _ready()]))

    harness.session.start()

    assert harness.session.active is True
    assert harness.posts == ["/ensure-tab", "/start"]


def test_signed_out_fails_fast_with_a_real_message(plugin, monkeypatch):
    signed_out = _ready(
        page="signed_out",
        micCount=0,
        readiness={
            "browser": "up",
            "tab": "ready",
            "content_script": "present",
            "control": "missing",
            "signed_in": "no",
            "document_ready": True,
            "control_stable": False,
            "tab_quiet_ms": 500,
            "reason": "signed_in.no",
        },
    )
    harness = _SessionHarness(plugin, monkeypatch, iter([signed_out]))
    monkeypatch.setattr(plugin.session, "_PAGE_READY_TIMEOUT_S", 30.0)

    harness.session.start()

    assert harness.session.active is False
    assert harness.notes and "sign in" in harness.notes[-1].lower()
    assert "/start" not in harness.posts


def test_readiness_is_logged_once_per_transition(plugin, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="voice_typer.internal_plugin.anthropic_stt")
    harness = _SessionHarness(plugin, monkeypatch, iter([_missing(), _missing(), _ready()]))

    harness.session.start()

    lines = [r.getMessage() for r in caplog.records if "readiness (cycle=#" in r.getMessage()]
    assert len(lines) == 2, lines
    assert "tab=missing" in lines[0] and "reason=tab.missing" in lines[0]
    assert "reason=ready" in lines[1]
