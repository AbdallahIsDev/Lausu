"""Unit tests for ADR-0025 C3 (in-memory samples) + C4 (abort, device_info).

Covers chunking/reassembly boundaries (empty, exact-size, multi-chunk,
out-of-order), abort mid-assembly and abort ack, and the optional
device_info field (present vs absent).
"""

from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import json

import numpy as np
from voice_typer.server._paths import IPC_TOKEN_ENV_VAR
from voice_typer.server.worker_client import (
    _MAX_FRAME_BYTES,
    _SAMPLES_CHUNK_RAW_BYTES,
    WorkerClient,
    chunk_samples,
    route_frame,
)
from voice_typer.worker import _ws_server as ws_server


def _payload(frame_str: str) -> dict:
    return json.loads(frame_str)["data"]


class TestChunkBoundaries:
    def test_empty_audio_yields_one_empty_chunk(self):
        frames = chunk_samples(b"", 16000, "en", 7)
        assert len(frames) == 1
        data = _payload(frames[0])
        assert (data["index"], data["total"]) == (0, 1)
        assert data["payload_b64"] == ""
        assert json.loads(frames[0])["id"] == 7

    def test_exact_chunk_size_yields_one_frame(self):
        frames = chunk_samples(b"\x00" * _SAMPLES_CHUNK_RAW_BYTES, 16000, None, 3)
        assert len(frames) == 1
        assert _payload(frames[0])["total"] == 1

    def test_one_byte_over_yields_two_frames(self):
        frames = chunk_samples(b"\x01" * (_SAMPLES_CHUNK_RAW_BYTES + 1), 16000, "en", 9)
        assert len(frames) == 2
        first, second = (json.loads(f) for f in frames)
        assert (first["data"]["index"], first["data"]["total"]) == (0, 2)
        assert (second["data"]["index"], second["data"]["total"]) == (1, 2)
        assert first["id"] == second["id"] == 9

    def test_every_frame_fits_the_cap(self):
        frames = chunk_samples(b"\x02" * (_SAMPLES_CHUNK_RAW_BYTES * 2 + 100), 22050, "en", 11)
        assert len(frames) == 3
        for frame in frames:
            assert len(frame.encode("utf-8")) < _MAX_FRAME_BYTES

    def test_rate_and_language_ride_every_chunk(self):
        frames = chunk_samples(b"\x03" * 10, 44100, "de", 5)
        for frame in frames:
            data = _payload(frame)
            assert data["sample_rate"] == 44100
            assert data["language"] == "de"


class TestAssembler:
    def test_out_of_order_reassembles(self):
        buf = ws_server._SamplesBuffer(total=3, sample_rate=16000, language="en")
        assert buf.add_chunk(2, base64.b64encode(b"cc").decode("ascii")) is None
        assert not buf.is_complete()
        assert buf.add_chunk(0, base64.b64encode(b"aa").decode("ascii")) is None
        assert buf.add_chunk(1, base64.b64encode(b"bb").decode("ascii")) is None
        assert buf.is_complete()
        assert buf.audio_bytes() == b"aabbcc"

    def test_duplicate_index_is_an_error(self):
        buf = ws_server._SamplesBuffer(total=2, sample_rate=16000, language=None)
        assert buf.add_chunk(0, base64.b64encode(b"a").decode("ascii")) is None
        assert buf.add_chunk(0, base64.b64encode(b"b").decode("ascii")) is not None
        assert not buf.is_complete()

    def test_bad_base64_is_an_error(self):
        buf = ws_server._SamplesBuffer(total=1, sample_rate=16000, language=None)
        assert buf.add_chunk(0, "!!!not-base64!!!") is not None

    def test_index_out_of_range_is_an_error(self):
        buf = ws_server._SamplesBuffer(total=1, sample_rate=16000, language=None)
        assert buf.add_chunk(1, "") is not None
        assert buf.add_chunk(-1, "") is not None

    def test_empty_single_chunk_completes(self):
        buf = ws_server._SamplesBuffer(total=1, sample_rate=16000, language="en")
        assert buf.add_chunk(0, "") is None
        assert buf.is_complete()
        assert buf.audio_bytes() == b""

    def test_header_validation(self):
        ok = {"total": 2, "index": 0, "sample_rate": 16000, "language": "en"}
        assert ws_server._valid_samples_header(dict(ok))[4] is None
        for bad in (
            {"total": 0, "index": 0, "sample_rate": 16000},
            {"total": 65, "index": 0, "sample_rate": 16000},
            {"total": "2", "index": 0, "sample_rate": 16000},
            {"total": 2, "index": 0, "sample_rate": 999},
            {"total": 2, "index": 0, "sample_rate": True},
            {"total": 2, "index": 0},
        ):
            assert ws_server._valid_samples_header(bad)[4] is not None


