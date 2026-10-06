"""ADR-0025 C5 dictation cutover tests (sites 1+2)."""

from __future__ import annotations

import concurrent.futures
import contextlib
import json
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from voice_typer.server import worker_client as worker_client_mod
from voice_typer.server.cloud_engines import CloudEngine
from voice_typer.server.dictation_pipeline import DictationPipeline
from voice_typer.server.worker_client import WorkerAbortedError, WorkerClient
from voice_typer.server.worker_path import worker_path_available, worker_path_for_backend


def _gate_app(active) -> MagicMock:
    app = MagicMock()
    app.models.active_transcriber.return_value = active
    return app


def _port_stub(port):
    return SimpleNamespace(port=port)


class TestGateMatrix:
    def test_cloud_backend_is_off(self, monkeypatch):
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: _port_stub(5123))
        active = CloudEngine(provider="openai", api_key="k", consent_given=True)
        assert worker_path_available(_gate_app(active)) == (False, "cloud_backend")

    def test_pack_missing_is_off(self, monkeypatch):
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: None)
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: _port_stub(5123))
        assert worker_path_available(_gate_app(MagicMock())) == (False, "offline_pack_missing")

    def test_no_port_is_off(self, monkeypatch):
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "1.0.0")
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: _port_stub(None))
        assert worker_path_available(_gate_app(MagicMock())) == (False, "worker_no_port")

    def test_all_legs_on(self, monkeypatch):
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "1.0.0")
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: _port_stub(5123))
        assert worker_path_available(_gate_app(MagicMock())) == (True, "ok")


class TestForBackend:
    """Backend-object form shares the one gate (E7, media ingest shape)."""

    def test_name_only_cloud_double_is_off(self):
        class CloudEngine:
            pass

        assert worker_path_for_backend(CloudEngine()) == (False, "cloud_backend")

    def test_pack_missing_is_off(self, monkeypatch):
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: None)
        assert worker_path_for_backend(MagicMock()) == (False, "offline_pack_missing")

    def test_no_port_is_off(self, monkeypatch):
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "1.0.0")
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: _port_stub(None))
        assert worker_path_for_backend(MagicMock()) == (False, "worker_no_port")


