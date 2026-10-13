"""``MicrophoneDeviceWatcher`` and the ``recorder.on_device_lost``"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from voice_typer.server.recording_controller import RecordingController


def _make_app_with_mock_recorder(mic_id: str | None = "5") -> MagicMock:
    """Build a mock app whose ``recorder`` has a mock ``_mic_watcher``."""
    app = MagicMock()
    app.recorder.recording = False
    app.recorder._devices._mic_watcher = MagicMock()
    # ``recorder.on_device_lost`` is normally a plain attribute, pre-fix
    for attr in ("on_device_lost",):
        if hasattr(app.recorder, attr):
            delattr(app.recorder, attr)
    app.config.microphone = mic_id
    app.config.voice_biometric_consent = True
    app._cycle_id = "#1"
    app._busy_event.is_set.return_value = True  # not busy → start proceeds
    app.models.active_transcriber.return_value = MagicMock(is_loaded=True)
    app.models.apply_pending_model_change.return_value = None
    app.models.ensure_active_engine_loaded.return_value = None
    return app


def _make_full_controller(app: MagicMock) -> RecordingController:
    """Construct a RecordingController the normal way (via __init__)."""
    return RecordingController(app)


def _assert_bound_methods_equal(actual, expected, msg: str = "") -> None:
    """Assert two bound methods refer to the same (instance, function)."""
    assert actual is not None, msg or "expected a bound method, got None"
    assert callable(actual), msg or "expected a callable"
    assert actual.__self__ is expected.__self__, (
        msg or f"bound method __self__ mismatch: {actual.__self__!r} vs {expected.__self__!r}"
    )
    assert actual.__func__ is expected.__func__, (
        msg or f"bound method __func__ mismatch: {actual.__func__!r} vs {expected.__func__!r}"
    )


class TestInitWiring:
    """DJ-65: ``__init__`` wires ``on_device_lost`` + the watcher hooks."""

    def test_on_device_lost_is_bound_on_init(self):
        """``recorder.on_device_lost`` MUST be set to our callback."""
        app = _make_app_with_mock_recorder()
        ctrl = _make_full_controller(app)

        actual = getattr(app.recorder, "on_device_lost", None)
        _assert_bound_methods_equal(
            actual,
            ctrl.on_device_lost,
            "DJ-65: __init__ must bind recorder.on_device_lost to "
            "self.on_device_lost so the recorder's terminal-case "
            "fallback (recorder.py:1142) invokes our callback instead "
            "of falling back to on_silence_auto_stop.",
        )

    def test_set_on_active_mic_lost_is_wired_on_init(self):
        """``watcher.set_on_active_mic_lost`` MUST be called with our"""
        app = _make_app_with_mock_recorder()
        ctrl = _make_full_controller(app)

        app.recorder._devices._mic_watcher.set_on_active_mic_lost.assert_called_once()
        actual_arg = app.recorder._devices._mic_watcher.set_on_active_mic_lost.call_args.args[0]
        _assert_bound_methods_equal(
            actual_arg,
            ctrl.on_active_mic_lost,
            "DJ-65: set_on_active_mic_lost must be called with self.on_active_mic_lost",
        )

    def test_set_device_id_provider_is_wired_on_init(self):
        """``watcher.set_device_id_provider`` MUST be called with our"""
        app = _make_app_with_mock_recorder()
        ctrl = _make_full_controller(app)

        app.recorder._devices._mic_watcher.set_device_id_provider.assert_called_once()
        actual_arg = app.recorder._devices._mic_watcher.set_device_id_provider.call_args.args[0]
        _assert_bound_methods_equal(
            actual_arg,
            ctrl._list_active_mic_ids,
            "DJ-65: set_device_id_provider must be called with self._list_active_mic_ids",
        )

    def test_init_wiring_is_no_op_when_no_mic_watcher(self):
        """DJ-65: the wiring is defensive, if the recorder has no"""
        app = _make_app_with_mock_recorder()
        app.recorder._devices._mic_watcher = None
        # Should not raise.
        ctrl = RecordingController(app)

        actual = getattr(app.recorder, "on_device_lost", None)
        _assert_bound_methods_equal(
            actual,
            ctrl.on_device_lost,
            "DJ-65: on_device_lost must be bound even when _mic_watcher is None",
        )


class TestStartWiring:
    """DJ-65: ``_start_impl`` calls ``set_active_mic_id(mic_id)`` after"""

    def test_start_calls_set_active_mic_id_with_opened_device(self):
        """After start, the watcher must have the actually-opened device"""
        app = _make_app_with_mock_recorder(mic_id="7")
        app.recorder._effective_device = 7
        ctrl = _make_full_controller(app)
        app.recorder._devices._mic_watcher.reset_mock()

        ctrl._lifecycle._start_impl(ctrl)

        app.recorder._devices._mic_watcher.set_active_mic_id.assert_called_once_with(7)

    def test_start_calls_set_active_mic_id_after_recorder_start(self):
        """``set_active_mic_id`` must be called AFTER ``recorder.start()``"""
        app = _make_app_with_mock_recorder(mic_id="5")
        ctrl = _make_full_controller(app)
        app.recorder._devices._mic_watcher.reset_mock()

        # Track call order between recorder.start() and set_active_mic_id.
        call_order: list[str] = []

        def _record_start():
            call_order.append("recorder.start")

        app.recorder.start.side_effect = _record_start

        original_set_active = app.recorder._devices._mic_watcher.set_active_mic_id

        def _record_set_active(mic_id):
            call_order.append("set_active_mic_id")
            original_set_active(mic_id)

        app.recorder._devices._mic_watcher.set_active_mic_id.side_effect = _record_set_active

        ctrl._lifecycle._start_impl(ctrl)

        assert call_order[0] == "recorder.start", (
            "DJ-65: recorder.start() must be called BEFORE "
            "set_active_mic_id so the mic id reflects the actually-"
            "opened device."
        )
        assert "set_active_mic_id" in call_order


class TestStopUnwiring:
    """DJ-65: ``_stop_impl`` calls ``set_active_mic_id(None)`` to clear"""

    def test_stop_calls_set_active_mic_id_none(self):
        """watcher doesn't fire ``_cancel_on_mic_lost`` for a recording"""
        app = _make_app_with_mock_recorder()
        ctrl = _make_full_controller(app)
        # Make the recorder appear to be recording so _stop_impl
        app.recorder.recording = True
        # Provide 1.0s of audio so the ``duration < 0.5`` short-circuit
        app.recorder.stop.return_value = np.ones(16000, dtype=np.float32) * 0.01
        app.recorder.last_rms = 0.05
        app.config.sample_rate = 16000
        app.recorder._devices._mic_watcher.reset_mock()

        # Patch DictationPipeline to a stub so the transcription thread
        import voice_typer.server.dictation_pipeline as dp_module

        original_pipeline = dp_module.DictationPipeline

        class FakePipeline:
            def __init__(self, app):
                pass

            def run(self, **kwargs):
                pass

        dp_module.DictationPipeline = FakePipeline
        try:
            ctrl._lifecycle._stop_impl(ctrl)
        finally:
            dp_module.DictationPipeline = original_pipeline

        set_active_calls = app.recorder._devices._mic_watcher.set_active_mic_id.call_args_list
        assert any(call.args == (None,) for call in set_active_calls), (
            f"DJ-65: _stop_impl must call set_active_mic_id(None) to "
            f"clear the active-mic id; got calls: {set_active_calls}"
        )

    def test_stop_calls_set_active_mic_id_none_after_recorder_stop(self):
        """``set_active_mic_id(None)`` must be called AFTER"""
        app = _make_app_with_mock_recorder()
        ctrl = _make_full_controller(app)
        app.recorder.recording = True
        app.recorder.stop.return_value = np.ones(16000, dtype=np.float32) * 0.01
        app.recorder.last_rms = 0.05
        app.config.sample_rate = 16000
        app.recorder._devices._mic_watcher.reset_mock()

        call_order: list[str] = []

        def _record_stop():
            call_order.append("recorder.stop")
            return np.ones(16000, dtype=np.float32) * 0.01

        app.recorder.stop.side_effect = _record_stop

        original_set_active = app.recorder._devices._mic_watcher.set_active_mic_id

        def _record_set_active(mic_id):
            call_order.append(f"set_active_mic_id({mic_id!r})")
            original_set_active(mic_id)

        app.recorder._devices._mic_watcher.set_active_mic_id.side_effect = _record_set_active

        import voice_typer.server.dictation_pipeline as dp_module

        original_pipeline = dp_module.DictationPipeline

        class FakePipeline:
            def __init__(self, app):
                pass

            def run(self, **kwargs):
                pass

        dp_module.DictationPipeline = FakePipeline
        try:
            ctrl._lifecycle._stop_impl(ctrl)
        finally:
            dp_module.DictationPipeline = original_pipeline

        # The stop runs on a daemon worker; join it so the order below
        # is deterministic instead of racing the test thread.
        ctrl._transcription_thread.join(timeout=30)
        assert not ctrl._transcription_thread.is_alive(), (
            "DJ-65: stop worker did not finish; order assertions would race"
        )
        stop_positions = [i for i, c in enumerate(call_order) if c == "recorder.stop"]
        none_positions = [i for i, c in enumerate(call_order) if c == "set_active_mic_id(None)"]
        assert stop_positions, "DJ-65: recorder.stop was never called"
        assert none_positions, "DJ-65: set_active_mic_id was never called"
        assert min(none_positions) > min(stop_positions), (
            f"DJ-65: set_active_mic_id(None) must be called AFTER "
            f"recorder.stop() (the id clears once audio is captured); "
            f"call order: {call_order}"
        )


