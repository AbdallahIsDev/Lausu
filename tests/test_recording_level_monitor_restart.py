"""Bubble restart of the level monitor happens only for a live consumer.

The idle bubble ignores levels and the recorder opens its own stream,
so an unconditional restart just pins the OS mic indicator for another
idle window for nobody. A consumer proves itself with polls (the mic
page heartbeats every 30s while visible).
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from voice_typer.server.recording_controller import RecordingController


def _make_controller() -> RecordingController:
    app = SimpleNamespace(config=SimpleNamespace(bubble_behavior="always_visible"))
    return RecordingController(app)


def _patch_monitor(monkeypatch, *, monitoring: bool, poll_age: float | None) -> MagicMock:
    import voice_typer.server.level_monitor as lm

    started = MagicMock()
    monkeypatch.setattr(lm, "is_monitoring", lambda: monitoring)
    monkeypatch.setattr(lm, "start_monitoring", started)
    monkeypatch.setattr(lm, "_LEVEL_IDLE_TIMEOUT_SEC", 60.0)
    if poll_age is None:
        monkeypatch.setattr(lm, "_last_get_level_poll_ts", 0.0)
    else:
        monkeypatch.setattr(lm, "_last_get_level_poll_ts", time.monotonic() - poll_age)
    return started


class TestRestartGatedOnPoller:
    def test_skips_when_behavior_not_always_visible(self, monkeypatch) -> None:
        app = SimpleNamespace(config=SimpleNamespace(bubble_behavior="show_on_record"))
        controller = RecordingController(app)
        started = _patch_monitor(monkeypatch, monitoring=False, poll_age=1.0)
        controller._maybe_restart_level_monitor_for_always_visible_bubble(app)
        started.assert_not_called()

    def test_skips_when_already_monitoring(self, monkeypatch) -> None:
        controller = _make_controller()
        started = _patch_monitor(monkeypatch, monitoring=True, poll_age=1.0)
        controller._maybe_restart_level_monitor_for_always_visible_bubble(controller._app)
        started.assert_not_called()

    def test_restarts_when_poll_is_recent(self, monkeypatch) -> None:
        controller = _make_controller()
        started = _patch_monitor(monkeypatch, monitoring=False, poll_age=5.0)
        controller._maybe_restart_level_monitor_for_always_visible_bubble(controller._app)
        started.assert_called_once()

    def test_skips_when_poll_is_stale(self, monkeypatch) -> None:
        controller = _make_controller()
        started = _patch_monitor(monkeypatch, monitoring=False, poll_age=120.0)
        controller._maybe_restart_level_monitor_for_always_visible_bubble(controller._app)
        started.assert_not_called()

    def test_skips_when_never_polled(self, monkeypatch) -> None:
        controller = _make_controller()
        started = _patch_monitor(monkeypatch, monitoring=False, poll_age=None)
        controller._maybe_restart_level_monitor_for_always_visible_bubble(controller._app)
        started.assert_not_called()
