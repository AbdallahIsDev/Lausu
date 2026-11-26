"""A connected browser owns its target tabs; switching plugins must never spawn a new one.

Regression: both plugins share one Chrome profile. A missing target tab used to
be treated as "browser not ready", which launched Chrome with the platform URL
and opened a duplicate tab on every switch. The extension now resolves tabs;
Python only launches Chrome when the browser transport itself is gone.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_PLUGIN_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"


def _ready(**changes):
    status = {
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
    status.update(changes)
    return status


def _load_plugin() -> object:
    name = "anthropic_stt_tab_resolution_under_test"
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
    monkeypatch.setattr(module, "plugins_enabled", lambda: True)
    monkeypatch.setattr(module, "attach", lambda app: object())
    monkeypatch.setattr(module, "ensure_daemon", lambda: True)
    monkeypatch.setattr(module, "_last_launch_ts", 0.0)
    monkeypatch.setattr(module, "_profile_running", lambda: False)
    captured: dict[str, object] = {}

    def _fake_thread(**kwargs):
        captured["target"] = kwargs["target"]
        return SimpleNamespace(start=lambda: None)

    monkeypatch.setattr(module, "threading", SimpleNamespace(Thread=_fake_thread))

    def _run_target():
        with monkeypatch.context() as patch:
            patch.setattr(module.session, "prepare_platform", lambda **_kwargs: None)
            captured["target"]()

    monkeypatch.setattr(module, "_activate_target", _run_target, raising=False)
    return module


class TestConnectedBrowserKeepsItsTabs:
    def test_a_missing_target_tab_does_not_launch_chrome(self, plugin, monkeypatch):
        launches: list[tuple[str, str]] = []
        monkeypatch.setattr(
            plugin,
            "launch_profile",
            lambda profile, url: launches.append((profile, url)) or True,
        )
        monkeypatch.setattr(
            plugin,
            "_daemon_status",
            lambda: {
                "browser": "connected",
                "page": "unknown",
                "hasTab": False,
            },
        )

        assert plugin._ensure_browser() is True
        assert launches == [], "a connected browser resolves its own target tab"

    def test_activation_warms_instead_of_launching_when_the_tab_is_missing(self, plugin, monkeypatch):
        launches: list[str] = []
        warmed: list[str] = []
        monkeypatch.setattr(plugin, "launch_profile", lambda profile, url: launches.append(url) or True)
        monkeypatch.setattr(
            plugin,
            "_daemon_status",
            lambda: {"browser": "connected", "page": "unknown", "hasTab": False},
        )
        monkeypatch.setattr(plugin, "_post", lambda path, timeout=None: warmed.append(path) or {})

        assert plugin.activate(MagicMock()) is True
        plugin._activate_target()
        assert launches == []
        assert warmed == ["/warm"]

    def test_a_disconnected_browser_still_launches_the_profile(self, plugin, monkeypatch):
        launches: list[str] = []
        monkeypatch.setattr(plugin, "launch_profile", lambda profile, url: launches.append(url) or True)
        polls = iter([{"browser": "disconnected"}, _ready()])
        monkeypatch.setattr(plugin, "_daemon_status", lambda: next(polls))

        assert plugin._ensure_browser() is True
        assert len(launches) == 1, "profile startup behaviour is preserved"


class TestStartResolvesTheTargetTab:
    def test_target_tab_is_resolved_before_start(self, plugin, monkeypatch):
        posts: list[str] = []

        def _post(path, timeout=None):
            posts.append(path)
            return {}

        monkeypatch.setattr(plugin, "_post", _post)
        monkeypatch.setattr(
            plugin,
            "_daemon_status",
            lambda: _ready(),
        )
        monkeypatch.setattr(plugin, "ensure_daemon", lambda: True)

        class FakeMeter:
            def __init__(self, app):
                pass

            def start(self):
                pass

        monkeypatch.setattr(plugin, "LevelMeter", FakeMeter)

        session = plugin.PluginSession(MagicMock())
        monkeypatch.setattr(session, "_ensure_browser", lambda timeout=None: True)
        monkeypatch.setattr(session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(session, "_duck", lambda: None)
        monkeypatch.setattr(session, "_meter", None)
        monkeypatch.setattr(session, "_publish_state", lambda state: None)

        session.start()

        assert posts == ["/ensure-tab", "/start"], posts

    def test_one_ensure_tab_round_trip_on_the_hotkey_path(self, plugin, monkeypatch, caplog):
        """The extension resolves the tab once before the mic gate and /start."""

        posts: list[str] = []
        monkeypatch.setattr(plugin, "_post", lambda path, timeout=None: posts.append(path) or {})
        monkeypatch.setattr(
            plugin,
            "_daemon_status",
            lambda: _ready(),
        )
        monkeypatch.setattr(plugin, "ensure_daemon", lambda: True)

        class FakeMeter:
            def __init__(self, app):
                pass

            def start(self):
                pass

        monkeypatch.setattr(plugin, "LevelMeter", FakeMeter)
        session = plugin.PluginSession(MagicMock())
        monkeypatch.setattr(session, "_ensure_browser", lambda timeout=None: True)
        monkeypatch.setattr(session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(session, "_duck", lambda: None)
        monkeypatch.setattr(session, "_meter", None)
        monkeypatch.setattr(session, "_publish_state", lambda state: None)
        caplog.set_level(logging.DEBUG)

        session.start()

        assert posts == ["/ensure-tab", "/start"], posts
        assert "Traceback" not in caplog.text
