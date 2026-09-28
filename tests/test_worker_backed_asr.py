"""Unit tests for the C7 worker-backed whisper backend."""

from __future__ import annotations

import concurrent.futures

import numpy as np
import pytest
from voice_typer.server.asr_errors import ModelNotDownloadedError
from voice_typer.server.worker_backed_asr import WorkerBackedAsr, WorkerTranscriptionError


class _FakeClient:
    def __init__(self, port=5123) -> None:
        self._port = port
        self.requests: list = []
        self.abort_all_calls = 0

    @property
    def port(self):
        return self._port

    def request_samples(self, raw, rate, language, timeout=None):
        self.requests.append((bytes(raw), rate, language))
        future: concurrent.futures.Future[dict] = concurrent.futures.Future()
        future.set_result({"text": "shimmed", "latency_ms": 5, "device_info": "cpu (int8)"})
        return future

    def abort_all_outstanding(self) -> int:
        self.abort_all_calls += 1
        return 0


class TestRegistryMapping:
    def test_whisper_spec_points_at_shim(self):
        from voice_typer.server.asr_registry import AsrBackendRegistry

        assert AsrBackendRegistry._BACKEND_SPECS["whisper"] == (
            "voice_typer.server.worker_backed_asr",
            "WorkerBackedAsr",
        )

    def test_create_whisper_builds_shim(self):
        from unittest.mock import MagicMock

        from voice_typer.server.asr_registry import AsrBackendRegistry

        registry = AsrBackendRegistry(MagicMock())
        backend = registry.create("whisper", whisper_kwargs={"model_size": "small.en"})
        assert isinstance(backend, WorkerBackedAsr)


class TestLoad:
    def test_load_refuses_without_pack(self, monkeypatch):
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: None)
        with pytest.raises(ModelNotDownloadedError):
            WorkerBackedAsr(model_size="small.en").load()

    def test_load_ok_with_pack(self, monkeypatch):
        from voice_typer.server.service import update_check

        monkeypatch.setattr(update_check, "_local_offline_pack_version", lambda *a, **k: "1.0.0")
        backend = WorkerBackedAsr(model_size="small.en")
        assert backend.load() is True
        assert backend.is_loaded is True
        backend.unload()
        assert backend.is_loaded is False


class TestTranscribe:
    def test_forwards_and_returns_text(self, monkeypatch):
        import voice_typer.server.worker_backed_asr as shim_mod

        fake = _FakeClient()
        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: fake)
        backend = WorkerBackedAsr(model_size="small.en", language="en")
        audio = np.zeros(16000, dtype=np.float32)
        assert backend.transcribe_with_fallback(audio) == "shimmed"
        raw, rate, language = fake.requests[0]
        assert rate == 16000
        assert language == "en"
        assert len(raw) == 16000 * 4
        assert backend.device_info == "cpu (int8)"

    def test_no_port_raises(self, monkeypatch):
        import voice_typer.server.worker_backed_asr as shim_mod

        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: _FakeClient(port=None))
        with pytest.raises(WorkerTranscriptionError):
            WorkerBackedAsr().transcribe_with_fallback(np.zeros(100, dtype=np.float32))

    def test_worker_error_raises_not_silence(self, monkeypatch):
        import voice_typer.server.worker_backed_asr as shim_mod

        class _FailClient(_FakeClient):
            def request_samples(self, *a, **k):
                raise RuntimeError("hop down")

        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: _FailClient())
        with pytest.raises(WorkerTranscriptionError):
            WorkerBackedAsr().transcribe_with_fallback(np.zeros(100, dtype=np.float32))

    def test_abort_propagates_unwrapped(self, monkeypatch):
        import voice_typer.server.worker_backed_asr as shim_mod
        from voice_typer.server.worker_client import WorkerAbortedError

        class _AbortClient(_FakeClient):
            def request_samples(self, *a, **k):
                future: concurrent.futures.Future[dict] = concurrent.futures.Future()
                future.set_exception(WorkerAbortedError("esc"))
                return future

        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: _AbortClient())
        with pytest.raises(WorkerAbortedError):
            WorkerBackedAsr().transcribe_with_fallback(np.zeros(100, dtype=np.float32))

    def test_request_abort_reaches_client(self, monkeypatch):
        import voice_typer.server.worker_backed_asr as shim_mod

        fake = _FakeClient()
        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: fake)
        backend = WorkerBackedAsr()
        backend.request_abort()
        backend.clear_abort()
        assert fake.abort_all_calls == 1

    def test_transcribe_protocol_alias(self, monkeypatch):
        """``transcribe`` is the mic-test / CloudEngine-fallback surface."""
        import voice_typer.server.worker_backed_asr as shim_mod

        fake = _FakeClient()
        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: fake)
        backend = WorkerBackedAsr(model_size="small.en", language="en")
        audio = np.zeros(16000, dtype=np.float32)
        assert backend.transcribe(audio, audio_stats=(0.1, 0.5, 10.0)) == "shimmed"
        assert len(fake.requests) == 1

    def test_no_transcribe_words_surface(self):
        assert not hasattr(WorkerBackedAsr(), "transcribe_words")
        assert WorkerBackedAsr.worker_backed is True
