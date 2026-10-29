"""Model leases, switch deferral and media-specific model loading (WS4/WS5)."""

from __future__ import annotations

import logging
import threading
import time
import types

import pytest
from voice_typer.server.media_ingest import lease as lease_mod
from voice_typer.server.media_ingest.errors import MODEL_CHANGED, MODEL_LOADING, MediaIngestError
from voice_typer.server.media_ingest.jobs import MediaJobManager
from voice_typer.server.media_ingest.lease import ModelLeaseGate
from voice_typer.server.model_manager._change import ChangeMixin
from voice_typer.server.model_manager._loading import LoadingMixin


class TestLeaseGate:
    def test_tracks_labels_and_idle(self):
        gate = ModelLeaseGate()
        first = gate.begin("whisper/small.en")
        second = gate.begin("cloud/openai/whisper-1")
        assert gate.active() == 2
        assert gate.engines() == {"whisper/small.en", "cloud/openai/whisper-1"}
        gate.end(first)
        gate.end(second)
        assert gate.active() == 0
        assert gate.wait_for_idle(0) is True

    def test_wait_for_idle_times_out(self):
        gate = ModelLeaseGate()
        gate.begin("whisper/old")
        started = time.perf_counter()
        assert gate.wait_for_idle(0.05) is False
        assert time.perf_counter() - started >= 0.04

    def test_end_is_idempotent(self):
        gate = ModelLeaseGate()
        token = gate.begin("x")
        gate.end(token)
        gate.end(token)
        assert gate.active() == 0


class _SwitchHarness(ChangeMixin):
    """Just enough object for the lease-wait helper."""

    def __init__(self) -> None:
        self.notices: list[str] = []
        self._app = types.SimpleNamespace(
            tray=types.SimpleNamespace(notify=lambda title, message: self.notices.append(message))
        )


class TestModelSwitchDeferral:
    def _gate(self, monkeypatch) -> ModelLeaseGate:
        gate = ModelLeaseGate()
        monkeypatch.setattr(lease_mod, "get_lease_gate", lambda: gate)
        return gate

    def test_no_running_jobs_does_not_wait(self, monkeypatch):
        self._gate(monkeypatch)
        harness = _SwitchHarness()
        started = time.perf_counter()
        assert harness._defer_switch_to_running_media_jobs() is True
        assert time.perf_counter() - started < 0.05

    def test_switch_waits_for_four_jobs_before_unloading(self, monkeypatch):
        """Four jobs finish on their own engine; the unload waits for them."""
        gate = self._gate(monkeypatch)
        manager = MediaJobManager(max_jobs=4)
        labels: list[str] = []
        unloaded = threading.Event()
        all_done = threading.Event()

        def _runner(job):
            token = gate.begin("whisper/old-model")
            labels.append("whisper/old-model")
            time.sleep(0.15)
            gate.end(token)
            return {"row_id": len(labels)}

        for _ in range(4):
            manager.start("fake", _runner)
        time.sleep(0.02)
        assert gate.active() == 4

        def _finish() -> None:
            manager.wait(5.0)
            all_done.set()

        finisher = threading.Thread(target=_finish)
        finisher.start()
        harness = _SwitchHarness()
        assert harness._defer_switch_to_running_media_jobs() is True
        unloaded.set()
        finisher.join(5)
        assert all_done.is_set(), "the switch returned before the jobs finished"
        # Unload only after every lease was released, and every job kept the
        # engine it started with.
        assert unloaded.is_set()
        assert labels == ["whisper/old-model"] * 4
        assert gate.active() == 0
        assert harness.notices == []

    def test_timeout_cancels_then_refuses_when_still_leased(self, monkeypatch):
        """A job that will not let go refuses the switch instead of tearing down."""
        from voice_typer.server import event_bus
        from voice_typer.server.media_ingest import jobs as jobs_mod

        gate = self._gate(monkeypatch)
        token = gate.begin("whisper/old-model")
        monkeypatch.setattr(lease_mod, "MODEL_SWITCH_LEASE_TIMEOUT_S", 0.05)
        monkeypatch.setattr(lease_mod, "MODEL_SWITCH_LEASE_CANCEL_GRACE_S", 0.05)

        cancel_calls: list[str | None] = []

        class _Manager:
            def cancel(self, job_id=None, *, reason=None):
                cancel_calls.append(reason)
                return ["job-1", "job-2"]

        monkeypatch.setattr(jobs_mod, "get_job_manager", lambda: _Manager())
        events: list[dict] = []
        monkeypatch.setattr(event_bus, "publish", lambda event: events.append(event))

        harness = _SwitchHarness()
        assert harness._defer_switch_to_running_media_jobs() is False
        assert cancel_calls == [MODEL_CHANGED]
        published = [e for e in events if e["type"] == "media_jobs_cancelled_for_model_change"]
        assert published and published[0]["data"]["count"] == 2
        # The change already acked `{"status": "loading"}`, so the refusal
        # itself must reach the renderer or the spinner never stops.
        refused = [e for e in events if e["type"] == "media_model_switch_refused"]
        assert refused and refused[0]["data"]["count"] == 1, (
            f"a refused switch must publish media_model_switch_refused: {events!r}"
        )
        assert harness.notices, "a refused switch must tell the user"
        assert gate.active() == 1
        gate.end(token)

    def test_cancelled_jobs_release_and_the_switch_applies(self, monkeypatch):
        from voice_typer.server import event_bus
        from voice_typer.server.media_ingest import jobs as jobs_mod

        gate = self._gate(monkeypatch)
        token = gate.begin("whisper/old-model")
        monkeypatch.setattr(lease_mod, "MODEL_SWITCH_LEASE_TIMEOUT_S", 0.02)
        monkeypatch.setattr(lease_mod, "MODEL_SWITCH_LEASE_CANCEL_GRACE_S", 0.5)

        class _Manager:
            def cancel(self, job_id=None, *, reason=None):
                gate.end(token)
                return ["job-1"]

        monkeypatch.setattr(jobs_mod, "get_job_manager", lambda: _Manager())
        monkeypatch.setattr(event_bus, "publish", lambda event: None)
        harness = _SwitchHarness()
        assert harness._defer_switch_to_running_media_jobs() is True
        assert harness.notices == []


