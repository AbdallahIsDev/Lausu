"""Instant first-press feedback: bubble + sound fire before recorder.start()."""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_start_app(*, bubble_behavior="show_on_record"):
    from voice_typer.server.recording_lifecycle import RecordingLifecycle

    lifecycle = RecordingLifecycle()
    app = MagicMock(name="app")
    app.config.bubble_behavior = bubble_behavior
    app.recorder.recording = False
    app._cycle_id = "#1"
    controller = MagicMock(name="controller")
    controller._app = app
    controller._start_worker_join_timeout = 0.1
    return lifecycle, controller, app


def test_instant_feedback_fires_before_recorder_start():
    """Bubble + tray + start cue publish before blocking recorder.start()."""
    lifecycle, controller, app = _make_start_app()
    order: list[str] = []

    def _bubble_show():
        order.append("bubble")

    def _recording_started():
        order.append("sound")

    app._waveform_bubble.show.side_effect = _bubble_show
    app.tray.set_state.side_effect = lambda *a, **k: order.append("tray")
    lifecycle._publish_recording_started_event = _recording_started  # type: ignore[method-assign]
    lifecycle._gate_voice_biometric_consent = lambda app: True  # type: ignore[method-assign]
    lifecycle._wire_recorder_start_callbacks = lambda c, a: None  # type: ignore[method-assign]
    lifecycle._notify_mic_watcher_of_active_device = lambda app: None  # type: ignore[method-assign]
    lifecycle._claim_keyboard_ownership_for_recording = lambda app: None  # type: ignore[method-assign]
    lifecycle._rearm_esc_cancel_if_enabled = lambda app: None  # type: ignore[method-assign]
    lifecycle._spawn_dictation_start_worker = lambda c, a: None  # type: ignore[method-assign]

    def _blocking_start():
        order.append("recorder")

    app.recorder.start.side_effect = _blocking_start

    lifecycle._start_impl(controller)

    assert order.index("bubble") < order.index("recorder")
    assert order.index("sound") < order.index("recorder")
    assert order.index("tray") < order.index("recorder")
    assert order.count("sound") == 1


def test_failed_start_hides_optimistic_bubble():
    """recorder.start() failure rolls back the optimistic bubble."""
    lifecycle, controller, app = _make_start_app()
    lifecycle._gate_voice_biometric_consent = lambda app: True  # type: ignore[method-assign]
    lifecycle._wire_recorder_start_callbacks = lambda c, a: None  # type: ignore[method-assign]
    lifecycle._publish_recording_started_event = lambda: None  # type: ignore[method-assign]
    lifecycle._teardown_failed_recorder_start = lambda *a, **k: None  # type: ignore[method-assign]
    lifecycle._publish_start_failure_notification = lambda *a, **k: None  # type: ignore[method-assign]
    app.recorder.start.side_effect = RuntimeError("no device")

    lifecycle._start_impl(controller)

    app._waveform_bubble.hide.assert_called_once()


def test_always_visible_failure_returns_to_idle():
    """always_visible failure returns bubble to idle instead of hide."""
    lifecycle, controller, app = _make_start_app(bubble_behavior="always_visible")
    lifecycle._gate_voice_biometric_consent = lambda app: True  # type: ignore[method-assign]
    lifecycle._wire_recorder_start_callbacks = lambda c, a: None  # type: ignore[method-assign]
    lifecycle._publish_recording_started_event = lambda: None  # type: ignore[method-assign]
    lifecycle._teardown_failed_recorder_start = lambda *a, **k: None  # type: ignore[method-assign]
    lifecycle._publish_start_failure_notification = lambda *a, **k: None  # type: ignore[method-assign]
    app.recorder.start.side_effect = RuntimeError("no device")

    lifecycle._start_impl(controller)

    app._waveform_bubble.set_state.assert_called_with("idle")


def test_prewarm_resolves_recorder_and_controller():
    """Phase-7 prewarm touches recorder + recording so hotkey never waits."""
    from voice_typer.server.startup_sequence._phases_late import LatePhases

    app = MagicMock(name="app")
    phases = LatePhases()
    phases._app = app  # type: ignore[attr-defined]

    phases._prewarm_recorder_subsystem(app)

    assert app.recorder is not None
    assert app.recording is not None
