"""Pin the ESC trigger wire: cancel() during the post-transcription window must mark the cycle.

The window (after ``recorder.stop()`` has run, while the transcription worker
T is still executing ``DictationPipeline.run()`` synchronously) is exactly
``recording=False, T alive, busy=True``. A real ESC there must reach
``_cancel_impl``'s mark branch so ``cycle_guard.is_cycle_live`` fails for that
cycle and every zero-trace guard (store/paste) drops the worker's side effects.
No existing test drives this real stop -> real cancel sequence end to end.
"""

from __future__ import annotations

import threading
from unittest.mock import patch

from voice_typer.server.cycle_guard import is_cycle_live

from tests.test_recording_controller_lifecycle_fixes import _make_controller


def _arrange_post_stop_window(ctrl, app, cycle_id: str = "#7") -> None:
    """Link the mock's busyness to the real inverted ``_busy_event`` and make stop() flip recording."""
    app._cycle_id = cycle_id
    app.recording = ctrl
    app.recorder.recording = True

    def _stop():
        app.recorder.recording = False  # a real Recorder.stop() clears this
        return b"\x00" * 16000  # 1.0s of audio at 16 kHz

    app.recorder.stop.side_effect = _stop
    app._busyness.set_busy.side_effect = app._busy_event.clear
    app._busyness.set_idle.side_effect = app._busy_event.set


class _BlockingPipeline:
    """Stands in for ``DictationPipeline`` while it is mid-pipeline (polish/vocab/store)."""

    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        self._entered = entered
        self._release = release

    def __call__(self, app):
        return self

    def run(self, **kwargs) -> None:
        self._entered.set()
        self._release.wait(timeout=10)


class TestEscCancelTriggerWire:
    def test_esc_mid_pipeline_marks_cycle_cancelled(self):
        ctrl, app = _make_controller()
        _arrange_post_stop_window(ctrl, app)
        pipeline = _BlockingPipeline(threading.Event(), threading.Event())

        with (
            patch("voice_typer.server.dictation_pipeline.DictationPipeline", pipeline),
            patch.object(ctrl, "_force_recover_from_stuck_transcription") as recover,
        ):
            ctrl.stop()
            assert pipeline._entered.wait(timeout=5), "pipeline never reached run()"

            # The post-transcription window the wire depends on:
            # stream already stopped, worker T still alive, busy flag set.
            assert app.recorder.recording is False
            assert ctrl._transcription_thread is not None
            assert ctrl._transcription_thread.is_alive()
            assert not app._busy_event.is_set()
            recover.assert_not_called()

            ctrl.cancel()  # real ESC route: cancel -> _cancel_impl

            assert "#7" in ctrl._cancelled_cycle_ids
            assert recover.call_args.kwargs == {"force": True, "cloud_cancel_requested": False}
            assert is_cycle_live(app, "#7") is False

            pipeline._release.set()
            ctrl._transcription_thread.join(timeout=5)
            assert not ctrl._transcription_thread.is_alive()

    def test_esc_after_worker_exits_is_a_noop(self):
        ctrl, app = _make_controller()
        _arrange_post_stop_window(ctrl, app)

        with patch("voice_typer.server.dictation_pipeline.DictationPipeline"):
            ctrl.stop()

        thread = ctrl._transcription_thread
        assert thread is not None
        thread.join(timeout=5)
        assert not thread.is_alive()
        app._busyness.set_idle()  # what the real pipeline's finally teardown does

        with patch.object(ctrl, "_force_recover_from_stuck_transcription") as recover:
            ctrl.cancel()

        assert "#7" not in ctrl._cancelled_cycle_ids
        recover.assert_not_called()
        assert is_cycle_live(app, "#7") is True
