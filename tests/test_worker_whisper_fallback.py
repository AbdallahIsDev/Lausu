"""Worker-first whisper fallback: sidecar routes through the pack worker."""

from __future__ import annotations

import concurrent.futures
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _config(**overrides):
    base = {"model_size": "small.en", "device": "cpu", "language": "en"}
    base.update(overrides)
    return SimpleNamespace(**base)


def _done_future(result=None, error=None):
    future: concurrent.futures.Future[dict] = concurrent.futures.Future()
    if error is not None:
        future.set_exception(error)
    else:
        future.set_result(result)
    return future


class _FakeLoadClient:
    def __init__(self, port=5123, future=None, refused=False):
        self._port = port
        self._future = future
        self._refused = refused
        self.calls: list = []

    @property
    def port(self):
        return self._port

    def request_load_whisper_model(self, model_size, device=None, language=None, timeout=None):
        self.calls.append((model_size, device, language))
        if self._refused:
            return None
        return self._future


def _patch_client(monkeypatch, client):
    import voice_typer.server.worker_client as client_mod

    monkeypatch.setattr(client_mod, "get_shared_client", lambda: client)


def _registry():
    from voice_typer.server.asr_registry import AsrBackendRegistry

    cfg = SimpleNamespace(
        asr_backend="whisper",
        model_size="small.en",
        device="cpu",
        language="en",
        beam_size=5,
        best_of=5,
        condition_on_previous_text=False,
        disabled_backends=[],
    )
    return AsrBackendRegistry(cfg)


class TestTryLoadWorkerWhisper:
    def test_success_returns_proxy_without_faster_whisper(self, monkeypatch):
        from voice_typer.server import system_whisper

        monkeypatch.delitem(sys.modules, "faster_whisper", raising=False)
        future = _done_future({"loaded": True, "backend": "whisper", "device_info": "cpu", "error": None})
        client = _FakeLoadClient(future=future)
        _patch_client(monkeypatch, client)
        engine = system_whisper.try_load_worker_whisper(_config())
        assert engine is not None
        assert engine.worker_backed is True
        assert engine.is_loaded is True
        assert engine.loaded_via == "worker/small.en"
        assert client.calls == [("small.en", "cpu", "en")]
        assert "faster_whisper" not in sys.modules

    def test_empty_model_size_returns_none_without_touching_client(self, monkeypatch):
        from voice_typer.server import system_whisper

        def _forbidden():
            raise AssertionError("client must not be consulted without a model_size")

        monkeypatch.setattr("voice_typer.server.worker_client.get_shared_client", _forbidden)
        assert system_whisper.try_load_worker_whisper(_config(model_size="")) is None

    def test_worker_down_returns_none(self, monkeypatch):
        from voice_typer.server import system_whisper

        _patch_client(monkeypatch, _FakeLoadClient(port=None))
        assert system_whisper.try_load_worker_whisper(_config()) is None

    def test_refused_future_returns_none(self, monkeypatch):
        from voice_typer.server import system_whisper

        _patch_client(monkeypatch, _FakeLoadClient(refused=True))
        assert system_whisper.try_load_worker_whisper(_config()) is None

    def test_load_refused_returns_none(self, monkeypatch):
        from voice_typer.server import system_whisper

        for result in (
            {"loaded": False, "backend": "whisper", "device_info": "", "error": "missing"},
            {"loaded": True, "backend": "whisper", "device_info": "cpu", "error": "boom"},
            {"text": "not a load result"},
            None,
        ):
            _patch_client(monkeypatch, _FakeLoadClient(future=_done_future(result)))
            assert system_whisper.try_load_worker_whisper(_config()) is None

    def test_timeout_and_error_return_none(self, monkeypatch):
        from voice_typer.server import system_whisper

        for error in (
            TimeoutError("slow"),
            concurrent.futures.CancelledError(),
            RuntimeError("hop down"),
        ):
            _patch_client(monkeypatch, _FakeLoadClient(future=_done_future(error=error)))
            assert system_whisper.try_load_worker_whisper(_config(), timeout=0.1) is None

    def test_client_lookup_failure_never_raises(self, monkeypatch):
        from voice_typer.server import system_whisper

        def _boom():
            raise RuntimeError("no client")

        monkeypatch.setattr("voice_typer.server.worker_client.get_shared_client", _boom)
        assert system_whisper.try_load_worker_whisper(_config()) is None


class _FakeSamplesClient:
    def __init__(self, port=5123, result=None, error=None, refused=False):
        self._port = port
        self._result = result
        self._error = error
        self._refused = refused
        self.requests: list = []
        self.abort_all_calls = 0

    @property
    def port(self):
        return self._port

    def request_samples(self, raw, rate, language, timeout=None):
        self.requests.append((bytes(raw), rate, language))
        if self._refused:
            return None
        return _done_future(self._result, self._error)

    def abort_all_outstanding(self):
        self.abort_all_calls += 1
        return 0


