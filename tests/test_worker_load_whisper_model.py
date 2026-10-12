"""WL-1 Round A: worker-side load_whisper_model WS command + protocol."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json

from voice_typer.server.asr_errors import ModelNotDownloadedError
from voice_typer.server.worker_client import WorkerClient, build_load_whisper_frame, route_frame
from voice_typer.server.worker_protocol import build_load_whisper_frame as build_frame_direct
from voice_typer.worker._transcribe import WorkerTranscriber
from voice_typer.worker._ws_commands import _CommandHandles, handle_load_whisper_model_async


class TestLoadFrame:
    def test_shape(self):
        frame = json.loads(build_load_whisper_frame("small.en", None, "en", 9))
        assert frame == {
            "cmd": "load_whisper_model",
            "id": 9,
            "data": {"model_size": "small.en", "device": None, "language": "en"},
        }

    def test_is_str_with_numeric_id(self):
        raw = build_load_whisper_frame("tiny", "cpu", None, 3)
        assert isinstance(raw, str)
        assert isinstance(json.loads(raw)["id"], int)

    def test_facade_reexport_matches_protocol(self):
        assert build_frame_direct("a", None, None, 1) == build_load_whisper_frame("a", None, None, 1)


class TestLoadRoute:
    def test_resolves_future_without_publish(self):
        published: list = []
        seen: list = []
        frame = {
            "type": "load_whisper_model_result",
            "id": 11,
            "data": {"loaded": True, "backend": "whisper", "device_info": "cpu (int8)", "error": None},
        }
        assert route_frame(frame, published.append, lambda i, r: seen.append((i, r))) == "load_result"
        assert seen == [
            (11, {"loaded": True, "backend": "whisper", "device_info": "cpu (int8)", "error": None})
        ]
        assert published == []

    def test_non_numeric_id_skips_resolver(self):
        for frame in (
            {"type": "load_whisper_model_result", "data": {"loaded": True}},
            {"type": "load_whisper_model_result", "id": "11", "data": {"loaded": True}},
            {"type": "load_whisper_model_result", "id": True, "data": {"loaded": True}},
        ):
            seen: list = []

            def _record(i, r, _seen=seen):
                _seen.append((i, r))

            assert route_frame(frame, lambda _m: None, _record) == "load_result"
            assert seen == []

    def test_resolver_failure_still_returns(self):
        def _boom(_i, _r):
            raise RuntimeError("bad resolver")

        frame = {"type": "load_whisper_model_result", "id": 5, "data": {"loaded": False}}
        assert route_frame(frame, lambda _m: None, _boom) == "load_result"


class TestRequestLoad:
    def test_no_port_returns_none(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            assert client.request_load_whisper_model("small.en") is None
            assert client._resolvers == {}
        finally:
            client.close()

    def test_port_set_returns_future_and_queues_frame(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            client._port = 5123
            future = client.request_load_whisper_model("small.en", None, "en")
            assert isinstance(future, concurrent.futures.Future)
            assert not future.done()
            frame = json.loads(client._outbound.get_nowait())
            assert frame["cmd"] == "load_whisper_model"
            assert frame["id"] == 1
            assert frame["data"] == {"model_size": "small.en", "device": None, "language": "en"}
        finally:
            client.close()


class _StubEngine:
    instances: list = []

    def __init__(self, model_size="small.en", device="auto", language="en", fail=None):
        self.model_size = model_size
        self._device = device
        self.fail = fail
        type(self).instances.append(self)
        self._model = object()

    @property
    def is_loaded(self):
        return self._model is not None

    @property
    def device_info(self):
        return "cpu (int8)"

    def load(self):
        if self.fail is not None:
            raise self.fail


class TestTranscriberLoad:
    def test_success_caches_engine(self, monkeypatch):
        import voice_typer.worker.whisper.engine as engine_mod

        _StubEngine.instances.clear()
        monkeypatch.setattr(engine_mod, "TranscriptionEngine", _StubEngine)
        transcriber = WorkerTranscriber()
        result = transcriber.load_whisper_model("small.en", None, "en")
        assert result == {"loaded": True, "backend": "whisper", "device_info": "cpu (int8)", "error": None}
        assert transcriber._engine is _StubEngine.instances[-1]
        assert transcriber._engine_language == "en"

    def test_cached_engine_short_circuits(self, monkeypatch):
        import voice_typer.worker.whisper.engine as engine_mod

        cached = _StubEngine(model_size="small.en")
        transcriber = WorkerTranscriber()
        transcriber._engine = cached
        transcriber._engine_language = "en"

        def _forbidden(*_a, **_k):
            raise AssertionError("must use cache")

        monkeypatch.setattr(engine_mod, "TranscriptionEngine", _forbidden)
        result = transcriber.load_whisper_model("small.en", None, "en")
        assert result["loaded"] is True
        assert result["error"] is None
        assert transcriber._engine is cached

    def test_missing_model_returns_error(self, monkeypatch):
        import voice_typer.worker.whisper.engine as engine_mod

        class _Missing(_StubEngine):
            def load(self):
                raise ModelNotDownloadedError("not downloaded")

        monkeypatch.setattr(engine_mod, "TranscriptionEngine", _Missing)
        result = WorkerTranscriber().load_whisper_model("tiny", None, None)
        assert result["loaded"] is False
        assert result["backend"] == "whisper"
        assert "not downloaded" in str(result["error"])

    def test_runtime_error_never_raises(self, monkeypatch):
        import voice_typer.worker.whisper.engine as engine_mod

        class _Broken(_StubEngine):
            def load(self):
                raise RuntimeError("gpu gone")

        monkeypatch.setattr(engine_mod, "TranscriptionEngine", _Broken)
        result = WorkerTranscriber().load_whisper_model("small.en")
        assert result["loaded"] is False
        assert "gpu gone" in str(result["error"])


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


class TestHandler:
    async def test_invalid_id_sends_nothing(self):
        ws = _FakeWS()
        await handle_load_whisper_model_async({"cmd": "load_whisper_model", "data": {}}, _handles(ws))
        assert ws.sent == []

    async def test_missing_model_size_sends_error(self):
        ws = _FakeWS()
        await handle_load_whisper_model_async(
            {"cmd": "load_whisper_model", "id": 4, "data": {}}, _handles(ws)
        )
        assert len(ws.sent) == 1
        frame = json.loads(ws.sent[0])
        assert frame["type"] == "load_whisper_model_result"
        assert frame["id"] == 4
        assert frame["data"]["loaded"] is False
        assert frame["data"]["error"] is not None

    async def test_valid_request_sends_result(self, monkeypatch):
        import voice_typer.worker._ws_commands as commands_mod

        ws = _FakeWS()
        calls: list = []

        class _FakeTranscriber:
            def load_whisper_model(self, model_size, device=None, language=None):
                calls.append((model_size, device, language))
                return {"loaded": True, "backend": "whisper", "device_info": "cpu (int8)", "error": None}

        monkeypatch.setattr(
            commands_mod, "get_transcriber", lambda: _FakeTranscriber(), raising=False
        )
        import voice_typer.worker._transcribe as transcribe_mod

        monkeypatch.setattr(transcribe_mod, "get_transcriber", lambda: _FakeTranscriber())
        await handle_load_whisper_model_async(
            {
                "cmd": "load_whisper_model",
                "id": 7,
                "data": {"model_size": "small.en", "device": None, "language": "en"},
            },
            _handles(ws),
        )
        for _ in range(100):
            if ws.sent:
                break
            await asyncio.sleep(0.01)
        assert len(ws.sent) == 1
        frame = json.loads(ws.sent[0])
        assert frame == {
            "type": "load_whisper_model_result",
            "id": 7,
            "data": {"loaded": True, "backend": "whisper", "device_info": "cpu (int8)", "error": None},
        }
        assert calls == [("small.en", None, "en")]
