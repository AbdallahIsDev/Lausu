"""A connected bridge is not a ready page (P2).

The hotkey must not click a dictation control before the tab has loaded,
hydrated and exposed the mic. The readiness verdict is derived from facts
reported by the content script, not from socket state.
"""

from __future__ import annotations

import importlib.util
import sys
from unittest.mock import MagicMock

import pytest
from tests.plugins.conftest import control_posts
from tools.internal_plugins._common.bridge.daemon_client import DaemonClient

_PLUGIN_PATH = (
    __import__("pathlib").Path(__file__).resolve().parents[2]
    / "tools"
    / "internal_plugins"
    / "anthropic_stt"
    / "plugin.py"
)


@pytest.fixture
def plugin(monkeypatch):
    name = "anthropic_stt_readiness_under_test"
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


def test_page_ready_requires_browser_page_mic_and_selectors() -> None:
    ready = {
        "browser": "connected",
        "page": "ok",
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
    assert DaemonClient.page_ready(ready) is True
    assert (
        DaemonClient.page_ready(
            {**ready, "readiness": {**ready["readiness"], "tab": "loading", "reason": "tab.loading"}}
        )
        is False
    )
    assert DaemonClient.page_ready({**ready, "readiness": {**ready["readiness"], "document_ready": False}}) is False
    assert DaemonClient.page_ready({**ready, "readiness": {**ready["readiness"], "control_stable": False}}) is False
    assert DaemonClient.page_ready({**ready, "micCount": 0}) is False
    assert DaemonClient.page_ready({**ready, "selectorsReady": False}) is False
    assert DaemonClient.page_ready({**ready, "page": "signed_out"}) is False
    assert DaemonClient.page_ready({**ready, "browser": "disconnected"}) is False


class TestStartWaitsForARealMic:
    def _session(self, plugin, monkeypatch):
        session = plugin.PluginSession(MagicMock())
        monkeypatch.setattr(session, "_ensure_daemon", lambda: True)
        monkeypatch.setattr(session, "_ensure_browser", lambda timeout=None: True)
        monkeypatch.setattr(session, "_watch_platform", lambda: None)
        monkeypatch.setattr(session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(session, "_duck", lambda: None)
        monkeypatch.setattr(session, "_restore_volume", lambda: None)
        monkeypatch.setattr(session, "_notify", lambda msg: None)

        class FakeMeter:
            def __init__(self, app):
                pass

            def start(self):
                pass

            def stop(self):
                pass

        monkeypatch.setattr(plugin, "LevelMeter", FakeMeter)
        return session

    def test_start_does_not_post_before_the_mic_exists(self, plugin, monkeypatch):
        session = self._session(plugin, monkeypatch)
        base = {
            "browser": "connected",
            "page": "ok",
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
        not_ready = {
            **base,
            "micCount": 0,
            "readiness": {**base["readiness"], "control": "missing", "reason": "control.missing"},
        }
        states = iter([not_ready, base, base])
        last = base
        monkeypatch.setattr(session, "_status", lambda: next(states, last))
        posts: list[str] = []
        monkeypatch.setattr(session, "_post", lambda path, timeout=None: posts.append(path) or {})
        monkeypatch.setattr(plugin.time, "sleep", lambda *_: None)

        session.start()

        assert session.active is True
        assert control_posts(posts) == ["/ensure-tab", "/start"], posts

    def test_start_refuses_when_the_page_never_becomes_ready(self, plugin, monkeypatch):
        session = self._session(plugin, monkeypatch)
        monkeypatch.setattr(
            session,
            "_status",
            lambda: {"browser": "connected", "page": "ok", "micCount": 0, "selectorsReady": True},
        )
        posts: list[str] = []
        notes: list[str] = []
        monkeypatch.setattr(session, "_post", lambda path, timeout=None: posts.append(path) or {})
        monkeypatch.setattr(session, "_notify", notes.append)
        monkeypatch.setattr(plugin.time, "sleep", lambda *_: None)
        monkeypatch.setattr(plugin.session, "_PAGE_READY_TIMEOUT_S", 0.02)

        session.start()

        assert session.active is False
        assert control_posts(posts) == ["/ensure-tab"], posts
        assert notes, "a clear error must be reported"
