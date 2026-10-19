"""Stuck-worker end-to-end pin: a force-recovered zombie worker may store
nothing, borrow nothing, and type nothing for a cycle that is no longer live.

Scope note: the e2e boundary starts at text production. Audio capture and
transcription are not re-driven here; instead the real guards plus the real
``_copy_and_paste`` run over the production stage list with an in-memory
clipboard, proving that a late text produced by an old cycle leaves zero
traces in the new cycle.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from voice_typer.server import clipboard as clip_mod
from voice_typer.server.branding import APP_NAME
from voice_typer.server.clipboard import ClipboardManager
from voice_typer.server.clipboard_snapshot import ClipboardSnapshot
from voice_typer.server.dictation_pipeline import DictationPipeline
from voice_typer.server.dictation_stages import (
    PipelineContext,
    _PipelineAbortCancelled,
    build_default_stages,
)
from voice_typer.server.recording_controller import RecordingController
from voice_typer.server.transcription_watchdog import TranscriptionWatchdog
from voice_typer.server.tray_types import AppState

from tests.fixtures.clipboard_helpers import make_clipboard_manager

NEW_CYCLE_TEXT = "the live cycle's dictation"
LATE_TEXT = "the zombie's late dictation"
USER_CLIPBOARD = "the user's own copied text"


class _FakeClipboard:
    """In-memory clipboard: a borrow or a restore would leave a trace here."""

    def __init__(self, text: str = USER_CLIPBOARD) -> None:
        self.text = text
        self.copies: list[str] = []

    def copy(self, text: str) -> None:
        self.copies.append(text)
        self.text = text

    def read(self) -> str:
        return self.text


@pytest.fixture(autouse=True)
def _isolate_clipboard(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":99")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with clip_mod._pending_restores_lock:
        clip_mod._pending_restores.clear()
    yield
    with clip_mod._pending_restores_lock:
        clip_mod._pending_restores.clear()


@pytest.fixture
def fake_clipboard():
    fake = _FakeClipboard()
    with (
        patch.object(clip_mod, "_copy_to_clipboard", side_effect=fake.copy),
        patch.object(clip_mod, "_paste_from_clipboard", side_effect=fake.read),
        patch.object(clip_mod, "_win32_empty_clipboard"),
        patch.object(clip_mod, "_win32_exclude_clipboard_from_monitoring"),
        patch.object(ClipboardSnapshot, "capture", return_value=None),
        patch.object(ClipboardManager, "_get_clipboard_sequence_number", return_value=0),
    ):
        yield fake


def _make_app_with_controller(cycle_id: str):
    cancelled_ids: OrderedDict[str, None] = OrderedDict()
    cancelled_lock = threading.Lock()
    controller = RecordingController.__new__(RecordingController)
    controller._app = None  # set below once the app exists
    controller._transcription_thread = None
    controller._watchdog_lock = threading.Lock()
    controller._watchdog_event = threading.Event()
    controller._watchdog_stop_event = threading.Event()
    controller._watchdog_thread = None
    controller._watchdog_firings = 0
    controller._watchdog_max_firings = 3
    controller._current_audio = None
    controller._cancelled_cycle_ids = cancelled_ids
    controller._cancelled_cycle_ids_lock = cancelled_lock
    controller._stop_watchdog_thread = lambda: None
    controller._cancel_streaming_session = lambda: None

    app = SimpleNamespace(
        _cycle_id=cycle_id,
        recording=controller,
        config=SimpleNamespace(
            history_enabled=True,
            crash_recovery_enabled=True,
            log_transcriptions=False,
            model_size="test-model",
            device="cpu",
            paste_on_stop=True,
            clipboard_save_restore=True,
            hotkey="f2",
        ),
        clipboard=make_clipboard_manager(),
        history_db=MagicMock(),
        _crash_recovery=MagicMock(),
        correction_usage=MagicMock(),
        _last_transcription=None,
        tray=MagicMock(),
        _waveform_bubble=MagicMock(),
        _busyness=MagicMock(),
        _schedule_timer=MagicMock(),
        _busy_event=threading.Event(),  # stays unset so force_recover proceeds
    )
    app._busyness.set_idle.side_effect = app._busy_event.set
    controller._app = app
    return app, controller


def _make_pipeline(app: SimpleNamespace, cycle_id: str) -> DictationPipeline:
    pipeline = DictationPipeline.__new__(DictationPipeline)
    pipeline._app = app
    pipeline._cycle_id = cycle_id
    pipeline._device_info = "test-device"
    pipeline._duration = 1.0
    pipeline._hide_or_idle_bubble = MagicMock()
    return pipeline


def _ctx(app: SimpleNamespace, pipeline: DictationPipeline, cycle_id: str) -> PipelineContext:
    return PipelineContext(cycle_id=cycle_id, audio=None, app=app, pipeline=pipeline)


def _assert_no_store_traces(app: SimpleNamespace) -> None:
    app.history_db.add_transcription.assert_not_called()
    app.correction_usage.record_dictation.assert_not_called()
    assert app._last_transcription is None


class TestLateTextFromCancelledWorker:
    def test_force_recovered_worker_stores_nothing(self, fake_clipboard):
        app, controller = _make_app_with_controller("#1")
        TranscriptionWatchdog().force_recover(controller, force=True)
        assert "#1" in controller._cancelled_cycle_ids

        pipeline = _make_pipeline(app, "#1")
        store_guard = build_default_stages()[-2]
        with pytest.raises(_PipelineAbortCancelled):
            store_guard.run(LATE_TEXT, _ctx(app, pipeline, "#1"))

        # The cancelled cycle was still current when it died, so the guard
        # tears the bubble down; nothing else may have been written.
        pipeline._hide_or_idle_bubble.assert_called_once()
        _assert_no_store_traces(app)
        app._crash_recovery.add.assert_not_called()

        app.clipboard.paste = MagicMock()
        pipeline._copy_and_paste(LATE_TEXT)
        assert fake_clipboard.copies == []
        assert fake_clipboard.text == USER_CLIPBOARD
        app.clipboard.paste.assert_not_called()

    def test_superseded_worker_stores_nothing_and_keeps_the_bubble(self, fake_clipboard):
        app, _controller = _make_app_with_controller("#2")
        pipeline = _make_pipeline(app, "#1")  # the previous cycle's pipeline
        store_guard = build_default_stages()[-2]
        with pytest.raises(_PipelineAbortCancelled):
            store_guard.run(LATE_TEXT, _ctx(app, pipeline, "#1"))

        pipeline._hide_or_idle_bubble.assert_not_called()
        _assert_no_store_traces(app)


class TestFlagShipZombieChain:
    def test_marked_and_superseded_worker_leaves_zero_traces(self, fake_clipboard):
        app, controller = _make_app_with_controller("#1")
        watchdog = TranscriptionWatchdog()
        watchdog.mark_cycle_cancelled(controller, "#1")
        app._cycle_id = "#2"  # the live cycle replaced it
        fake_clipboard.text = NEW_CYCLE_TEXT

        stages = build_default_stages()
        store_guard, paste_guard = stages[-2], stages[-1]
        ctx = _ctx(app, _make_pipeline(app, "#1"), "#1")
        with pytest.raises(_PipelineAbortCancelled):
            store_guard.run(LATE_TEXT, ctx)
        with pytest.raises(_PipelineAbortCancelled):
            paste_guard.run(LATE_TEXT, ctx)

        _assert_no_store_traces(app)
        app._crash_recovery.add.assert_called_once_with(LATE_TEXT, pasted=False, cycle_id="#1")
        app.clipboard.paste = MagicMock()
        ctx.pipeline._copy_and_paste(LATE_TEXT)
        app.clipboard.paste.assert_not_called()
        assert fake_clipboard.copies == []
        assert fake_clipboard.text == NEW_CYCLE_TEXT
        assert clip_mod._pending_restores == []
        ctx.pipeline._hide_or_idle_bubble.assert_not_called()
        app.tray.set_state.assert_not_called()
        app._schedule_timer.assert_not_called()


class TestForceRecoverSideEffects:
    def test_recovery_marks_cycle_and_resets_transport(self, fake_clipboard):
        app, controller = _make_app_with_controller("#1")
        i18n_t = MagicMock(side_effect=lambda key, **kw: key)
        with patch("voice_typer.server.transcription_watchdog.i18n.t", i18n_t):
            TranscriptionWatchdog().force_recover(controller, force=True)

        assert "#1" in controller._cancelled_cycle_ids
        assert app._busy_event.is_set() is True
        assert controller._current_audio is None
        assert app._schedule_timer.call_args.args[0] == 5.0
        app.tray.set_state.assert_any_call(AppState.IDLE, "state.recording_controller.recovered")
        app.tray.notify.assert_called_once_with(APP_NAME, "notify.recording_controller.cancelled_timeout")
        i18n_t.assert_any_call("notify.recording_controller.cancelled_timeout", hotkey="F2")


class TestLiveCycleStillStores:
    def test_live_cycle_stores_with_no_regression(self, fake_clipboard):
        app, _controller = _make_app_with_controller("#1")
        app.history_db.add_transcription.return_value = 1
        pipeline = _make_pipeline(app, "#1")
        store_guard = build_default_stages()[-2]

        store_guard.run("live dictation", _ctx(app, pipeline, "#1"))

        app.history_db.add_transcription.assert_called_once()
        assert app._last_transcription == "live dictation"