class TestRegistryRefusesUnloadWhileLeased:
    def _registry(self):
        from voice_typer.server.asr_registry import AsrBackendRegistry

        config = types.SimpleNamespace(asr_backend="whisper", disabled_backends=[])
        return AsrBackendRegistry(config)

    def test_unload_is_refused_while_a_lease_is_held(self, monkeypatch, caplog):
        gate = ModelLeaseGate()
        monkeypatch.setattr(lease_mod, "get_lease_gate", lambda: gate)
        registry = self._registry()
        unloaded: list[int] = []
        backend = types.SimpleNamespace(
            is_loaded=True, unload=lambda: unloaded.append(1), device_info="cpu", loaded_via="x"
        )
        registry.register("whisper", backend)
        token = gate.begin("whisper/small.en")

        with caplog.at_level(logging.ERROR, logger="voice_typer.server.asr_registry"):
            registry.unload("whisper")
        assert unloaded == [], "the engine was freed under a running job"
        assert "refusing to unload" in caplog.text

        gate.end(token)
        registry.unload("whisper")
        assert unloaded == [1]


class TestEngineUnloadIsBounded:
    def test_whisper_unload_skips_when_the_inference_lock_is_held(self, monkeypatch, caplog):
        from voice_typer.server import system_whisper

        monkeypatch.setattr("voice_typer.server.asr.registry.MODEL_UNLOAD_LOCK_TIMEOUT_S", 0.05)
        engine = system_whisper.SystemWhisperEngine.__new__(system_whisper.SystemWhisperEngine)
        engine._inference_lock = threading.RLock()
        engine._model = object()
        engine._loaded = True
        # RLock is re-entrant, so the holder must be ANOTHER thread: that is
        # the real shape (a decode in progress), not the same thread nesting.
        holding = threading.Event()
        release = threading.Event()

        def _hold() -> None:
            with engine._inference_lock:
                holding.set()
                release.wait(5)

        holder = threading.Thread(target=_hold, daemon=True)
        holder.start()
        assert holding.wait(5)
        try:
            with caplog.at_level(logging.ERROR, logger="voice_typer.server.system_whisper"):
                engine.unload()
        finally:
            release.set()
            holder.join(5)
        assert engine._model is not None, "the model was freed while a decode held it"
        assert engine._loaded is True
        assert "refusing to unload" in caplog.text

    def test_parakeet_unload_skips_when_inference_is_active(self, monkeypatch, caplog):
        from voice_typer.server.parakeet_engine import ParakeetEngine

        monkeypatch.setattr("voice_typer.server.asr.registry.MODEL_UNLOAD_LOCK_TIMEOUT_S", 0.05)
        engine = ParakeetEngine.__new__(ParakeetEngine)
        engine._lock = threading.RLock()
        engine._inference_cond = threading.Condition(engine._lock)
        engine._active_inference = 1
        engine._model = object()
        engine._processor = None
        with caplog.at_level(logging.ERROR, logger="voice_typer.server.parakeet_engine"):
            engine.unload()
        assert engine._model is not None
        assert "refusing to unload" in caplog.text

    def test_qwen_unload_skips_when_inference_is_active(self, monkeypatch, caplog):
        from voice_typer.server import qwen_engine

        monkeypatch.setattr("voice_typer.server.asr.registry.MODEL_UNLOAD_LOCK_TIMEOUT_S", 0.05)
        engine = qwen_engine.QwenEngine.__new__(qwen_engine.QwenEngine)
        engine._lock = threading.RLock()
        engine._inference_cond = threading.Condition(engine._lock)
        engine._active_inference = 1
        engine._model = object()
        engine._onnx_model = None
        with caplog.at_level(logging.ERROR, logger="voice_typer.server.qwen_engine"):
            engine.unload()
        assert engine._model is not None
        assert "refusing to unload" in caplog.text