class TestAbortAll:
    def test_fails_futures_and_sends_aborts(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            client._port = 5123
            first = client.request_samples(b"\x00" * 32, 16000, "en")
            second = client.request_samples(b"\x01" * 32, 16000, "en")
            assert first is not None and second is not None
            assert client.abort_all_outstanding() == 2
            for future in (first, second):
                assert isinstance(future.exception(timeout=5), WorkerAbortedError)
            aborts = [json.loads(f) for f in list(client._outbound.queue)]
            assert [a["cmd"] for a in aborts if a.get("cmd") == "abort_request"] == ["abort_request"] * 2
            assert {a["id"] for a in aborts} == {1, 2}
            assert client._resolvers == {}
        finally:
            client.close()

    def test_empty_is_zero(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            assert client.abort_all_outstanding() == 0
        finally:
            client.close()


def _pipeline_app(engine) -> MagicMock:
    app = MagicMock()
    app.models.active_transcriber.return_value = engine
    app.recording.pop_streaming_session.return_value = None
    app.recording._cancelled_cycle_ids = set()
    app.recording._cancelled_cycle_ids_lock = threading.Lock()

    @contextlib.contextmanager
    def _busy(name=None):
        yield name

    app.models.registry.busy_context = _busy
    app.models.registry.active_name = "parakeet"
    app.config.sample_rate = 16000
    app.config.language = "en"
    return app


def _pipeline(app, audio) -> DictationPipeline:
    pipeline = DictationPipeline.__new__(DictationPipeline)
    pipeline._app = app
    pipeline._cycle_id = "cutover-cycle"
    pipeline._audio = audio
    pipeline._audio_stats = None
    pipeline._duration = 1.0
    pipeline._recorded_rms = 0.02
    pipeline._device_info = ""
    pipeline._quality_summary = None
    pipeline._last_resources_check_ts = 0.0
    pipeline._resources_check_interval = 60.0
    return pipeline


def _engine(text="local words"):
    engine = MagicMock()
    engine.is_loaded = True
    engine.device_info = "fake-cpu"
    engine.last_quality_summary = {"score": 0.5}
    engine.transcribe_with_fallback.return_value = text
    return engine


def _resolved_future(result):
    future: concurrent.futures.Future[dict] = concurrent.futures.Future()
    future.set_result(result)
    return future


def _failed_future(exc):
    future: concurrent.futures.Future[dict] = concurrent.futures.Future()
    future.set_exception(exc)
    return future


class TestBatchCutover:
    """C7: worker-backed backends go through the shim (no in-process)."""

    def _shim_app(self, monkeypatch, result):
        from voice_typer.server import worker_backed_asr as shim_mod

        shim = shim_mod.WorkerBackedAsr(model_size="small.en", language="en")
        fake = MagicMock()
        fake.port = 5123
        fake.request_samples.return_value = result
        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: fake)
        app = _pipeline_app(shim)
        return app, fake

    def test_worker_text_used_and_local_untouched(self, monkeypatch):
        app, fake = self._shim_app(
            monkeypatch, _resolved_future({"text": "worker words", "latency_ms": 7, "device_info": "cpu-test"})
        )
        pipeline = _pipeline(app, np.zeros(16000, dtype=np.float32))
        assert pipeline._transcribe() == "worker words"
        assert fake.request_samples.call_count == 1
        assert pipeline._device_info == "cpu-test"
        assert pipeline._quality_summary is None

    def test_auto_detect_sends_none_language_to_worker(self, monkeypatch):
        app, fake = self._shim_app(
            monkeypatch, _resolved_future({"text": "worker words", "latency_ms": 7, "device_info": "cpu-test"})
        )
        app.config.language = ""
        pipeline = _pipeline(app, np.zeros(16000, dtype=np.float32))
        assert pipeline._transcribe() == "worker words"
        assert fake.request_samples.call_args.args[2] is None

    def test_explicit_language_still_reaches_worker(self, monkeypatch):
        app, fake = self._shim_app(
            monkeypatch, _resolved_future({"text": "worker words", "latency_ms": 7, "device_info": "cpu-test"})
        )
        app.config.language = "ar"
        pipeline = _pipeline(app, np.zeros(16000, dtype=np.float32))
        assert pipeline._transcribe() == "worker words"
        assert fake.request_samples.call_args.args[2] == "ar"

    def test_timeout_degrades_instead_of_in_process(self, monkeypatch):
        from voice_typer.server.dictation_pipeline.transcribe_step import BackendNotLoadedError

        app, _fake = self._shim_app(monkeypatch, _failed_future(TimeoutError("slow worker")))
        pipeline = _pipeline(app, np.zeros(16000, dtype=np.float32))
        with pytest.raises(BackendNotLoadedError):
            pipeline._transcribe()

    def test_aborted_returns_empty(self, monkeypatch):
        app, fake = self._shim_app(monkeypatch, _failed_future(WorkerAbortedError("esc")))
        pipeline = _pipeline(app, np.zeros(16000, dtype=np.float32))
        assert pipeline._transcribe() == ""
        assert fake.request_samples.call_count == 1

    def test_gate_off_stays_in_process(self, monkeypatch):
        import voice_typer.server.worker_path as worker_path_mod

        engine = _engine()
        app = _pipeline_app(engine)
        fake = MagicMock()
        monkeypatch.setattr(worker_path_mod, "worker_path_available", lambda _a: (False, "worker_no_port"))
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: fake)
        pipeline = _pipeline(app, np.zeros(16000, dtype=np.float32))
        assert pipeline._transcribe() == "local words"
        fake.request_samples.assert_not_called()


class TestStreamingUntouched:
    def test_session_finalize_wins_without_worker(self, monkeypatch):
        import voice_typer.server.worker_path as worker_path_mod

        engine = _engine()
        app = _pipeline_app(engine)
        session = MagicMock()
        session.finalize.return_value = "stream words"
        app.recording.pop_streaming_session.return_value = session
        monkeypatch.setattr(
            worker_path_mod,
            "worker_path_available",
            lambda _a: (_ for _ in ()).throw(AssertionError("streaming must not consult the gate")),
        )
        fake = MagicMock()
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: fake)
        pipeline = _pipeline(app, np.zeros(16000, dtype=np.float32))
        assert pipeline._transcribe() == "stream words"
        fake.request_samples.assert_not_called()
        engine.transcribe_with_fallback.assert_not_called()


class TestRequestAbortSite2:
    def test_aborts_worker_and_engine(self, monkeypatch):
        app = MagicMock()
        engine = MagicMock()
        app.models.active_transcriber.return_value = engine
        fake = MagicMock()
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: fake)
        pipeline = DictationPipeline.__new__(DictationPipeline)
        pipeline._app = app
        pipeline.request_abort()
        fake.abort_all_outstanding.assert_called_once_with()
        engine.request_abort.assert_called_once_with()

    def test_worker_failure_still_aborts_engine(self, monkeypatch):
        app = MagicMock()
        engine = MagicMock()
        app.models.active_transcriber.return_value = engine
        fake = MagicMock()
        fake.abort_all_outstanding.side_effect = RuntimeError("client down")
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: fake)
        pipeline = DictationPipeline.__new__(DictationPipeline)
        pipeline._app = app
        pipeline.request_abort()
        engine.request_abort.assert_called_once_with()
