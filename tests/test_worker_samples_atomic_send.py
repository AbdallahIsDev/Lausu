"""Atomic multi-frame sends to the runtime-pack worker.

Covers the capacity pre-checks and the enqueue rollback behind
``WorkerClient.request_samples`` / ``enqueue_frames`` plus the
oversize fail-fast in ``WorkerBackedAsr.transcribe_with_fallback``:
oversize and contended sends fail before touching the queue, a
mid-enqueue ``Full`` leaves none of the request's frames behind, and
the streamed frames stay byte-identical to the list-built ones.
"""

from __future__ import annotations

import concurrent.futures
import json
import queue

import numpy as np
import pytest
from voice_typer.server import worker_client, worker_protocol
from voice_typer.server.worker_backed_asr import WorkerBackedAsr, WorkerTranscriptionError
from voice_typer.server.worker_client import WorkerClient


def _client() -> WorkerClient:
    client = WorkerClient(publish=lambda event: None)
    client._port = 5123
    return client


def _small_chunks(monkeypatch: pytest.MonkeyPatch, raw_bytes: int = 100) -> None:
    monkeypatch.setattr(worker_protocol, "_SAMPLES_CHUNK_RAW_BYTES", raw_bytes)


def _queued_ids(client: WorkerClient) -> list:
    ids = []
    with client._outbound.mutex:
        for frame in list(client._outbound.queue):
            ids.append(json.loads(frame).get("id"))
    return ids


class TestSharedCapSource:
    def test_client_worker_and_protocol_agree(self):
        from voice_typer.server.ipc.protocol_version import MAX_SAMPLES_CHUNKS
        from voice_typer.worker import _ws_samples

        assert worker_protocol._SAMPLES_MAX_CHUNKS == MAX_SAMPLES_CHUNKS
        assert worker_client._SAMPLES_MAX_CHUNKS == MAX_SAMPLES_CHUNKS
        assert _ws_samples._SAMPLES_MAX_CHUNKS == MAX_SAMPLES_CHUNKS

    def test_worker_header_enforces_the_shared_cap(self):
        from voice_typer.worker._ws_samples import _SAMPLES_MAX_CHUNKS, _valid_samples_header

        ok = {"total": _SAMPLES_MAX_CHUNKS, "index": 0, "sample_rate": 16000}
        assert _valid_samples_header(dict(ok))[4] is None
        over = dict(ok, total=_SAMPLES_MAX_CHUNKS + 1)
        assert _valid_samples_header(over)[4] is not None


class TestRequestSamplesPrechecks:
    def test_oversize_never_builds_frames(self, monkeypatch):
        _small_chunks(monkeypatch)
        client = _client()
        built: list = []

        def _spy(*args, **kwargs):
            built.append(True)
            return iter([])

        monkeypatch.setattr(worker_client, "iter_chunk_samples", _spy)
        audio = b"\x00" * (64 * 100 + 1)
        assert client.request_samples(audio, 16000, "en") is None
        assert built == []
        assert client._outbound.qsize() == 0
        assert client._resolvers == {}

    def test_contended_queue_keeps_existing_frames(self, monkeypatch):
        _small_chunks(monkeypatch)
        client = _client()
        for index in range(60):
            client._outbound.put_nowait(f"dummy-{index}")
        audio = b"\x00" * (8 * 100)
        assert client.request_samples(audio, 16000, "en") is None
        assert client._outbound.qsize() == 60
        with client._outbound.mutex:
            assert [f for f in client._outbound.queue] == [f"dummy-{index}" for index in range(60)]
        assert client._resolvers == {}

    def test_empty_audio_still_sends_one_chunk(self):
        client = _client()
        future = client.request_samples(b"", 16000, "en")
        assert future is not None
        assert client._outbound.qsize() == 1
        payload = json.loads(client._outbound.get_nowait())["data"]
        assert (payload["index"], payload["total"]) == (0, 1)


