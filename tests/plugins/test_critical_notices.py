"""Critical notices bypass notify=False; routine notices do not."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"


@pytest.fixture
def plugin(monkeypatch):
    name = "anthropic_stt_critical_notice_under_test"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, _PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    monkeypatch.setattr(module._copy, "notify_enabled", lambda: False)
    return module


def _session(plugin, monkeypatch, events):
    app = MagicMock()
    app.tray.notify.side_effect = lambda title, msg: events.append(("os", msg))
    session = plugin.PluginSession(app)
    monkeypatch.setattr(session, "_session_events", lambda *, start: None)
    monkeypatch.setattr(session, "_publish_state", lambda state: None)
    monkeypatch.setattr(session, "_stop_meter", lambda: None)
    monkeypatch.setattr(session, "_restore_volume", lambda: None)
    monkeypatch.setattr(
        session,
        "_status",
        lambda: {
            "browser": "connected",
            "page": "unknown",
            "hasTab": False,
            "readiness": {
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
        },
    )
    monkeypatch.setattr(session, "_post", lambda path, timeout=None: {})
    return session


def test_browser_loss_during_stop_notifies_both_channels(plugin, monkeypatch):
    from voice_typer.server import event_bus

    events: list[tuple[str, str]] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: events.append(("app", event["data"]["message"])))
    session = _session(plugin, monkeypatch, events)
    with session._lock:
        session._active = True
        session._t0 = 1.0

    session.stop()

    kinds = {kind for kind, _ in events}
    assert kinds == {"os", "app"}
    assert "nothing was captured" in events[0][1].lower()
    assert len(events) == 2, "one OS + one in-app, never a duplicate"


def test_routine_notice_still_obeys_notify_false(plugin, monkeypatch, caplog):
    events: list[tuple[str, str]] = []
    session = _session(plugin, monkeypatch, events)
    session._notify("routine activation done")
    assert events == []