class TestCancelUnwiring:
    """DJ-65: ``_cancel_impl`` also calls ``set_active_mic_id(None)``"""

    def test_cancel_calls_set_active_mic_id_none(self):
        app = _make_app_with_mock_recorder()
        ctrl = _make_full_controller(app)
        app.recorder.recording = True
        app.recorder._devices._mic_watcher.reset_mock()

        ctrl._lifecycle._cancel_impl(ctrl)

        app.recorder._devices._mic_watcher.set_active_mic_id.assert_called_once_with(None)


class TestCallbackBehavior:
    """DJ-65: the wired callbacks behave correctly."""

    def test_cancel_on_mic_lost_notifies_tray_and_defers_stop(self):
        """``on_active_mic_lost`` (the watcher-side callback) must:"""
        app = _make_app_with_mock_recorder()
        ctrl = _make_full_controller(app)

        scheduled: list[tuple] = []

        def _capture_schedule(delay, func, *args, **kwargs):
            scheduled.append((delay, func))

        app._schedule_timer.side_effect = _capture_schedule
        app.tray.notify_safety = MagicMock()

        ctrl.on_active_mic_lost()

        # Tray notification was shown.
        assert app.tray.notify_safety.called, (
            "DJ-65: on_active_mic_lost must show a tray notification "
            "so the user sees 'microphone unplugged' (not 'silence "
            "detected')."
        )
        notify_args = app.tray.notify_safety.call_args
        notification_text = notify_args.args[1] if len(notify_args.args) > 1 else ""
        assert "microphone" in notification_text.lower(), (
            f"DJ-65: notification must mention 'microphone'; got: {notification_text!r}"
        )
        # Stop was deferred via _schedule_timer(0, ...).
        assert scheduled, (
            "DJ-65: on_active_mic_lost must defer the stop via "
            "_schedule_timer(0, ...), must NOT call stop() directly."
        )
        assert scheduled[0][0] == 0, f"DJ-65: defer delay must be 0; got {scheduled[0][0]}"
        assert scheduled[0][1] == app._stop_dictation

    def test_on_device_lost_notifies_tray_and_defers_stop(self):
        """``on_device_lost`` (the terminal-case callback) must:"""
        app = _make_app_with_mock_recorder()
        ctrl = _make_full_controller(app)

        scheduled: list[tuple] = []

        def _capture_schedule(delay, func, *args, **kwargs):
            scheduled.append((delay, func))

        app._schedule_timer.side_effect = _capture_schedule
        app.tray.notify_safety = MagicMock()

        ctrl.on_device_lost()

        assert app.tray.notify_safety.called
        notify_args = app.tray.notify_safety.call_args
        notification_text = notify_args.args[1] if len(notify_args.args) > 1 else ""
        assert "microphone" in notification_text.lower(), (
            f"DJ-65: notification must mention 'microphone'; got: {notification_text!r}"
        )
        assert scheduled, (
            "DJ-65: on_device_lost must defer the stop via _schedule_timer(0, ...), must NOT call stop() directly."
        )
        assert scheduled[0][0] == 0
        assert scheduled[0][1] == app._stop_dictation

    def test_device_id_provider_returns_mic_ids(self):
        """the app's ``list_microphones`` device indexes."""
        app = _make_app_with_mock_recorder()
        app.list_microphones = MagicMock(
            return_value=[
                {"index": 0, "id": "0", "name": "Mic A"},
                {"index": 1, "id": "1", "name": "Mic B"},
            ]
        )
        ctrl = _make_full_controller(app)

        ids = ctrl._list_active_mic_ids()
        assert ids == [0, 1], f"DJ-65: device_id_provider must return mic indexes; got {ids}"

    @pytest.mark.skip(
        reason="_list_active_mic_ids reads controller._app.list_microphones() "
        "only; the old cached-``_microphones`` fallback no longer exists, "
        "so this case has no new-API equivalent."
    )
    def test_device_id_provider_falls_back_to_cached_microphones(self):
        """provider falls back to the cached ``_microphones`` list."""
        app = _make_app_with_mock_recorder()
        # No ``list_microphones`` attribute, the mock won't have one
        if hasattr(app, "list_microphones"):
            delattr(app, "list_microphones")
        app._microphones = [
            {"id": "5", "name": "Cached Mic"},
            {"id": "6", "name": "Other Mic"},
        ]
        ctrl = _make_full_controller(app)

        ids = ctrl._list_active_mic_ids()
        assert ids == ["5", "6"], f"DJ-65: device_id_provider must fall back to the cached _microphones list; got {ids}"

    def test_device_id_provider_returns_empty_on_failure(self):
        """On any failure (no lister, no cached list), the provider"""
        app = _make_app_with_mock_recorder()
        if hasattr(app, "list_microphones"):
            delattr(app, "list_microphones")
        if hasattr(app, "_microphones"):
            delattr(app, "_microphones")
        ctrl = _make_full_controller(app)

        ids = ctrl._list_active_mic_ids()
        assert ids == [], f"DJ-65: device_id_provider must return [] on failure; got {ids}"
