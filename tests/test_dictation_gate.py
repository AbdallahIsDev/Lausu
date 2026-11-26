"""App-wide burst gate: five taps are one gesture, for every engine."""

from __future__ import annotations

from types import SimpleNamespace

from voice_typer.server.dictation_gate import DictationGate


class Clock:
    def __init__(self) -> None:
        self.now = 10.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def app_with(state: str, *, recording_started: float | None = None, plugin: bool = False):
    tray = SimpleNamespace(_state=SimpleNamespace(value=state), _recording_started_at=recording_started)
    app = SimpleNamespace(tray=tray)
    if plugin:
        app._internal_plugin_active_session = SimpleNamespace(
            _starting=state == "loading",
            _stopping=state == "transcribing",
            _active=state == "recording",
        )
    return app


def test_five_taps_at_150ms_give_one_start():
    clock = Clock()
    gate = DictationGate(clock)
    app = app_with("idle")
    actions = []
    for _ in range(5):
        actions.append(gate.decide(app))
        clock.advance(0.15)
    assert actions == ["start", "ignore-burst", "ignore-burst", "ignore-burst", "ignore-burst"]


def test_press_after_600ms_is_a_new_gesture():
    clock = Clock()
    gate = DictationGate(clock)
    app = app_with("idle")
    assert gate.decide(app) == "start"
    clock.advance(0.6)
    app = app_with("recording", recording_started=clock.now - 1.0)
    assert gate.decide(app) == "stop"


def test_press_during_starting_and_stopping_is_ignored():
    clock = Clock()
    gate = DictationGate(clock)
    assert gate.decide(app_with("idle")) == "start"
    clock.advance(0.6)
    assert gate.decide(app_with("loading")) == "ignore-transition"
    clock.advance(0.6)
    assert gate.decide(app_with("transcribing")) == "ignore-transition"


def test_stop_inside_min_recording_window_is_ignored():
    clock = Clock()
    gate = DictationGate(clock)
    app = app_with("recording", recording_started=clock.now)
    assert gate.decide(app) == "ignore-transition"
    clock.advance(0.6)
    assert gate.decide(app_with("recording", recording_started=clock.now - 0.6)) == "stop"


def test_gate_covers_plugin_session_state():
    clock = Clock()
    gate = DictationGate(clock)
    assert gate.decide(app_with("idle", plugin=True)) == "start"
    clock.advance(0.6)
    assert gate.decide(app_with("recording", plugin=True)) == "stop"
    gate.cancel()
    assert gate.generation == 2
