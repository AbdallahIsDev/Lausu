"""Worker-side load_parakeet_model / load_qwen_model commands + routing.

Mirrors the WL-1 whisper coverage (``test_worker_load_whisper_model.py``)
for the two ONNX backends: frame shapes, protocol routing, client
requests, transcriber load with stubbed engines (no real weights, C-TEST-8),
worker handlers, the sidecar worker-first try_load functions, the proxy
engines, and the registry worker-first routing with in-process fallback.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import sys
from types import SimpleNamespace

import pytest
from voice_typer.server.asr_errors import ModelNotDownloadedError
from voice_typer.server.worker_client import (
    WorkerClient,
    build_load_parakeet_frame,
    build_load_qwen_frame,
    route_frame,
)
from voice_typer.server.worker_protocol import (
    build_load_parakeet_frame as build_parakeet_direct,
    build_load_qwen_frame as build_qwen_direct,
)
from voice_typer.worker._transcribe import WorkerTranscriber
from voice_typer.worker._ws_commands import (
    _CommandHandles,
    handle_load_parakeet_model_async,
    handle_load_qwen_model_async,
)


class TestLoadFrame:
    def test_parakeet_shape(self):
        frame = json.loads(build_load_parakeet_frame("cpu", "en", 9))
        assert frame == {
            "cmd": "load_parakeet_model",
            "id": 9,
            "data": {"device": "cpu", "language": "en"},
        }

    def test_qwen_shape(self):
        frame = json.loads(build_load_qwen_frame("/models/qwen", None, "en", 5))
        assert frame == {
            "cmd": "load_qwen_model",
            "id": 5,
            "data": {"model_path": "/models/qwen", "device": None, "language": "en"},
        }

    def test_is_str_with_numeric_id(self):
        for raw in (build_load_parakeet_frame(None, None, 3), build_load_qwen_frame("/m", "cpu", None, 4)):
            assert isinstance(raw, str)
            assert isinstance(json.loads(raw)["id"], int)

    def test_facade_reexport_matches_protocol(self):
        assert build_parakeet_direct(None, "en", 1) == build_load_parakeet_frame(None, "en", 1)
        assert build_qwen_direct("/m", None, None, 1) == build_load_qwen_frame("/m", None, None, 1)


class TestLoadRoute:
    def test_parakeet_resolves_future_without_publish(self):
        published: list = []
        seen: list = []
        frame = {
            "type": "load_parakeet_model_result",
            "id": 11,
            "data": {"loaded": True, "backend": "parakeet", "device_info": "CPU", "error": None},
        }
        assert route_frame(frame, published.append, lambda i, r: seen.append((i, r))) == "load_result"
        assert seen == [(11, {"loaded": True, "backend": "parakeet", "device_info": "CPU", "error": None})]
        assert published == []

    def test_qwen_resolves_future_without_publish(self):
        published: list = []
        seen: list = []
        frame = {
            "type": "load_qwen_model_result",
            "id": 7,
            "data": {"loaded": True, "backend": "qwen", "device_info": "CPU", "error": None},
        }
        assert route_frame(frame, published.append, lambda i, r: seen.append((i, r))) == "load_result"
        assert seen == [(7, {"loaded": True, "backend": "qwen", "device_info": "CPU", "error": None})]
        assert published == []

    def test_backend_default_from_frame_type(self):
        for ftype, backend in (
            ("load_parakeet_model_result", "parakeet"),
            ("load_qwen_model_result", "qwen"),
        ):
            seen: list = []

            def _record(i, r, _seen=seen):
                _seen.append(r)

            frame = {"type": ftype, "id": 3, "data": {"loaded": True}}
            assert route_frame(frame, lambda _m: None, _record) == "load_result"
            assert seen[0]["backend"] == backend

    def test_non_numeric_id_skips_resolver(self):
        for frame in (
            {"type": "load_parakeet_model_result", "data": {"loaded": True}},
            {"type": "load_qwen_model_result", "id": "11", "data": {"loaded": True}},
            {"type": "load_qwen_model_result", "id": True, "data": {"loaded": True}},
        ):
            seen: list = []

            def _record(i, r, _seen=seen):
                _seen.append((i, r))

            assert route_frame(frame, lambda _m: None, _record) == "load_result"
            assert seen == []

    def test_resolver_failure_still_returns(self):
        def _boom(_i, _r):
            raise RuntimeError("bad resolver")

        for ftype in ("load_parakeet_model_result", "load_qwen_model_result"):
            frame = {"type": ftype, "id": 5, "data": {"loaded": False}}
            assert route_frame(frame, lambda _m: None, _boom) == "load_result"


class TestRequestLoad:
    def test_no_port_returns_none(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            assert client.request_load_parakeet_model() is None
            assert client.request_load_qwen_model("/m") is None
            assert client._resolvers == {}
        finally:
            client.close()

    def test_port_set_returns_future_and_queues_frame(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            client._port = 5123
            future = client.request_load_parakeet_model("cpu", "en")
            assert isinstance(future, concurrent.futures.Future)
            assert not future.done()
            frame = json.loads(client._outbound.get_nowait())
            assert frame["cmd"] == "load_parakeet_model"
            assert frame["id"] == 1
            assert frame["data"] == {"device": "cpu", "language": "en"}

            future = client.request_load_qwen_model("/models/qwen", None, "en")
            assert isinstance(future, concurrent.futures.Future)
            frame = json.loads(client._outbound.get_nowait())
            assert frame["cmd"] == "load_qwen_model"
            assert frame["id"] == 2
            assert frame["data"] == {"model_path": "/models/qwen", "device": None, "language": "en"}
        finally:
            client.close()


class _StubConfig:
    """Config stub whose load() returns an isolated namespace (no disk)."""

    @classmethod
    def load(cls):
        return SimpleNamespace(device="cpu", language="en", qwen_model_path="/models/qwen")


class _StubParakeetEngine:
    instances: list = []

    def __init__(self, device="auto", language=None, config=None, fail=None):
        self.device = device
        self.language = language
        self.config = config
        self.fail = fail
        type(self).instances.append(self)
        self._model = object()

    @property
    def is_loaded(self):
        return self._model is not None

    @property
    def device_info(self):
        return "CPU"

    def load(self):
        if self.fail is not None:
            raise self.fail
        return True

    def unload(self):
        self._model = None


class _StubQwenEngine:
    instances: list = []

    def __init__(self, model_path=None, device="auto", language=None, config=None, fail=None):
        self.model_path = model_path
        self.device = device
        self.language = language
        self.config = config
        self.fail = fail
        type(self).instances.append(self)
        self._model = object()

    @property
    def is_loaded(self):
        return self._model is not None

    @property
    def device_info(self):
        return "CPU"

    def load(self):
        if self.fail is not None:
            raise self.fail
        return True

    def unload(self):
        self._model = None


def _patch_config(monkeypatch):
    import voice_typer.server.config as config_mod

    monkeypatch.setattr(config_mod, "Config", _StubConfig)


class TestTranscriberLoadParakeet:
    def test_success_caches_engine(self, monkeypatch):
        import voice_typer.server.parakeet_engine as parakeet_mod

        _StubParakeetEngine.instances.clear()
        _patch_config(monkeypatch)
        monkeypatch.setattr(parakeet_mod, "ParakeetEngine", _StubParakeetEngine)
        transcriber = WorkerTranscriber()
        result = transcriber.load_parakeet_model(None, "en")
        assert result == {"loaded": True, "backend": "parakeet", "device_info": "CPU", "error": None}
        assert transcriber._engine is _StubParakeetEngine.instances[-1]
        assert transcriber._engine_language == "en"
        assert transcriber._engine_backend == "parakeet"

    def test_cached_engine_short_circuits(self, monkeypatch):
        import voice_typer.server.parakeet_engine as parakeet_mod

        _patch_config(monkeypatch)
        cached = _StubParakeetEngine()
        transcriber = WorkerTranscriber()
        transcriber._engine = cached
        transcriber._engine_language = "en"
        transcriber._engine_backend = "parakeet"

        def _forbidden(*_a, **_k):
            raise AssertionError("must use cache")

        monkeypatch.setattr(parakeet_mod, "ParakeetEngine", _forbidden)
        result = transcriber.load_parakeet_model(None, "en")
        assert result["loaded"] is True
        assert result["error"] is None
        assert transcriber._engine is cached

    def test_wrong_backend_rebuilds(self, monkeypatch):
        import voice_typer.server.parakeet_engine as parakeet_mod

        _patch_config(monkeypatch)
        _StubParakeetEngine.instances.clear()
        monkeypatch.setattr(parakeet_mod, "ParakeetEngine", _StubParakeetEngine)
        transcriber = WorkerTranscriber()
        transcriber._engine = _StubParakeetEngine()
        transcriber._engine_language = "en"
        transcriber._engine_backend = "qwen"
        result = transcriber.load_parakeet_model(None, "en")
        assert result["loaded"] is True
        assert transcriber._engine_backend == "parakeet"

    def test_load_false_is_error(self, monkeypatch):
        import voice_typer.server.parakeet_engine as parakeet_mod

        class _Refusing(_StubParakeetEngine):
            def load(self):
                return False

        _patch_config(monkeypatch)
        monkeypatch.setattr(parakeet_mod, "ParakeetEngine", _Refusing)
        result = WorkerTranscriber().load_parakeet_model(None, "en")
        assert result["loaded"] is False
        assert result["backend"] == "parakeet"
        assert "load failed" in str(result["error"])

    def test_missing_model_never_raises(self, monkeypatch):
        import voice_typer.server.parakeet_engine as parakeet_mod

        class _Missing(_StubParakeetEngine):
            def load(self):
                raise ModelNotDownloadedError("not downloaded", model_size="parakeet", backend="parakeet")

        _patch_config(monkeypatch)
        monkeypatch.setattr(parakeet_mod, "ParakeetEngine", _Missing)
        result = WorkerTranscriber().load_parakeet_model()
        assert result["loaded"] is False
        assert "not downloaded" in str(result["error"])

    def test_runtime_error_never_raises(self, monkeypatch):
        import voice_typer.server.parakeet_engine as parakeet_mod

        class _Broken(_StubParakeetEngine):
            def load(self):
                raise RuntimeError("gpu gone")

        _patch_config(monkeypatch)
        monkeypatch.setattr(parakeet_mod, "ParakeetEngine", _Broken)
        result = WorkerTranscriber().load_parakeet_model("cuda")
        assert result["loaded"] is False
        assert "gpu gone" in str(result["error"])


class TestTranscriberLoadQwen:
    def test_success_caches_engine(self, monkeypatch):
        import voice_typer.server.qwen_engine as qwen_mod

        _StubQwenEngine.instances.clear()
        _patch_config(monkeypatch)
        monkeypatch.setattr(qwen_mod, "QwenEngine", _StubQwenEngine)
        transcriber = WorkerTranscriber()
        result = transcriber.load_qwen_model("/models/qwen", None, "en")
        assert result == {"loaded": True, "backend": "qwen", "device_info": "CPU", "error": None}
        assert transcriber._engine is _StubQwenEngine.instances[-1]
        assert transcriber._engine.model_path == "/models/qwen"
        assert transcriber._engine_backend == "qwen"

    def test_cached_engine_short_circuits_same_path(self, monkeypatch):
        import voice_typer.server.qwen_engine as qwen_mod

        _patch_config(monkeypatch)
        cached = _StubQwenEngine(model_path="/models/qwen")
        transcriber = WorkerTranscriber()
        transcriber._engine = cached
        transcriber._engine_language = "en"
        transcriber._engine_backend = "qwen"

        def _forbidden(*_a, **_k):
            raise AssertionError("must use cache")

        monkeypatch.setattr(qwen_mod, "QwenEngine", _forbidden)
        result = transcriber.load_qwen_model("/models/qwen", None, "en")
        assert result["loaded"] is True
        assert transcriber._engine is cached

    def test_different_path_rebuilds(self, monkeypatch):
        import voice_typer.server.qwen_engine as qwen_mod

        _patch_config(monkeypatch)
        _StubQwenEngine.instances.clear()
        monkeypatch.setattr(qwen_mod, "QwenEngine", _StubQwenEngine)
        transcriber = WorkerTranscriber()
        transcriber._engine = _StubQwenEngine(model_path="/models/qwen")
        transcriber._engine_language = "en"
        transcriber._engine_backend = "qwen"
        result = transcriber.load_qwen_model("/models/other", None, "en")
        assert result["loaded"] is True
        assert transcriber._engine.model_path == "/models/other"

    def test_load_false_is_error(self, monkeypatch):
        import voice_typer.server.qwen_engine as qwen_mod

        class _Refusing(_StubQwenEngine):
            def load(self):
                return False

        _patch_config(monkeypatch)
        monkeypatch.setattr(qwen_mod, "QwenEngine", _Refusing)
        result = WorkerTranscriber().load_qwen_model("/models/qwen")
        assert result["loaded"] is False
        assert result["backend"] == "qwen"
        assert "load failed" in str(result["error"])

    def test_runtime_error_never_raises(self, monkeypatch):
        import voice_typer.server.qwen_engine as qwen_mod

        class _Broken(_StubQwenEngine):
            def load(self):
                raise RuntimeError("onnx session died")

        _patch_config(monkeypatch)
        monkeypatch.setattr(qwen_mod, "QwenEngine", _Broken)
        result = WorkerTranscriber().load_qwen_model("/models/qwen")
        assert result["loaded"] is False
        assert "onnx session died" in str(result["error"])


class _FakeWS:
    def __init__(self):
        self.sent: list = []

    async def send(self, payload):
        self.sent.append(payload)


def _handles(ws):
    async def _complete(_fn, _rid):
        raise AssertionError("load path must not use the transcribe tail")

    def _launch(_fn, _rid):
        raise AssertionError("load path must not use the transcribe tail")

    return _CommandHandles(
        websocket=ws, samples={}, aborted=set(), streams={}, complete=_complete, launch=_launch
    )


async def _wait_sent(ws, count=1):
    for _ in range(100):
        if len(ws.sent) == count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"expected {count} frame(s), got {len(ws.sent)}")


class TestHandler:
    async def test_invalid_id_sends_nothing(self):
        ws = _FakeWS()
        await handle_load_parakeet_model_async({"cmd": "load_parakeet_model", "data": {}}, _handles(ws))
        await handle_load_qwen_model_async({"cmd": "load_qwen_model", "data": {}}, _handles(ws))
        assert ws.sent == []

    async def test_qwen_missing_model_path_sends_error(self):
        ws = _FakeWS()
        await handle_load_qwen_model_async({"cmd": "load_qwen_model", "id": 4, "data": {}}, _handles(ws))
        await _wait_sent(ws)
        frame = json.loads(ws.sent[0])
        assert frame["type"] == "load_qwen_model_result"
        assert frame["id"] == 4
        assert frame["data"]["loaded"] is False
        assert frame["data"]["backend"] == "qwen"
        assert frame["data"]["error"] is not None

    async def test_parakeet_valid_request_sends_result(self, monkeypatch):
        import voice_typer.worker._transcribe as transcribe_mod

        ws = _FakeWS()
        calls: list = []

        class _FakeTranscriber:
            def load_parakeet_model(self, device=None, language=None):
                calls.append((device, language))
                return {"loaded": True, "backend": "parakeet", "device_info": "CPU", "error": None}

        monkeypatch.setattr(transcribe_mod, "get_transcriber", lambda: _FakeTranscriber())
        await handle_load_parakeet_model_async(
            {"cmd": "load_parakeet_model", "id": 7, "data": {"device": "cpu", "language": "en"}},
            _handles(ws),
        )
        await _wait_sent(ws)
        frame = json.loads(ws.sent[0])
        assert frame == {
            "type": "load_parakeet_model_result",
            "id": 7,
            "data": {"loaded": True, "backend": "parakeet", "device_info": "CPU", "error": None},
        }
        assert calls == [("cpu", "en")]

    async def test_qwen_valid_request_sends_result(self, monkeypatch):
        import voice_typer.worker._transcribe as transcribe_mod

        ws = _FakeWS()
        calls: list = []

        class _FakeTranscriber:
            def load_qwen_model(self, model_path, device=None, language=None):
                calls.append((model_path, device, language))
                return {"loaded": True, "backend": "qwen", "device_info": "CPU", "error": None}

        monkeypatch.setattr(transcribe_mod, "get_transcriber", lambda: _FakeTranscriber())
        await handle_load_qwen_model_async(
            {
                "cmd": "load_qwen_model",
                "id": 8,
                "data": {"model_path": "/models/qwen", "device": None, "language": "en"},
            },
            _handles(ws),
        )
        await _wait_sent(ws)
        frame = json.loads(ws.sent[0])
        assert frame == {
            "type": "load_qwen_model_result",
            "id": 8,
            "data": {"loaded": True, "backend": "qwen", "device_info": "CPU", "error": None},
        }
        assert calls == [("/models/qwen", None, "en")]

    async def test_thread_raise_still_resolves(self, monkeypatch):
        import voice_typer.worker._transcribe as transcribe_mod

        ws = _FakeWS()

        class _Boom:
            def load_parakeet_model(self, device=None, language=None):
                raise RuntimeError("engine exploded")

        monkeypatch.setattr(transcribe_mod, "get_transcriber", lambda: _Boom())
        await handle_load_parakeet_model_async(
            {"cmd": "load_parakeet_model", "id": 9, "data": {}}, _handles(ws)
        )
        await _wait_sent(ws)
        frame = json.loads(ws.sent[0])
        assert frame["type"] == "load_parakeet_model_result"
        assert frame["id"] == 9
        assert frame["data"]["loaded"] is False
        assert "engine exploded" in str(frame["data"]["error"])


def _config(**overrides):
    base = {"model_size": "small.en", "device": "cpu", "language": "en", "qwen_model_path": "/models/qwen"}
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
        self.parakeet_calls: list = []
        self.qwen_calls: list = []

    @property
    def port(self):
        return self._port

    def request_load_parakeet_model(self, device=None, language=None, timeout=None):
        self.parakeet_calls.append((device, language))
        if self._refused:
            return None
        return self._future

    def request_load_qwen_model(self, model_path, device=None, language=None, timeout=None):
        self.qwen_calls.append((model_path, device, language))
        if self._refused:
            return None
        return self._future


def _patch_client(monkeypatch, client):
    import voice_typer.server.worker_client as client_mod

    monkeypatch.setattr(client_mod, "get_shared_client", lambda: client)


class TestTryLoadWorkerParakeet:
    def test_success_returns_proxy(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        monkeypatch.delitem(sys.modules, "onnx_asr", raising=False)
        future = _done_future({"loaded": True, "backend": "parakeet", "device_info": "CPU", "error": None})
        client = _FakeLoadClient(future=future)
        _patch_client(monkeypatch, client)
        engine = worker_proxy_asr.try_load_worker_parakeet(_config())
        assert engine is not None
        assert engine.worker_backed is True
        assert engine.is_loaded is True
        assert engine.loaded_via == "worker/parakeet"
        assert client.parakeet_calls == [("cpu", "en")]
        assert "onnx_asr" not in sys.modules

    def test_worker_down_returns_none(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        _patch_client(monkeypatch, _FakeLoadClient(port=None))
        assert worker_proxy_asr.try_load_worker_parakeet(_config()) is None

    def test_refused_future_returns_none(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        _patch_client(monkeypatch, _FakeLoadClient(refused=True))
        assert worker_proxy_asr.try_load_worker_parakeet(_config()) is None

    def test_load_refused_returns_none(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        for result in (
            {"loaded": False, "backend": "parakeet", "device_info": "", "error": "missing"},
            {"loaded": True, "backend": "parakeet", "device_info": "CPU", "error": "boom"},
            {"text": "not a load result"},
            None,
        ):
            _patch_client(monkeypatch, _FakeLoadClient(future=_done_future(result)))
            assert worker_proxy_asr.try_load_worker_parakeet(_config()) is None

    def test_timeout_and_error_return_none(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        for error in (
            TimeoutError("slow"),
            concurrent.futures.CancelledError(),
            RuntimeError("hop down"),
        ):
            _patch_client(monkeypatch, _FakeLoadClient(future=_done_future(error=error)))
            assert worker_proxy_asr.try_load_worker_parakeet(_config(), timeout=0.1) is None

    def test_client_lookup_failure_never_raises(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        def _boom():
            raise RuntimeError("no client")

        monkeypatch.setattr("voice_typer.server.worker_client.get_shared_client", _boom)
        assert worker_proxy_asr.try_load_worker_parakeet(_config()) is None


class TestTryLoadWorkerQwen:
    def test_success_returns_proxy(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        future = _done_future({"loaded": True, "backend": "qwen", "device_info": "CPU", "error": None})
        client = _FakeLoadClient(future=future)
        _patch_client(monkeypatch, client)
        engine = worker_proxy_asr.try_load_worker_qwen(_config())
        assert engine is not None
        assert engine.worker_backed is True
        assert engine.is_loaded is True
        assert engine.loaded_via == "worker/qwen"
        assert client.qwen_calls == [("/models/qwen", "cpu", "en")]

    def test_empty_model_path_skips_client(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        def _forbidden():
            raise AssertionError("client must not be consulted without a model path")

        monkeypatch.setattr("voice_typer.server.worker_client.get_shared_client", _forbidden)
        assert worker_proxy_asr.try_load_worker_qwen(_config(qwen_model_path="")) is None
        assert worker_proxy_asr.try_load_worker_qwen(_config(qwen_model_path=None)) is None

    def test_worker_down_returns_none(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        _patch_client(monkeypatch, _FakeLoadClient(port=None))
        assert worker_proxy_asr.try_load_worker_qwen(_config()) is None

    def test_refused_future_returns_none(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        _patch_client(monkeypatch, _FakeLoadClient(refused=True))
        assert worker_proxy_asr.try_load_worker_qwen(_config()) is None

    def test_load_refused_returns_none(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        for result in (
            {"loaded": False, "backend": "qwen", "device_info": "", "error": "missing"},
            {"loaded": True, "backend": "qwen", "device_info": "CPU", "error": "boom"},
            {"text": "not a load result"},
            None,
        ):
            _patch_client(monkeypatch, _FakeLoadClient(future=_done_future(result)))
            assert worker_proxy_asr.try_load_worker_qwen(_config()) is None

    def test_timeout_and_error_return_none(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        for error in (
            TimeoutError("slow"),
            concurrent.futures.CancelledError(),
            RuntimeError("hop down"),
        ):
            _patch_client(monkeypatch, _FakeLoadClient(future=_done_future(error=error)))
            assert worker_proxy_asr.try_load_worker_qwen(_config(), timeout=0.1) is None


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
        from voice_typer.server.worker_proxy_asr import WorkerParakeetProxyEngine, WorkerQwenProxyEngine

        for engine_cls, kwargs in (
            (WorkerParakeetProxyEngine, {}),
            (WorkerQwenProxyEngine, {"model_path": "/models/qwen"}),
        ):
            client = _FakeSamplesClient(result={"text": "hello", "device_info": "CPU"})
            engine = engine_cls(language="en", client=client, **kwargs)
            assert engine.transcribe_with_fallback(np.zeros(16000, dtype=np.float32)) == "hello"
            raw, rate, language = client.requests[0]
            assert rate == 16000
            assert language == "en"
            assert len(raw) == 16000 * 4

    def test_transcribe_error_raises(self):
        import numpy as np
        from voice_typer.server.worker_backed_asr import WorkerTranscriptionError
        from voice_typer.server.worker_proxy_asr import WorkerParakeetProxyEngine

        client = _FakeSamplesClient(result={"text": "", "error": "worker blew up"})
        with pytest.raises(WorkerTranscriptionError):
            WorkerParakeetProxyEngine(client=client).transcribe_with_fallback(np.zeros(100, dtype=np.float32))

    def test_transcribe_without_worker_raises(self):
        import numpy as np
        from voice_typer.server.worker_backed_asr import WorkerTranscriptionError
        from voice_typer.server.worker_proxy_asr import WorkerQwenProxyEngine

        client = _FakeSamplesClient(port=None)
        with pytest.raises(WorkerTranscriptionError):
            WorkerQwenProxyEngine(client=client).transcribe_with_fallback(np.zeros(100, dtype=np.float32))

    def test_refused_request_raises(self):
        import numpy as np
        from voice_typer.server.worker_backed_asr import WorkerTranscriptionError
        from voice_typer.server.worker_proxy_asr import WorkerParakeetProxyEngine

        client = _FakeSamplesClient(refused=True)
        with pytest.raises(WorkerTranscriptionError):
            WorkerParakeetProxyEngine(client=client).transcribe_with_fallback(np.zeros(100, dtype=np.float32))

    def test_abort_propagates_unwrapped(self):
        import numpy as np
        from voice_typer.server.worker_client import WorkerAbortedError
        from voice_typer.server.worker_proxy_asr import WorkerQwenProxyEngine

        client = _FakeSamplesClient(error=WorkerAbortedError("esc"))
        with pytest.raises(WorkerAbortedError):
            WorkerQwenProxyEngine(client=client).transcribe_with_fallback(np.zeros(100, dtype=np.float32))

    def test_lifecycle_and_abort(self):
        from voice_typer.server.worker_proxy_asr import WorkerParakeetProxyEngine

        client = _FakeSamplesClient()
        engine = WorkerParakeetProxyEngine(client=client)
        assert engine.load() is True
        assert engine.is_loaded is True
        engine.request_abort()
        engine.clear_abort()
        assert client.abort_all_calls == 1
        engine.unload()
        assert engine.is_loaded is False


class _StubEngine:
    """In-process fake registering the parakeet/qwen fallback leaf."""

    def __init__(self):
        self._loaded = False

    @property
    def is_loaded(self):
        return self._loaded

    @property
    def device_info(self):
        return "CPU"

    @property
    def loaded_via(self):
        return "stub"

    def load(self, *, progress_callback=None, **kwargs):
        self._loaded = True
        return True

    def unload(self):
        self._loaded = False

    def clear_abort(self):
        pass

    def request_abort(self):
        pass

    def transcribe_with_fallback(self, audio, *args, **kwargs):
        return "in-process"


def _registry(backend="parakeet", **overrides):
    from voice_typer.server.asr_registry import AsrBackendRegistry

    cfg = SimpleNamespace(
        asr_backend=backend,
        model_size="small.en",
        device="cpu",
        language="en",
        beam_size=5,
        best_of=5,
        condition_on_previous_text=False,
        disabled_backends=[],
        qwen_model_path="/models/qwen",
    )
    for key, value in overrides.items():
        setattr(cfg, key, value)
    registry = AsrBackendRegistry(cfg)
    registry.register(backend, _StubEngine())
    return registry


class TestRegistryWorkerFirst:
    def test_parakeet_worker_first_registers_proxy(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        proxy = object.__new__(worker_proxy_asr.WorkerParakeetProxyEngine)
        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_parakeet", lambda *a, **k: proxy)

        def _forbidden(*a, **k):
            raise AssertionError("in-process load must not run when the worker serves")

        registry = _registry("parakeet")
        import voice_typer.server.asr.registry as registry_core

        monkeypatch.setattr(registry_core.RegistryCore, "_attempt_load", _forbidden)
        assert registry.load_with_fallback(progress_callback=lambda msg: None) is proxy
        assert registry.get("parakeet") is proxy

    def test_qwen_worker_first_registers_proxy(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        proxy = object.__new__(worker_proxy_asr.WorkerQwenProxyEngine)
        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_qwen", lambda *a, **k: proxy)

        def _forbidden(*a, **k):
            raise AssertionError("in-process load must not run when the worker serves")

        registry = _registry("qwen")
        import voice_typer.server.asr.registry as registry_core

        monkeypatch.setattr(registry_core.RegistryCore, "_attempt_load", _forbidden)
        assert registry.load_with_fallback(progress_callback=lambda msg: None) is proxy
        assert registry.get("qwen") is proxy

    def test_worker_down_falls_to_in_process(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_parakeet", lambda *a, **k: None)
        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_qwen", lambda *a, **k: None)
        for backend in ("parakeet", "qwen"):
            registry = _registry(backend)
            engine = registry.load_with_fallback(progress_callback=lambda msg: None)
            assert isinstance(engine, _StubEngine)
            assert engine.is_loaded is True

    def test_worker_error_falls_to_in_process(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        def _boom(*a, **k):
            raise RuntimeError("worker hop down")

        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_parakeet", _boom)
        registry = _registry("parakeet")
        engine = registry.load_with_fallback(progress_callback=lambda msg: None)
        assert isinstance(engine, _StubEngine)

    def test_disabled_backend_skips_worker(self, monkeypatch):
        def _forbidden(*a, **k):
            raise AssertionError("disabled backend must not consult the worker")

        from voice_typer.server import worker_proxy_asr

        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_parakeet", _forbidden)
        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_qwen", _forbidden)
        # disabled → whisper fallback path (never returns the stub): a None
        # whisper (no whisper registered) yields None overall, proving no
        # worker consultation happened.
        registry = _registry("parakeet", disabled_backends=["parakeet"])
        assert registry.load_with_fallback(progress_callback=lambda msg: None) is None

    def test_whisper_primary_never_consults_onnx_hook(self):
        registry = _registry("parakeet")
        assert registry._try_worker_backend_fallback("whisper") is None
        assert registry._try_worker_backend_fallback("cloud") is None

    def test_load_active_worker_first_returns_proxy(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        proxy = object.__new__(worker_proxy_asr.WorkerParakeetProxyEngine)
        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_parakeet", lambda *a, **k: proxy)
        registry = _registry("parakeet")
        engine = registry.load_active(progress_callback=lambda msg: None)
        assert engine is proxy
        assert registry.get("parakeet") is proxy

    def test_load_active_worker_down_loads_in_process(self, monkeypatch):
        from voice_typer.server import worker_proxy_asr

        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_parakeet", lambda *a, **k: None)
        monkeypatch.setattr(worker_proxy_asr, "try_load_worker_qwen", lambda *a, **k: None)
        for backend in ("parakeet", "qwen"):
            registry = _registry(backend)
            engine = registry.load_active(progress_callback=lambda msg: None)
            assert isinstance(engine, _StubEngine)
            assert engine.is_loaded is True