class TestAtomicEnqueue:
    def test_mid_enqueue_full_withdraws_samples_frames(self, monkeypatch):
        _small_chunks(monkeypatch)
        client = _client()
        real_put = client._outbound.put_nowait
        calls: list = []

        def _flaky(frame):
            calls.append(frame)
            if len(calls) == 3:
                raise queue.Full
            return real_put(frame)

        monkeypatch.setattr(client._outbound, "put_nowait", _flaky)
        before = client._request_seq
        assert client.request_samples(b"\x00" * (4 * 100), 16000, "en") is None
        assert client._outbound.qsize() == 0
        assert (before + 1) not in _queued_ids(client)
        assert client._resolvers == {}

    def test_mid_enqueue_full_withdraws_streaming_frames(self, monkeypatch):
        client = _client()
        client._outbound.put_nowait("dummy-0")
        real_put = client._outbound.put_nowait
        calls: list = []

        def _flaky(frame):
            calls.append(frame)
            if len(calls) == 2:
                raise queue.Full
            return real_put(frame)

        monkeypatch.setattr(client._outbound, "put_nowait", _flaky)
        assert client.enqueue_frames(["f-1", "f-2", "f-3"]) is False
        with client._outbound.mutex:
            assert list(client._outbound.queue) == ["dummy-0"]

    def test_enqueue_frames_prefetch_refuses_without_mutation(self):
        client = _client()
        for index in range(63):
            client._outbound.put_nowait(f"dummy-{index}")
        assert client.enqueue_frames(["f-1", "f-2"]) is False
        assert client._outbound.qsize() == 63

    def test_enqueue_frames_small_batch_succeeds(self):
        client = _client()
        client._outbound.put_nowait("dummy-0")
        assert client.enqueue_frames(["f-1", "f-2"]) is True
        assert client._outbound.qsize() == 3


class TestGeneratorParity:
    def test_streamed_frames_match_list_built(self):
        audio = b"\xab" * (720 * 1024 * 2 + 17)
        streamed = list(worker_protocol.iter_chunk_samples(audio, 22050, "de", 11))
        listed = worker_protocol.chunk_samples(audio, 22050, "de", 11)
        assert streamed == listed
        assert len(streamed) == 3
        for index, frame in enumerate(streamed):
            assert isinstance(frame, str)
            body = json.loads(frame)
            assert body["id"] == 11 and not isinstance(body["id"], bool)
            assert (body["data"]["index"], body["data"]["total"]) == (index, 3)
            assert len(frame.encode("utf-8")) < worker_protocol._MAX_FRAME_BYTES


class _FakeClient:
    def __init__(self) -> None:
        self.requests: list = []

    @property
    def port(self):
        return 5123

    def request_samples(self, raw, rate, language, timeout=None):
        self.requests.append((bytes(raw), rate, language))
        future: concurrent.futures.Future[dict] = concurrent.futures.Future()
        future.set_result({"text": "ok", "latency_ms": 1})
        return future


class TestBackedAsrPrecheck:
    def test_oversize_raises_before_touching_client(self, monkeypatch):
        import voice_typer.server.worker_backed_asr as shim_mod

        _small_chunks(monkeypatch)
        fake = _FakeClient()
        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: fake)
        audio = np.zeros(64 * 100 // 4 + 1, dtype=np.float32)
        with pytest.raises(WorkerTranscriptionError):
            WorkerBackedAsr().transcribe_with_fallback(audio)
        assert fake.requests == []

    def test_small_audio_forwards_exact_bytes(self, monkeypatch):
        import voice_typer.server.worker_backed_asr as shim_mod

        fake = _FakeClient()
        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: fake)
        audio = np.arange(400, dtype=np.float32)
        assert WorkerBackedAsr().transcribe_with_fallback(audio) == "ok"
        raw, rate, _language = fake.requests[0]
        assert raw == audio.tobytes()
        assert rate == 16000
