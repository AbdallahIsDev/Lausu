"""A vanished tab during auto-stop is one line, no traceback, no POST."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"


@pytest.fixture
def plugin(monkeypatch):
    name = "anthropic_stt_stop_missing_under_test"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, _PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


def test_stop_with_a_missing_tab_never_posts_and_logs_one_warning(plugin, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG, logger="voice_typer.internal_plugin.anthropic_stt")
    session = plugin.PluginSession(MagicMock())
    posts: list[str] = []
    notes: list[str] = []
    monkeypatch.setattr(session, "_post", lambda path, timeout=None: posts.append(path) or {})
    monkeypatch.setattr(session, "_notify", notes.append)
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
    with session._lock:
        session._active = True
        session._t0 = 10.0

    session.stop()

    assert posts == [], "no /stop POST into a tab that does not exist"
    warns = [r for r in caplog.records if r.levelno == logging.WARNING and "stop lost the browser" in r.getMessage()]
    assert len(warns) == 1
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors == []
    assert not any("Traceback" in r.getMessage() for r in caplog.records)
    assert any("nothing was captured" in str(call.args[-1]).lower() for call in session._app.tray.notify.call_args_list)