class TestProxyEngine:
    def test_transcribe_forwards_to_client(self):
        import numpy as np
        from voice_typer.server.system_whisper import WorkerWhisperProxyEngine

        client = _FakeSamplesClient(result={"text": "hello", "device_info": "cpu"})
        engine = WorkerWhisperProxyEngine(model_size="small.en", language="en", client=client)
        assert engine.transcribe_with_fallback(np.zeros(16000, dtype=np.float32)) == "hello"
        raw, rate, language = client.requests[0]
        assert rate == 16000
        assert language == "en"
        assert len(raw) == 16000 * 4

    def test_transcribe_error_raises(self):
        import numpy as np
        from voice_typer.server.worker_backed_asr import WorkerTranscriptionError

        client = _FakeSamplesClient(result={"text": "", "error": "worker blew up"})
        from voice_typer.server.system_whisper import WorkerWhisperProxyEngine

        with pytest.raises(WorkerTranscriptionError):
            WorkerWhisperProxyEngine(model_size="tiny", client=client).transcribe_with_fallback(
                np.zeros(100, dtype=np.float32)
            )

    def test_transcribe_without_worker_raises(self):
        import numpy as np
        from voice_typer.server.system_whisper import WorkerWhisperProxyEngine
        from voice_typer.server.worker_backed_asr import WorkerTranscriptionError

        client = _FakeSamplesClient(port=None)
        with pytest.raises(WorkerTranscriptionError):
            WorkerWhisperProxyEngine(model_size="tiny", client=client).transcribe_with_fallback(
                np.zeros(100, dtype=np.float32)
            )

    def test_refused_request_raises(self):
        import numpy as np
        from voice_typer.server.system_whisper import WorkerWhisperProxyEngine
        from voice_typer.server.worker_backed_asr import WorkerTranscriptionError

        client = _FakeSamplesClient(refused=True)
        with pytest.raises(WorkerTranscriptionError):
            WorkerWhisperProxyEngine(model_size="tiny", client=client).transcribe_with_fallback(
                np.zeros(100, dtype=np.float32)
            )

    def test_abort_propagates_unwrapped(self):
        import numpy as np
        from voice_typer.server.system_whisper import WorkerWhisperProxyEngine
        from voice_typer.server.worker_client import WorkerAbortedError

        client = _FakeSamplesClient(error=WorkerAbortedError("esc"))
        with pytest.raises(WorkerAbortedError):
            WorkerWhisperProxyEngine(model_size="tiny", client=client).transcribe_with_fallback(
                np.zeros(100, dtype=np.float32)
            )

    def test_lifecycle_and_abort(self):
        from voice_typer.server.system_whisper import WorkerWhisperProxyEngine

        client = _FakeSamplesClient()
        engine = WorkerWhisperProxyEngine(model_size="tiny", client=client)
        assert engine.load() is True
        assert engine.is_loaded is True
        engine.request_abort()
        engine.clear_abort()
        assert client.abort_all_calls == 1
        engine.unload()
        assert engine.is_loaded is False


class TestRegistryFallbackOrder:
    def test_worker_first_registers_proxy(self, monkeypatch):
        from voice_typer.server import system_whisper

        proxy = MagicMock()
        monkeypatch.setattr(system_whisper, "try_load_worker_whisper", lambda *a, **k: proxy)

        def _forbidden(*a, **k):
            raise AssertionError("legacy path must not run when the worker serves")

        monkeypatch.setattr(system_whisper, "try_load_system_whisper", _forbidden)
        registry = _registry()
        assert registry._try_system_whisper_fallback() is proxy
        assert registry.get("whisper") is proxy

    def test_worker_down_falls_to_legacy(self, monkeypatch):
        from voice_typer.server import system_whisper

        legacy = MagicMock()
        monkeypatch.setattr(system_whisper, "try_load_worker_whisper", lambda *a, **k: None)
        monkeypatch.setattr(system_whisper, "try_load_system_whisper", lambda *a, **k: legacy)
        registry = _registry()
        assert registry._try_system_whisper_fallback() is legacy
        assert registry.get("whisper") is legacy

    def test_worker_error_falls_to_legacy(self, monkeypatch):
        from voice_typer.server import system_whisper

        legacy = MagicMock()

        def _boom(*a, **k):
            raise RuntimeError("worker hop down")

        monkeypatch.setattr(system_whisper, "try_load_worker_whisper", _boom)
        monkeypatch.setattr(system_whisper, "try_load_system_whisper", lambda *a, **k: legacy)
        registry = _registry()
        assert registry._try_system_whisper_fallback() is legacy

    def test_both_unavailable_returns_none(self, monkeypatch):
        from voice_typer.server import system_whisper

        monkeypatch.setattr(system_whisper, "try_load_worker_whisper", lambda *a, **k: None)
        monkeypatch.setattr(system_whisper, "try_load_system_whisper", lambda *a, **k: None)
        assert _registry()._try_system_whisper_fallback() is None