class _ScriptedWS:
    """Fake worker-side socket: one recv (auth) then async iteration."""

    def __init__(self, auth_frame: str, incoming=()) -> None:
        self.sent: list = []
        self._auth = auth_frame
        self._incoming = list(incoming)
        self.remote_address = ("127.0.0.1", 1)
        self.origin = ""
        self.closed = False

    async def recv(self):
        return self._auth

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for item in self._incoming:
            if isinstance(item, BaseException):
                raise item
            yield item

    async def send(self, frame) -> None:
        self.sent.append(frame)

    async def close(self, code=None) -> None:
        self.closed = True


class _DoneError(Exception):
    pass


def _abort_frame(request_id):
    return json.dumps({"cmd": "abort_request", "id": request_id, "data": {}})


class TestAbortSession:
    async def test_abort_unknown_id_still_acks(self, monkeypatch):
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")
        auth = json.dumps({"type": "auth", "token": "tok"})
        ws = _ScriptedWS(auth, [_abort_frame(41), _DoneError()])
        await ws_server._handle_connection(
            ws,
            prewarm_ran=False,
            stop_event=asyncio.Event(),
            shutdown_timer=ws_server._ShutdownTimer(),
        )
        acks = [json.loads(f) for f in ws.sent if json.loads(f).get("type") == "abort_ack"]
        assert acks == [{"type": "abort_ack", "id": 41, "data": {"aborted": True}}]

    async def test_abort_mid_assembly_refuses_late_chunks(self, monkeypatch):
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")
        auth = json.dumps({"type": "auth", "token": "tok"})
        chunk0 = json.dumps(
            {
                "cmd": "transcribe_samples",
                "id": 8,
                "data": {
                    "index": 0,
                    "total": 2,
                    "sample_rate": 16000,
                    "language": "en",
                    "payload_b64": base64.b64encode(b"aa").decode("ascii"),
                },
            }
        )
        chunk1 = json.loads(chunk0)
        chunk1["data"]["index"] = 1
        ws = _ScriptedWS(auth, [chunk0, _abort_frame(8), json.dumps(chunk1), _DoneError()])
        await ws_server._handle_connection(
            ws,
            prewarm_ran=False,
            stop_event=asyncio.Event(),
            shutdown_timer=ws_server._ShutdownTimer(),
        )
        bodies = [json.loads(f) for f in ws.sent]
        assert {"type": "abort_ack", "id": 8, "data": {"aborted": True}} in bodies
        errors = [b for b in bodies if b.get("type") == "transcribe_offline_result" and b.get("id") == 8]
        assert len(errors) == 1
        assert errors[0]["data"]["error"] == "request aborted"


class _SlowTranscriber:
    """Fake backend: slow inference, cooperative abort flag."""

    def __init__(self, delay: float = 0.5) -> None:
        self._delay = delay
        self.aborted = False
        self.calls = 0

    def transcribe_array(self, audio, sample_rate, language):
        import threading as _threading

        self.calls += 1
        _threading.Event().wait(self._delay)
        return {"text": "slow words", "error": None}

    def transcribe_file(self, *args):
        return self.transcribe_array(None, 0, None)

    def request_abort(self) -> bool:
        self.aborted = True
        return True


def _samples_frame(request_id, index=0, total=1, text_bytes=b"aaaa"):
    return json.dumps(
        {
            "cmd": "transcribe_samples",
            "id": request_id,
            "data": {
                "index": index,
                "total": total,
                "sample_rate": 16000,
                "language": "en",
                "payload_b64": base64.b64encode(text_bytes).decode("ascii"),
            },
        }
    )


