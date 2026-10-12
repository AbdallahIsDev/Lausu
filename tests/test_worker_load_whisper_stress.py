"""WL-1 Round A stress/robustness probe for load_whisper_model (no fixes here).

Mocked heavy deps throughout: no real weights, stub TranscriptionEngine.
Targets the Round A diff: worker_protocol.build_load_whisper_frame +
route load_whisper_model_result, worker_client.request_load_whisper_model,
WorkerTranscriber.load_whisper_model, worker handle_load_whisper_model_async.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import queue

import pytest
from voice_typer.server.worker_client import _OUTBOUND_QUEUE_MAX, WorkerClient, route_frame
from voice_typer.server.worker_protocol import parse_incoming
from voice_typer.worker._transcribe import WorkerTranscriber
from voice_typer.worker._ws_commands import _CommandHandles, handle_load_whisper_model_async


class _StubEngine:
    constructions = 0
    loads = 0

    def __init__(self, model_size="tiny", device="auto", language="en"):
        type(self).constructions += 1
        self.model_size = model_size

    @property
    def is_loaded(self):
        return True

    @property
    def device_info(self):
        return "cpu (int8)"

    def load(self):
        type(self).loads += 1


class _FakeWS:
    def __init__(self):
        self.sent: list = []

    async def send(self, payload):
        self.sent.append(payload)


def _handles(ws, aborted=None):
    async def _complete(_fn, _rid):
        raise AssertionError("load path must not use the transcribe tail")

    def _launch(_fn, _rid):
        raise AssertionError("load path must not use the transcribe tail")

    return _CommandHandles(
        websocket=ws,
        samples={},
        aborted=set() if aborted is None else set(aborted),
        streams={},
        complete=_complete,
        launch=_launch,
    )


def _stub_transcriber(monkeypatch, calls: list | None = None):
    import voice_typer.worker._transcribe as transcribe_mod
    import voice_typer.worker._ws_commands as commands_mod

    class _FakeTranscriber:
        def load_whisper_model(self, model_size, device=None, language=None):
            if calls is not None:
                calls.append((model_size, device, language))
            return {"loaded": True, "backend": "whisper", "device_info": "cpu (int8)", "error": None}

    monkeypatch.setattr(transcribe_mod, "get_transcriber", lambda: _FakeTranscriber())
    monkeypatch.setattr(commands_mod, "get_transcriber", lambda: _FakeTranscriber(), raising=False)


async def _drain_ws(ws, timeout=5.0):
    for _ in range(int(timeout / 0.01)):
        if ws.sent:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out waiting for worker result frame")


class TestConcurrentLoad:
    def test_concurrent_load_requests_share_single_flight_or_serialize(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            client._port = 5199
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
                futures = list(
                    pool.map(
                        lambda _i: client.request_load_whisper_model("tiny", None, "en", timeout=None),
                        range(10),
                    )
                )
            assert all(f is not None for f in futures)
            ids = []
            while True:
                try:
                    ids.append(json.loads(client._outbound.get_nowait())["id"])
                except queue.Empty:
                    break
            assert len(ids) == 10
            assert len(set(ids)) == 10
            payload = {"loaded": True, "backend": "whisper", "device_info": "cpu", "error": None}
            for request_id in ids:
                assert client._take_result(request_id, payload) is True
            for future in futures:
                assert future.result(timeout=5)["loaded"] is True
        finally:
            client.close()


class TestTimeoutFallback:
    def test_worker_timeout_falls_back(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            client._port = 5199
            future = client.request_load_whisper_model("tiny", None, "en", timeout=0.05)
            assert future is not None
            request_id = json.loads(client._outbound.get_nowait())["id"]
            with pytest.raises(TimeoutError):
                future.result(timeout=5)
            assert request_id not in client._resolvers
            assert (
                client._take_result(
                    request_id,
                    {"loaded": True, "backend": "whisper", "device_info": "cpu", "error": None},
                )
                is False
            )
        finally:
            client.close()


class TestMalformedFrames:
    def test_malformed_frames_never_hang(self):
        published: list = []
        frames = [
            {"type": "load_whisper_model_result", "data": {"loaded": True}},
            {"type": "load_whisper_model_result", "id": 3, "data": None},
            {"type": "load_whisper_model_result", "id": 4, "data": "boom"},
            {"type": "load_whisper_model_result", "id": 5, "data": {"loaded": False, "error": "gpu gone"}},
            {"type": "error", "data": "worker exploded"},
        ]
        for frame in frames:
            seen: list = []

            def _record(i, r, _seen=seen):
                _seen.append((i, r))

            action = route_frame(frame, published.append, _record)
            assert action in ("load_result", "error")
        assert published == []

    def test_non_dict_raw_never_reaches_router(self):
        assert parse_incoming("[1,2,3]") is None
        assert parse_incoming("not json{{{") is None
        assert parse_incoming(b"\xff\xfe") is None

    async def test_handler_missing_model_size_sends_loaded_false(self):
        ws = _FakeWS()
        await handle_load_whisper_model_async(
            {"cmd": "load_whisper_model", "id": 21, "data": {}}, _handles(ws)
        )
        assert len(ws.sent) == 1
        frame = json.loads(ws.sent[0])
        assert frame["type"] == "load_whisper_model_result"
        assert frame["id"] == 21
        assert frame["data"]["loaded"] is False
        assert frame["data"]["error"] is not None

    async def test_handler_missing_id_sends_nothing(self):
        ws = _FakeWS()
        await handle_load_whisper_model_async(
            {"cmd": "load_whisper_model", "data": {"model_size": "tiny"}}, _handles(ws)
        )
        await handle_load_whisper_model_async("not-a-dict" if False else {"cmd": "x"}, _handles(ws))
        assert ws.sent == []


class TestAbortSemantics:
    async def test_abort_does_not_kill_load(self, monkeypatch):
        calls: list = []
        _stub_transcriber(monkeypatch, calls)
        ws = _FakeWS()
        await handle_load_whisper_model_async(
            {
                "cmd": "load_whisper_model",
                "id": 9,
                "data": {"model_size": "tiny", "device": None, "language": "en"},
            },
            _handles(ws, aborted={9}),
        )
        await _drain_ws(ws)
        assert len(ws.sent) == 1
        frame = json.loads(ws.sent[0])
        assert frame["id"] == 9
        assert frame["data"]["loaded"] is True
        assert calls == [("tiny", None, "en")]


class TestTranscriberCache:
    def test_transcriber_cache_hit_fast(self, monkeypatch):
        import voice_typer.worker.whisper.engine as engine_mod

        _StubEngine.constructions = 0
        _StubEngine.loads = 0
        monkeypatch.setattr(engine_mod, "TranscriptionEngine", _StubEngine)
        transcriber = WorkerTranscriber()
        first = transcriber.load_whisper_model("tiny", None, "en")
        assert first["loaded"] is True
        assert _StubEngine.constructions == 1
        second = transcriber.load_whisper_model("tiny", None, "en")
        assert second["loaded"] is True
        assert second["error"] is None
        assert _StubEngine.constructions == 1
        assert transcriber._engine is not None

    def test_cache_miss_on_language_change_rebuilds(self, monkeypatch):
        import voice_typer.worker.whisper.engine as engine_mod

        _StubEngine.constructions = 0
        _StubEngine.loads = 0
        monkeypatch.setattr(engine_mod, "TranscriptionEngine", _StubEngine)
        transcriber = WorkerTranscriber()
        transcriber.load_whisper_model("tiny", None, "en")
        transcriber.load_whisper_model("tiny", None, "de")
        assert _StubEngine.constructions == 2


class TestOutboundFull:
    def test_outbound_queue_full_returns_none(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            client._port = 5199
            for i in range(_OUTBOUND_QUEUE_MAX):
                client._outbound.put_nowait(f"filler-{i}")
            assert client.request_load_whisper_model("tiny", None, "en") is None
            assert client._resolvers == {}
        finally:
            while True:
                try:
                    client._outbound.get_nowait()
                except queue.Empty:
                    break
            client.close()
