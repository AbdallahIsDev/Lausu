"""Closing the dictation profile mid-cycle must recover cleanly and immediately.

Two regressions from the live log: the platform watchdog posted /stop to a
browser that was already gone (409 not-recording + traceback), and the 30 s
launch cooldown refused to reopen a profile the user had explicitly closed.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PLUGIN_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"


def _load_plugin() -> object:
    name = "anthropic_stt_relaunch_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _PLUGIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plugin(monkeypatch):
    module = _load_plugin()
    monkeypatch.setattr(module, "_last_launch_ts", 0.0)
    monkeypatch.setattr(module, "_PLATFORM_WATCH_GRACE_S", 0.0)
    monkeypatch.setattr(module, "_PLATFORM_WATCH_POLL_S", 0.0)
    return module


class TestBrowserClosedMidCapture:
    def test_watchdog_does_not_post_stop_to_a_closed_browser(self, plugin, monkeypatch):
        session = plugin.PluginSession(MagicMock())
        monkeypatch.setattr(session, "_active", True)
        monkeypatch.setattr(session, "_t0", time.monotonic() - 3.0)
        monkeypatch.setattr(session, "_status", lambda: {"browser": "disconnected", "state": "no-page"})
        posts: list[str] = []
        notes: list[str] = []
        monkeypatch.setattr(session, "_post", lambda path, timeout=None: posts.append(path))
        monkeypatch.setattr(session, "_notify", notes.append)
        monkeypatch.setattr(session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(session, "_publish_state", lambda state: None)
        restored: list[bool] = []
        monkeypatch.setattr(session, "_restore_volume", lambda: restored.append(True))

        session._watch_platform()

        assert posts == [], "a closed browser cannot answer /stop"
        assert restored, "volume ducked at start must be restored on abort"
        assert any("closed" in note.lower() for note in notes)
        assert session.active is False


class TestStartAfterBrowserDisconnect:
    def test_start_recovers_when_the_browser_drops_during_startup(self, plugin, monkeypatch):
        session = plugin.PluginSession(MagicMock())
        monkeypatch.setattr(session, "_ensure_daemon", lambda: True)
        monkeypatch.setattr(session, "_status", lambda: {"browser": "connected", "page": "ok"})
        browsers = []
        monkeypatch.setattr(session, "_ensure_browser", lambda timeout=None: browsers.append(1) or True)

        posts: list[str] = []

        def _post(path, timeout=None):
            posts.append(path)
            if path == "/start" and posts.count("/start") == 1:
                raise plugin.BridgeError("the browser extension disconnected", "browser-not-open")
            return {}

        monkeypatch.setattr(session, "_post", _post)

        class FakeMeter:
            def __init__(self, app):
                pass

            def start(self):
                pass

            def stop(self):
                pass

        monkeypatch.setattr(plugin, "LevelMeter", FakeMeter)
        monkeypatch.setattr(session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(session, "_duck", lambda: None)
        monkeypatch.setattr(session, "_watch_platform", lambda: None)
        monkeypatch.setattr(plugin.time, "sleep", lambda *_: None)

        session.start()

        assert session.active is True
        assert len(browsers) == 2, "the profile must be reopened before retrying"
        assert posts.count("/start") == 2
        assert posts == ["/ensure-tab", "/start", "/ensure-tab", "/start"]


class TestExpectedStartFailures:
    def test_a_signed_out_tab_is_a_clean_actionable_line(self, plugin, monkeypatch, caplog):
        import logging

        session = plugin.PluginSession(MagicMock())
        monkeypatch.setattr(session, "_ensure_daemon", lambda: True)
        monkeypatch.setattr(session, "_ensure_browser", lambda timeout=None: True)
        monkeypatch.setattr(session, "_status", lambda: {"browser": "connected", "page": "signed_out"})
        monkeypatch.setattr(session, "_watch_platform", lambda: None)

        def _post(path, timeout=None):
            if path == "/start":
                raise plugin.BridgeError("the tab is signed out", "signed-out")
            return {}

        monkeypatch.setattr(session, "_post", _post)
        notes: list[str] = []
        monkeypatch.setattr(session, "_notify", notes.append)
        caplog.set_level(logging.DEBUG)

        session.start()

        assert session.active is False
        assert "Traceback" not in caplog.text
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("signed out" in note.lower() for note in notes)


class TestRelaunchAfterClose:
    def test_a_closed_profile_relaunches_inside_the_cooldown(self, plugin, monkeypatch):
        monkeypatch.setattr(plugin, "_last_launch_ts", time.monotonic())
        monkeypatch.setattr(plugin, "_daemon_config", lambda: {"profileDir": "P", "claudeUrl": "U"})
        monkeypatch.setattr(plugin, "_profile_missing", lambda: True)
        launches: list[tuple[str, str]] = []
        monkeypatch.setattr(
            plugin,
            "launch_profile",
            lambda profile, url: launches.append((profile, url)) or True,
        )

        assert plugin._launch_profile_if_due() is True
        assert launches == [("P", "about:blank")]

    def test_an_open_profile_still_respects_the_cooldown(self, plugin, monkeypatch):
        monkeypatch.setattr(plugin, "_last_launch_ts", time.monotonic())
        monkeypatch.setattr(plugin, "_daemon_config", lambda: {"profileDir": "P", "claudeUrl": "U"})
        monkeypatch.setattr(plugin, "_profile_missing", lambda: False)
        launches: list[tuple[str, str]] = []
        monkeypatch.setattr(
            plugin,
            "launch_profile",
            lambda profile, url: launches.append((profile, url)) or True,
        )

        assert plugin._launch_profile_if_due() is False
        assert launches == []
