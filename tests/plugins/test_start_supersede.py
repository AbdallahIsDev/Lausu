"""A new press must supersede a stuck start instead of waiting behind it."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"


@pytest.fixture
def plugin(monkeypatch):
    name = "anthropic_stt_supersede_under_test"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, _PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


def test_press_during_start_bumps_generation_and_requests_restart(plugin, monkeypatch):
    session = plugin.PluginSession(MagicMock())
    calls: list[str] = []
    monkeypatch.setattr(session, "start", lambda: calls.append("start"))
    monkeypatch.setattr(session, "stop", lambda: calls.append("stop"))

    session.toggle()  # first press starts
    assert calls == ["start"]

    with session._lock:
        session._starting = True
        session._busy = True
    session.toggle()  # second press supersedes the in-flight start

    with session._lock:
        assert session._start_generation == 1
        assert session._restart_requested is True
    assert calls == ["start"], "the superseding start runs only after the old one exits"
