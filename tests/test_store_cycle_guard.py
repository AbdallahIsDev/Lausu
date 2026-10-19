"""A cancelled (ESC) dictation must leave zero traces.

``docs/voice_typer_recording_edge_cases.md`` §1: the default pipeline used
to guard only the paste stage, but ``_store_result`` runs BEFORE it, so a
cancelled cycle still wrote a history row, a crash-recovery entry, the
usage count, and ``_last_transcription`` (undo/repaste resurrected the
text). The store stage is now wrapped in
``CancellationGuard(..., preserve_on_cancel=False)`` and ``_store_result``
re-checks liveness at write time (a cancel can land between the two).
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from voice_typer.server.dictation_pipeline import DictationPipeline
from voice_typer.server.dictation_stages import (
    CancellationGuard,
    PipelineContext,
    StoreResultStage,
    _PipelineAbortCancelled,
    build_default_stages,
)


def _make_app(cycle_id: str, *, cancelled: tuple[str, ...] = ()) -> SimpleNamespace:
    recording = MagicMock()
    recording._cancelled_cycle_ids = OrderedDict((cid, None) for cid in cancelled)
    recording._cancelled_cycle_ids_lock = threading.Lock()
    config = SimpleNamespace(
        history_enabled=True,
        crash_recovery_enabled=True,
        log_transcriptions=False,
        model_size="test-model",
        device="cpu",
    )
    return SimpleNamespace(
        _cycle_id=cycle_id,
        recording=recording,
        config=config,
        history_db=MagicMock(),
        _crash_recovery=MagicMock(),
        correction_usage=MagicMock(),
        _last_transcription=None,
        tray=MagicMock(),
    )


def _make_pipeline(app: SimpleNamespace, cycle_id: str) -> DictationPipeline:
    pipeline = DictationPipeline.__new__(DictationPipeline)
    pipeline._app = app
    pipeline._cycle_id = cycle_id
    pipeline._duration = 1.0
    pipeline._hide_or_idle_bubble = MagicMock()
    return pipeline


def _ctx(app, pipeline, cycle_id: str) -> PipelineContext:
    return PipelineContext(cycle_id=cycle_id, audio=None, app=app, pipeline=pipeline)


def _assert_no_traces(app) -> None:
    app.history_db.add_transcription.assert_not_called()
    app._crash_recovery.add.assert_not_called()
    app.correction_usage.record_dictation.assert_not_called()
    assert app._last_transcription is None


class TestCycleIdClassDefault:
    def test_new_built_pipeline_reads_str_cycle_id(self):
        pipeline = DictationPipeline.__new__(DictationPipeline)
        assert pipeline._cycle_id == ""


class TestStoreGuardBlocksCancelledCycle:
    def test_cancelled_current_cycle_writes_nothing_and_tears_down_bubble(self):
        app = _make_app("#1", cancelled=("#1",))
        pipeline = _make_pipeline(app, "#1")

        with pytest.raises(_PipelineAbortCancelled):
            CancellationGuard(StoreResultStage(), preserve_on_cancel=False).run(
                "cancelled dictation", _ctx(app, pipeline, "#1")
            )

        _assert_no_traces(app)
        pipeline._hide_or_idle_bubble.assert_called_once()

    def test_superseded_cycle_writes_nothing_and_keeps_the_live_bubble(self):
        app = _make_app("#2")
        pipeline = _make_pipeline(app, "#1")

        with pytest.raises(_PipelineAbortCancelled):
            CancellationGuard(StoreResultStage(), preserve_on_cancel=False).run("late text", _ctx(app, pipeline, "#1"))

        _assert_no_traces(app)
        pipeline._hide_or_idle_bubble.assert_not_called()

    def test_store_guard_skips_the_recovery_write(self):
        app = _make_app("#1", cancelled=("#1",))
        pipeline = _make_pipeline(app, "#1")

        with pytest.raises(_PipelineAbortCancelled):
            CancellationGuard(StoreResultStage(), preserve_on_cancel=False).run("late text", _ctx(app, pipeline, "#1"))

        app._crash_recovery.add.assert_not_called()

    def test_live_cycle_reaches_the_wrapped_store_stage(self):
        app = _make_app("#1")
        pipeline = _make_pipeline(app, "#1")
        pipeline._store_result = MagicMock()

        result = CancellationGuard(StoreResultStage(), preserve_on_cancel=False).run(
            "live text", _ctx(app, pipeline, "#1")
        )

        assert result == "live text"
        pipeline._store_result.assert_called_once_with("live text")
        pipeline._hide_or_idle_bubble.assert_not_called()


class TestDefaultPipelineWiring:
    def test_cancelled_cycle_leaves_zero_traces_through_the_default_store_guard(self):
        app = _make_app("#1", cancelled=("#1",))
        pipeline = _make_pipeline(app, "#1")
        store_guard, paste_guard = build_default_stages()[-2:]

        assert isinstance(store_guard, CancellationGuard)
        assert store_guard.name == "store"
        assert isinstance(paste_guard, CancellationGuard)
        assert paste_guard.name == "paste"

        with pytest.raises(_PipelineAbortCancelled):
            store_guard.run("cancelled dictation", _ctx(app, pipeline, "#1"))

        _assert_no_traces(app)


class TestStoreResultRechecksLiveness:
    def test_cancel_between_guard_and_write_returns_early(self):
        app = _make_app("#1", cancelled=("#1",))
        pipeline = _make_pipeline(app, "#1")

        pipeline._store_result("late text")

        _assert_no_traces(app)

    def test_live_cycle_still_writes_history_recovery_undo_and_event(self, monkeypatch):
        published: list[dict] = []
        monkeypatch.setattr("voice_typer.server.event_bus.publish", lambda msg: published.append(msg) or True)
        app = _make_app("#1")
        app.history_db.add_transcription.return_value = 7
        pipeline = _make_pipeline(app, "#1")

        pipeline._store_result("live text")

        app.history_db.add_transcription.assert_called_once()
        app._crash_recovery.add.assert_called_once_with("live text", pasted=False, cycle_id="#1")
        app._crash_recovery.flush.assert_called_once_with(timeout=2.0)
        app.correction_usage.record_dictation.assert_called_once()
        assert app._last_transcription == "live text"
        assert [msg["type"] for msg in published] == ["transcription_final"]
