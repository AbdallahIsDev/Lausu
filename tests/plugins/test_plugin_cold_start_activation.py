"""Selecting a plugin at app start must not block on, or alarm about, a cold browser.

``activate()`` used to open the dictation profile and then wait 15 s for the
extension handshake, finishing with two ERROR lines when Chrome was still
booting — the normal cold-start shape. Nothing is waiting on that warm-up at
startup (the first hotkey press is), so it now opens the window and returns;
the wait belongs to the press.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tests.fixtures.sleep_seam import patch_module_time

_PLUGIN_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"


def _load_plugin() -> object:
    """Import the plugin module under a private name (no daemon, no side effects)."""
    name = "anthropic_stt_activation_under_test"
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
    monkeypatch.setattr(
        module,
        "threading",
        SimpleNamespace(Thread=lambda **_kwargs: SimpleNamespace(start=lambda: None)),
    )
    return module


class TestActivationWithAColdBrowser:
    def test_cold_browser_opens_the_profile_and_returns_immediately(self, plugin, monkeypatch, caplog):
        launches: list[tuple[str, str]] = []
        monkeypatch.setattr(
            plugin,
            "launch_profile",
            lambda profile, url: launches.append((profile, url)) or True,
        )
        monkeypatch.setattr(plugin, "_daemon_config", lambda: {"profileDir": "P", "claudeUrl": "U"})
        monkeypatch.setattr(plugin, "_daemon_status", lambda: {"browser": "connecting"})
        # A wait would call this; the cold path must not post /warm at all.
        warmed: list[str] = []
        monkeypatch.setattr(plugin, "_post", lambda path, timeout=None: warmed.append(path))
        waited: list[float] = []
        monkeypatch.setattr(
            plugin,
            "_ensure_browser",
            lambda timeout=None: waited.append(1.0) or False,
        )
        caplog.set_level(logging.INFO, logger="voice_typer.internal_plugin.anthropic_stt.plugin")

        assert plugin.activate(MagicMock()) is True

        assert launches == [("P", "U")]
        assert warmed == [], "a page that is not up yet cannot be warmed"
        assert waited == []

    def test_cold_start_logs_one_info_line_and_no_error(self, plugin, monkeypatch, caplog):
        monkeypatch.setattr(plugin, "launch_profile", lambda profile, url: True)
        monkeypatch.setattr(plugin, "_daemon_config", lambda: {"profileDir": "P", "claudeUrl": "U"})
        monkeypatch.setattr(plugin, "_daemon_status", lambda: {"browser": "connecting"})
        caplog.set_level(logging.DEBUG)

        plugin.activate(MagicMock())

        errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert errors == [], [r.getMessage() for r in errors]
        assert any("the first hotkey press waits for it" in r.getMessage() for r in caplog.records)

    def test_bridge_already_ready_warms_without_launching_a_window(self, plugin, monkeypatch):
        launches: list[tuple[str, str]] = []
        monkeypatch.setattr(
            plugin,
            "launch_profile",
            lambda profile, url: launches.append((profile, url)) or True,
        )
        monkeypatch.setattr(
            plugin,
            "_daemon_status",
            lambda: {"browser": "connected", "page": "ok"},
        )
        warmed: list[str] = []
        monkeypatch.setattr(plugin, "_post", lambda path, timeout=None: warmed.append(path))

        assert plugin.activate(MagicMock()) is True

        assert launches == [], "the window is already open and answering"
        assert warmed == ["/warm"]

    def test_a_failing_warm_is_still_reported(self, plugin, monkeypatch, caplog):
        """A ready bridge that refuses to warm is a real failure, not cold start."""
        pg = plugin
        monkeypatch.setattr(pg, "_daemon_status", lambda: {"browser": "connected", "page": "ok"})

        def _boom(path, timeout=None):
            raise pg.BridgeError("the Claude browser extension is not connected", "bridge")

        monkeypatch.setattr(pg, "_post", _boom)
        caplog.set_level(logging.ERROR)

        assert pg.activate(MagicMock()) is False
        assert "the Claude browser extension is not connected" in caplog.text


class TestBlankProfileLaunch:
    def test_a_relaunch_opens_the_active_platform_url(self, plugin, monkeypatch):
        launches: list[tuple[str, str]] = []
        monkeypatch.setattr(
            plugin,
            "launch_profile",
            lambda profile, url: launches.append((profile, url)) or True,
        )
        monkeypatch.setattr(
            plugin,
            "_daemon_config",
            lambda: {"profileDir": "P", "url": "https://claude.ai/new"},
        )
        monkeypatch.setattr(plugin, "_profile_missing", lambda: True)

        assert plugin._launch_profile_if_due() is True
        assert launches == [("P", "https://claude.ai/new")]


class TestActivationPreparesPlatform:
    def test_prepare_platform_reuses_the_tab_and_waits_for_a_ready_mic(self, plugin, monkeypatch):
        from tools.internal_plugins._common.bridge import session as shared_session
        from tools.internal_plugins._common.bridge.daemon_client import DaemonClient

        ready = {
            "browser": "connected",
            "page": "ok",
            "micCount": 1,
            "selectorsReady": True,
        }
        statuses = iter([{"browser": "disconnected"}, ready])
        posts: list[str] = []
        monkeypatch.setattr(plugin, "_daemon_status", lambda: next(statuses, ready))
        monkeypatch.setattr(plugin, "_post", lambda path, timeout=None: posts.append(path) or {})
        monkeypatch.setattr(plugin.time, "sleep", lambda *_: None)

        ok = shared_session.prepare_platform(
            status_fn=plugin._daemon_status,
            post_fn=plugin._post,
            connected_fn=plugin._browser_connected,
            ready_fn=DaemonClient.page_ready,
            clock=plugin.time,
        )

        assert ok is True
        assert "/ensure-tab" in posts, "activation must resolve the platform tab"

    def test_activation_starts_a_background_preparation(self, plugin, monkeypatch):

        started: list[str] = []

        class FakeThread:
            def __init__(self, *, target, name, daemon):
                started.append(name)

            def start(self):
                pass

        monkeypatch.setattr(plugin.threading, "Thread", FakeThread)
        monkeypatch.setattr(plugin, "_daemon_config", lambda: {"profileDir": "P", "claudeUrl": "U"})
        monkeypatch.setattr(plugin, "_daemon_status", lambda: {"browser": "connected", "page": "ok"})
        monkeypatch.setattr(plugin, "_post", lambda path, timeout=None: {})

        assert plugin.activate(MagicMock()) is True
        assert "plugin-activate-platform" in started


class TestLaunchSingleFlight:
    def test_a_running_profile_is_never_relaunched(self, plugin, monkeypatch):
        launches: list[tuple[str, str]] = []
        monkeypatch.setattr(
            plugin,
            "launch_profile",
            lambda profile, url: launches.append((profile, url)) or True,
        )
        monkeypatch.setattr(plugin, "_profile_running", lambda: True)
        monkeypatch.setattr(plugin, "_last_launch_ts", 0.0)

        assert plugin._launch_profile_if_due() is False
        assert launches == [], "a running profile must never get another tab"

    def test_concurrent_launch_requests_spawn_one_process(self, plugin, monkeypatch):
        import threading

        launches: list[tuple[str, str]] = []
        monkeypatch.setattr(
            plugin,
            "launch_profile",
            lambda profile, url: launches.append((profile, url)) or True,
        )
        monkeypatch.setattr(plugin, "_profile_running", lambda: False)
        monkeypatch.setattr(plugin, "_profile_missing", lambda: False)
        monkeypatch.setattr(plugin, "_daemon_config", lambda: {"profileDir": "P", "claudeUrl": "U"})
        monkeypatch.setattr(plugin.time, "monotonic", lambda: 100.0)
        monkeypatch.setattr(plugin, "_last_launch_ts", 0.0)

        threads = [threading.Thread(target=plugin._launch_profile_if_due) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert launches == [("P", "U")]


class TestBrowserWaitBudget:
    def test_a_launch_this_call_made_gets_the_cold_boot_budget(self, plugin, monkeypatch):
        monkeypatch.setattr(plugin, "launch_profile", lambda profile, url: True)
        # Due now: the cooldown is measured from the last launch.
        monkeypatch.setattr(plugin, "_last_launch_ts", -1000.0)
        monkeypatch.setattr(plugin, "_daemon_config", lambda: {"profileDir": "P", "claudeUrl": "U"})
        monkeypatch.setattr(plugin, "_daemon_status", lambda: {"browser": "connecting"})
        budgets: list[float] = []
        clock = {"now": 0.0}

        def _sleep(seconds):
            clock["now"] += seconds
            budgets.append(seconds)

        # Rebind the plugin module's own ``time`` (never the stdlib module, whose
        # patch is process-global and would catch another thread's sleeps).
        fake_time = patch_module_time(monkeypatch, plugin, sleep=_sleep)
        fake_time.monotonic = lambda: clock["now"]

        assert plugin._ensure_browser() is False
        assert sum(budgets) >= plugin._COLD_BROWSER_START_TIMEOUT_S - 1.0

    def test_an_already_open_window_keeps_the_short_budget(self, plugin, monkeypatch):
        monkeypatch.setattr(plugin, "_last_launch_ts", plugin.time.monotonic())
        monkeypatch.setattr(plugin, "_daemon_status", lambda: {"browser": "connecting"})
        clock = {"now": 0.0}
        slept: list[float] = []

        def _sleep(seconds):
            clock["now"] += seconds
            slept.append(seconds)

        fake_time = patch_module_time(monkeypatch, plugin, sleep=_sleep)
        fake_time.monotonic = lambda: clock["now"]

        assert plugin._ensure_browser() is False
        assert sum(slept) <= plugin._BROWSER_START_TIMEOUT_S + 1.0

    def test_the_profile_is_not_relaunched_inside_the_cooldown(self, plugin, monkeypatch):
        """C-START-3: a dead extension must not spawn a window per press."""
        launches: list[tuple[str, str]] = []
        monkeypatch.setattr(
            plugin,
            "launch_profile",
            lambda profile, url: launches.append((profile, url)) or True,
        )
        monkeypatch.setattr(plugin, "_daemon_config", lambda: {"profileDir": "P", "claudeUrl": "U"})
        monkeypatch.setattr(plugin.time, "monotonic", lambda: 100.0)
        monkeypatch.setattr(plugin, "_last_launch_ts", 90.0)
        monkeypatch.setattr(plugin, "_profile_missing", lambda: False)

        assert plugin._launch_profile_if_due() is False
        assert launches == []
