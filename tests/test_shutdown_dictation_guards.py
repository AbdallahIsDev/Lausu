"""Shutdown vs an in-flight dictation: discard-on-shutdown + cycle-start gate.

docs/voice_typer_recording_edge_cases.md §5: a graceful quit let a worker
the 3s transcription join did not finish still store/paste after teardown
started. ``do_cleanup`` (and the Windows logoff fast path) now mark the
app's live cycle cancelled BEFORE any phase, so the already-built
``is_cycle_live`` guards drop the late result — no new guard machinery.
Recording-quit stays safe by design: no partial audio file is ever
written (regression guard).

All recorders/models/pipelines are mocked; no real audio, no real mic.
"""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from voice_typer.server.dictation_stages import (
    CancellationGuard,
    PasteStage,
    PipelineContext,
    StoreResultStage,
    _PipelineAbortCancelled,
)
from voice_typer.server.recording_lifecycle import RecordingLifecycle
from voice_typer.server.shutdown.cleanup import do_cleanup, do_fast_cleanup
from voice_typer.server.shutdown.teardowns.recorder import teardown_recorder

from tests.fixtures.shutdown_helpers import (
    make_cancelled_registry_recording,
    make_quiet_cleanup_controller,
)


@pytest.fixture(autouse=True)
def _clear_pending_restores():
    from voice_typer.server import clipboard as clip_mod

    with clip_mod._pending_restores_lock:
        clip_mod._pending_restores.clear()
    yield
    with clip_mod._pending_restores_lock:
        clip_mod._pending_restores.clear()


def _make_app(cycle_id="#7") -> SimpleNamespace:
    return SimpleNamespace(
        _cleanup_done=False,
        _cycle_id=cycle_id,
        recording=make_cancelled_registry_recording(),
        _ipc_server=None,
    )


def _make_pipeline_stub(app) -> SimpleNamespace:
    pipeline = SimpleNamespace()
    pipeline._app = app
    pipeline._cycle_id = app._cycle_id
    pipeline._store_result = MagicMock()
    pipeline._copy_and_paste = MagicMock()
    pipeline._hide_or_idle_bubble = MagicMock()
    return pipeline


def _ctx(app, pipeline) -> PipelineContext:
    return PipelineContext(cycle_id=app._cycle_id, audio=None, app=app, pipeline=pipeline)