class _FakeRegistry:
    def __init__(self, busy: bool) -> None:
        self._busy = busy
        self.active_name = "whisper"

    def is_busy(self, name=None) -> bool:
        return self._busy


class _MediaLoadHarness(LoadingMixin):
    def __init__(
        self,
        *,
        engine=None,
        busy: bool = False,
        size: str = "small.en",
        load_thread: threading.Thread | None = None,
    ) -> None:
        self._app = types.SimpleNamespace(
            config=types.SimpleNamespace(asr_backend="whisper", model_size=size),
            tray=types.SimpleNamespace(set_state=lambda *a, **k: None),
        )
        self._registry = _FakeRegistry(busy)
        self._pending_dictation = False
        self._model_load_thread = load_thread
        self._sync_load_in_progress = False
        self._lazy_init_lock = threading.Lock()
        self._engine = engine
        self.ensure_calls: list[bool] = []

    def active_transcriber(self):
        return self._engine

    def ensure_active_engine_loaded(self, *, queue_pending_dictation: bool = True):
        self.ensure_calls.append(queue_pending_dictation)
        return self._engine

    def cancel_idle_unload_timer(self) -> None:
        return None


class TestMediaModelLoading:
    def test_busy_backend_is_reported_as_loading_not_missing(self):
        harness = _MediaLoadHarness(busy=True)
        with pytest.raises(MediaIngestError) as excinfo:
            harness.ensure_engine_loaded_for_media()
        assert excinfo.value.code == MODEL_LOADING
        assert harness._pending_dictation is False
        assert harness.ensure_calls == []

    def test_nothing_selected_is_no_model(self):
        harness = _MediaLoadHarness(size="")
        result = harness.ensure_engine_loaded_for_media()
        assert result.state == "no_model"

    def test_ready_engine_carries_a_label_from_the_engine(self):
        engine = types.SimpleNamespace(is_loaded=True, _model_size="small.en")
        harness = _MediaLoadHarness(engine=engine)
        result = harness.ensure_engine_loaded_for_media()
        assert result.state == "ready"
        assert result.engine is engine
        assert result.label == "whisper/small.en"

    def test_in_flight_load_is_awaited_then_reported_ready(self, monkeypatch):
        from voice_typer.server.model_manager import _loading

        monkeypatch.setattr(_loading, "MEDIA_MODEL_LOAD_WAIT_S", 2.0)
        engine = types.SimpleNamespace(is_loaded=True, _model_size="small.en")
        release = threading.Event()

        def _load() -> None:
            release.wait(2)
            harness._engine = engine

        harness = _MediaLoadHarness()
        thread = threading.Thread(target=_load, daemon=True)
        harness._model_load_thread = thread
        thread.start()
        threading.Timer(0.1, release.set).start()
        result = harness.ensure_engine_loaded_for_media()
        assert result.state == "ready"
        assert result.engine is engine
        thread.join(2)

    def test_in_flight_load_that_never_finishes_is_retryable(self, monkeypatch):
        from voice_typer.server.model_manager import _loading

        monkeypatch.setattr(_loading, "MEDIA_MODEL_LOAD_WAIT_S", 0.2)
        release = threading.Event()

        def _load() -> None:
            release.wait(5)

        harness = _MediaLoadHarness()
        thread = threading.Thread(target=_load, daemon=True)
        harness._model_load_thread = thread
        thread.start()
        try:
            with pytest.raises(MediaIngestError) as excinfo:
                harness.ensure_engine_loaded_for_media()
            assert excinfo.value.code == MODEL_LOADING
        finally:
            release.set()
            thread.join(2)

    def test_failed_load_keeps_no_engine_with_a_reason(self):
        harness = _MediaLoadHarness()
        result = harness.ensure_engine_loaded_for_media()
        assert result.state == "failed"
        assert result.reason
        assert harness.ensure_calls == [False]

    def test_media_never_queues_a_pending_dictation(self):
        """The busy path must not pin `_pending_dictation` from media."""
        harness = _MediaLoadHarness(busy=True)
        result = LoadingMixin.ensure_active_engine_loaded(harness, queue_pending_dictation=False)
        assert result is None
        assert harness._pending_dictation is False

        control = _MediaLoadHarness(busy=True)
        assert LoadingMixin.ensure_active_engine_loaded(control) is None
        assert control._pending_dictation is True, "the dictation control must still queue"