class TestAbortMidInference:
    async def test_abort_landing_mid_inference_drops_result(self, monkeypatch):
        """The abort must be processed while inference runs, not after.

        Regression: the handler awaited inference inline, so an abort
        queued behind it always lost the race and the result leaked.
        """
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")
        fake = _SlowTranscriber(delay=0.5)
        monkeypatch.setattr("voice_typer.worker._transcribe.get_transcriber", lambda: fake)
        auth = json.dumps({"type": "auth", "token": "tok"})
        ws = _ScriptedWS(auth, [_samples_frame(50), _abort_frame(50), _DoneError()])
        await ws_server._handle_connection(
            ws,
            prewarm_ran=False,
            stop_event=asyncio.Event(),
            shutdown_timer=ws_server._ShutdownTimer(),
        )
        await asyncio.sleep(1.0)
        bodies = [json.loads(f) for f in ws.sent]
        assert {"type": "abort_ack", "id": 50, "data": {"aborted": True}} in bodies
        assert fake.aborted is True
        assert [b for b in bodies if b.get("type") == "transcribe_offline_result"] == []

    async def test_unaborted_samples_still_deliver(self, monkeypatch):
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")
        fake = _SlowTranscriber(delay=0.01)
        monkeypatch.setattr("voice_typer.worker._transcribe.get_transcriber", lambda: fake)
        auth = json.dumps({"type": "auth", "token": "tok"})
        ws = _ScriptedWS(auth, [_samples_frame(51), _DoneError()])
        await ws_server._handle_connection(
            ws,
            prewarm_ran=False,
            stop_event=asyncio.Event(),
            shutdown_timer=ws_server._ShutdownTimer(),
        )
        await asyncio.sleep(0.5)
        bodies = [json.loads(f) for f in ws.sent]
        results = [b for b in bodies if b.get("type") == "transcribe_offline_result" and b.get("id") == 51]
        assert len(results) == 1
        assert results[0]["data"]["text"] == "slow words"


class TestEmptyArrayNeedsNoEngine:
    def test_zero_length_audio_returns_empty_without_loading(self, monkeypatch):
        from voice_typer.worker._transcribe import WorkerTranscriber

        def _fail(*args, **kwargs):
            raise AssertionError("engine must not build for empty audio")

        monkeypatch.setattr(WorkerTranscriber, "_ensure_engine", _fail)
        out = WorkerTranscriber().transcribe_array(np.zeros(0, dtype="float32"), 16000, "en")
        assert out["text"] == "" and out["error"] is None


class TestDeviceInfo:
    def test_present_device_info_is_preserved(self):
        published: list = []
        frame = {
            "type": "transcribe_offline_result",
            "id": 1,
            "data": {"text": "hi", "latency_ms": 3, "device_info": "cuda (float16)"},
        }
        assert route_frame(frame, published.append) == "result"
        assert published[0]["data"]["device_info"] == "cuda (float16)"

    def test_absent_device_info_keeps_frozen_shape(self):
        published: list = []
        frame = {"type": "transcribe_offline_result", "data": {"text": "hi", "latency_ms": 3}}
        assert route_frame(frame, published.append) == "result"
        assert published[0]["data"] == {"text": "hi", "latency_ms": 3}

    def test_non_string_device_info_is_dropped(self):
        published: list = []
        frame = {
            "type": "transcribe_offline_result",
            "data": {"text": "hi", "latency_ms": 3, "device_info": {"gpu": 0}},
        }
        assert route_frame(frame, published.append) == "result"
        assert "device_info" not in published[0]["data"]


class TestSamplesClient:
    def test_request_samples_none_without_port(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            assert client.request_samples(b"\x00" * 8, 16000) is None
        finally:
            client.close()

    def test_request_samples_resolves_by_id(self, monkeypatch):
        monkeypatch.setenv("VOICE_TYPER_IPC_TOKEN", "t")
        published: list = []
        client = WorkerClient(publish=published.append)
        client._port = 5123
        try:
            future = client.request_samples(b"\x00" * 100, 16000, "en")
            assert isinstance(future, concurrent.futures.Future)
            assert len(client._outbound.queue) == 1
            frame = {
                "type": "transcribe_offline_result",
                "id": 1,
                "data": {"text": "x", "latency_ms": 1, "device_info": "cpu"},
            }
            assert route_frame(frame, published.append, on_result=client._take_result) == "result"
            assert future.result(timeout=5) == {"text": "x", "latency_ms": 1, "device_info": "cpu"}
        finally:
            client.close()

    def test_send_abort_needs_port(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            assert client.send_abort(1) is False
            client._port = 5123
            assert client.send_abort(1) is True
            body = json.loads(client._outbound.get_nowait())
            assert body == {"cmd": "abort_request", "id": 1, "data": {}}
        finally:
            client.close()

    def test_abort_ack_routes_without_publish(self):
        published: list = []
        assert route_frame({"type": "abort_ack", "id": 9}, published.append) == "abort_ack"
        assert published == []