class TestDiscardOnShutdownMark:
    """``do_cleanup`` marks the live cycle BEFORE any teardown phase."""

    def test_do_cleanup_marks_the_live_cycle_before_any_phase(self):
        order: list[str] = []
        app = _make_app("#7")
        real_mark = app.recording._mark_cycle_cancelled

        def _spy_mark(cycle_id):
            order.append("mark")
            return real_mark(cycle_id)

        app.recording._mark_cycle_cancelled = _spy_mark
        controller = make_quiet_cleanup_controller(app, order=order)

        do_cleanup(controller)

        assert "#7" in app.recording._cancelled_cycle_ids
        assert order[:2] == ["mark", "drain"], f"mark must land before the teardown phases; got {order}"

    def test_do_cleanup_is_noop_on_stub_apps(self):
        """Unit stubs (MagicMock ``_cycle_id``) must not trip the mark."""
        controller = make_quiet_cleanup_controller(SimpleNamespace(_cleanup_done=False, _cycle_id=MagicMock()))
        do_cleanup(controller)  # must not raise

    def test_fast_cleanup_marks_the_live_cycle(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.shutdown_controller.os._exit", lambda code=0: None)
        app = _make_app("#9")
        app._crash_recovery = None
        app.history_db = None
        app.recorder = None
        app._mutex_handle = None
        app._restore_volume = MagicMock()
        app._duck_crash_recovery = MagicMock()
        controller = make_quiet_cleanup_controller(app)

        do_fast_cleanup(controller)

        assert "#9" in app.recording._cancelled_cycle_ids


class TestOrphanWorkerRefusedAfterShutdown:
    """The late result of a worker the 3s join did not finish refuses."""

    def test_late_store_and_paste_are_both_refused(self):
        app = _make_app("#7")
        app.config = SimpleNamespace(crash_recovery_enabled=False)
        app.history_db = MagicMock()
        app._crash_recovery = MagicMock()
        controller = make_quiet_cleanup_controller(app)
        do_cleanup(controller)

        pipeline = _make_pipeline_stub(app)
        ctx = _ctx(app, pipeline)

        with pytest.raises(_PipelineAbortCancelled):
            CancellationGuard(StoreResultStage(), preserve_on_cancel=False).run("late text", ctx)
        with pytest.raises(_PipelineAbortCancelled):
            CancellationGuard(PasteStage()).run("late text", ctx)

        pipeline._store_result.assert_not_called()
        pipeline._copy_and_paste.assert_not_called()

    def test_late_store_direct_call_writes_nothing(self):
        app = _make_app("#7")
        app.config = SimpleNamespace(history_enabled=True, crash_recovery_enabled=True)
        app.history_db = MagicMock()
        app._crash_recovery = MagicMock()
        controller = make_quiet_cleanup_controller(app)
        do_cleanup(controller)

        pipeline = _make_pipeline_stub(app)
        # Call the real step: the effect-time re-check (C-CONC-2) refuses.
        from voice_typer.server.dictation_pipeline import DictationPipeline

        DictationPipeline._store_result(pipeline, "late text")

        app.history_db.add_transcription.assert_not_called()
        app._crash_recovery.add.assert_not_called()


class TestCycleStartGateDuringShutdown:
    """A press mid-shutdown must not start a new cycle during teardown."""

    @staticmethod
    def _controller(*, shutting_down: bool, event=None):
        if event is None:
            event = threading.Event()
            if shutting_down:
                event.set()
        app = SimpleNamespace(
            _shutting_down_event=event,
            _cycle_id="#12",
            _start_dictation=MagicMock(),
            _stop_dictation=MagicMock(),
        )
        return SimpleNamespace(_app=app, _toggle_lock=threading.Lock())

    def test_toggle_refused_while_shutting_down(self):
        controller = self._controller(shutting_down=True)

        RecordingLifecycle().toggle(controller)

        controller._app._start_dictation.assert_not_called()
        controller._app._stop_dictation.assert_not_called()

    def test_start_refused_while_shutting_down(self):
        controller = self._controller(shutting_down=True)

        RecordingLifecycle().start(controller)

        controller._app._start_dictation.assert_not_called()

    def test_public_entry_proceeds_when_not_shutting_down(self):
        controller = self._controller(shutting_down=False)
        ran: list[bool] = []

        RecordingLifecycle()._run_public_entry(controller, lambda: ran.append(True))

        assert ran == [True]

    def test_mock_like_is_set_is_not_treated_as_shutdown(self):
        """Strict ``is True``: MagicMock ``is_set()`` must not trip the gate."""
        controller = self._controller(shutting_down=False, event=MagicMock())
        ran: list[bool] = []

        RecordingLifecycle()._run_public_entry(controller, lambda: ran.append(True))

        assert ran == [True]


class TestRecordingQuitWritesNoAudioFile:
    """Shutdown during recording: in-RAM audio is discarded, nothing lands on disk."""

    def test_teardown_recorder_stops_stream_and_writes_nothing(self, monkeypatch):
        writes: list[tuple] = []
        monkeypatch.setattr(Path, "write_bytes", lambda self, data: writes.append((self, data)))
        monkeypatch.setattr(Path, "write_text", lambda self, data, **kw: writes.append((self, data)))

        app = SimpleNamespace(
            recorder=MagicMock(),
            recording=SimpleNamespace(_transcription_thread=None),
        )
        app.recorder.recording = True
        app.recorder.stop.return_value = b"in-ram audio that must be dropped"
        controller = SimpleNamespace(
            _app=app,
            _recorder_teardown_done=threading.Event(),
            _recorder_force_closed=False,
        )

        teardown_recorder(controller)

        app.recorder.stop.assert_called_once_with()
        app.recorder.discard.assert_not_called()
        assert controller._recorder_force_closed is False
        assert controller._recorder_teardown_done.is_set()
        assert writes == [], f"shutdown during recording must write no audio file; got {writes}"
