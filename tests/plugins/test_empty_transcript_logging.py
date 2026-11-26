"""An empty result must be diagnosable from lausu.log alone (A5)."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PLUGIN_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "google_stt" / "plugin.py"


@pytest.fixture
def plugin(monkeypatch):
    name = "google_stt_empty_log_under_test"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, _PLUGIN_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


def test_empty_after_stop_logs_the_control_and_the_verdict(plugin, monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="voice_typer.internal_plugin.google_stt")
    session = plugin.PluginSession(MagicMock())
    monkeypatch.setattr(session, "_session_events", lambda *, start: None)
    monkeypatch.setattr(session, "_notify", lambda msg: None)
    res = {
        "text": "",
        "empty_reason": "empty_after_stop",
        "state": "recording",
        "state_after": "signal_disagreement",
        "control": "Stop dictation (^D)|button|32x32",
        "committed": True,
        "click_ms": 415,
        "scrape_ms": 1311,
    }

    session._finish(res, cycle=1, elapsed=1.7)

    lines = [r.getMessage() for r in caplog.records if "no transcript" in r.getMessage()]
    assert lines
    line = lines[0]
    assert "verdict=no-speech" in line
    assert "reason=empty_after_stop" in line
    assert "page_state=signal_disagreement" in line
    assert "control=Stop dictation" in line
    assert "committed=True" in line
    assert "click=415ms" in line and "scrape=1311ms" in line
