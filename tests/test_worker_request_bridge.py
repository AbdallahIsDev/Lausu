"""Unit tests for the ADR-0025 C2 sync bridge (``WorkerClient.request_transcribe``).

Covers the C2 matrix: id-echo correlation, timeout, cancel, missing /
non-int id fallback to type-routing without dropping the publish, and a
raising resolver never dropping the result.
"""

from __future__ import annotations

import asyncio
import collections
import concurrent.futures
import contextlib
import json
import threading
import time

import pytest
from voice_typer.server import worker_client
from voice_typer.server.worker_client import WorkerClient, route_frame


class _EndOfScriptError(Exception):
    """FakeWS raises this when its scripted inbound frames run out."""


class _FakeWS:
    def __init__(self, incoming=()) -> None:
        self.sent: list = []
        self._incoming = collections.deque(incoming)

    async def send(self, frame) -> None:
        self.sent.append(frame)

    async def recv(self):
        if not self._incoming:
            raise _EndOfScriptError
        item = self._incoming.popleft()
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self, code=None) -> None:
        pass


def _client():
    published: list = []
    client = WorkerClient(publish=published.append)
    client._port = 5123
    return client, published


def _result_frame(request_id, text="hello"):
    frame: dict = {"type": "transcribe_offline_result", "data": {"text": text, "latency_ms": 9}}
    if request_id is not None:
        frame["id"] = request_id
    return json.dumps(frame)


class TestRequestHandle:
    def test_returns_pending_future_and_registers_id(self):
        client, _ = _client()
        try:
            future = client.request_transcribe("a.wav", 16000, "en")
            assert isinstance(future, concurrent.futures.Future)
            assert not future.done()
            assert list(client._resolvers) == [1]
        finally:
            client.close()

    def test_no_port_returns_none(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            assert client.request_transcribe("a.wav") is None
            assert client._resolvers == {}
        finally:
            client.close()


class TestEchoCorrelation:
    async def test_matching_id_resolves_future_and_still_publishes(self, monkeypatch):
        monkeypatch.setenv("VOICE_TYPER_IPC_TOKEN", "t")
        client, published = _client()
        try:
            future = client.request_transcribe("a.wav")
            assert future is not None
            ws = _FakeWS([_result_frame(1, text="spoken words")])
            with pytest.raises(_EndOfScriptError):
                await client._run_session(ws, client._generation)
            assert future.done()
            assert future.result() == {"text": "spoken words", "latency_ms": 9}
            assert client._resolvers == {}
            assert published == [
                {"type": "transcribe_offline_result", "data": {"text": "spoken words", "latency_ms": 9}}
            ]
        finally:
            client.close()

    async def test_two_in_flight_resolve_out_of_order_by_id(self, monkeypatch):
        monkeypatch.setenv("VOICE_TYPER_IPC_TOKEN", "t")
        client, published = _client()
        try:
            first = client.request_transcribe("a.wav")
            second = client.request_transcribe("b.wav")
            assert first is not None and second is not None
            ws = _FakeWS([_result_frame(2, text="second"), _result_frame(1, text="first")])
            with pytest.raises(_EndOfScriptError):
                await client._run_session(ws, client._generation)
            assert first.result() == {"text": "first", "latency_ms": 9}
            assert second.result() == {"text": "second", "latency_ms": 9}
            assert len(published) == 2
        finally:
            client.close()


class TestIdFallback:
    @pytest.mark.parametrize("bad_id", [None, "7", True, 7.0, [1]])
    def test_non_int_id_falls_back_to_type_routing(self, bad_id):
        client, published = _client()
        try:
            future = client.request_transcribe("a.wav")
            assert future is not None
            action = route_frame(json.loads(_result_frame(bad_id)), published.append, on_result=client._take_result)
            assert action == "result"
            assert not future.done()
            assert published == [{"type": "transcribe_offline_result", "data": {"text": "hello", "latency_ms": 9}}]
            future.cancel()
        finally:
            client.close()

    def test_unknown_int_id_still_publishes(self):
        client, published = _client()
        try:
            action = route_frame(json.loads(_result_frame(4242)), published.append, on_result=client._take_result)
            assert action == "result"
            assert published != []
        finally:
            client.close()

    def test_raising_resolver_never_drops_result(self):
        published: list = []

        def _evil(_request_id, _result):
            raise RuntimeError("resolver blew up")

        action = route_frame(json.loads(_result_frame(3)), published.append, on_result=_evil)
        assert action == "result"
        assert published == [{"type": "transcribe_offline_result", "data": {"text": "hello", "latency_ms": 9}}]

    def test_take_result_never_raises(self):
        client, _ = _client()
        try:
            assert client._take_result(999, {"text": "x", "latency_ms": 0}) is False
        finally:
            client.close()


class TestTimeout:
    def test_expiry_fails_future_and_late_result_publishes(self):
        client, published = _client()
        try:
            future = client.request_transcribe("a.wav", timeout=0.05)
            assert future is not None
            with pytest.raises(TimeoutError):
                future.result(timeout=5)
            assert client._resolvers == {}
            action = route_frame(json.loads(_result_frame(1)), published.append, on_result=client._take_result)
            assert action == "result"
            assert published != []
            with pytest.raises(TimeoutError):
                future.result(timeout=1)
        finally:
            client.close()


class TestCancel:
    def test_cancel_drops_mapping_but_keeps_publish(self):
        client, published = _client()
        try:
            future = client.request_transcribe("a.wav")
            assert future is not None
            assert future.cancel() is True
            action = route_frame(json.loads(_result_frame(1)), published.append, on_result=client._take_result)
            assert action == "result"
            assert future.cancelled()
            assert published != []
        finally:
            client.close()


class TestSessionRegistrationGuard:
    async def test_newer_session_keeps_registration_when_older_exits(self, monkeypatch):
        """A superseded session's exit must not clear the live one's wake-up.

        Regression: relay + direct update double-point the client, so two
        generations overlap briefly; the older session's ``finally`` used
        to blank the pair the newer session had just stored, and every
        forward then waited out the heartbeat interval.
        """
        monkeypatch.setenv("VOICE_TYPER_IPC_TOKEN", "t")
        published: list = []
        client = WorkerClient(publish=published.append)
        client._port = 5123

        class _ParkingWS(_FakeWS):
            async def recv(self):
                await asyncio.sleep(3600)

        ws_old, ws_new = _ParkingWS([]), _ParkingWS([])
        try:
            gen = client._generation
            older = asyncio.ensure_future(client._run_session(ws_old, gen))
            await asyncio.sleep(0.2)
            newer = asyncio.ensure_future(client._run_session(ws_new, gen))
            await asyncio.sleep(0.2)
            live_wake = client._session_wake
            assert live_wake is not None
            older.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await older
            assert client._session_wake is live_wake
            newer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await newer
            assert client._session_wake is None
        finally:
            client.close()

    def test_notify_without_session_is_a_silent_noop(self):
        client = WorkerClient(publish=lambda _m: None)
        try:
            client._port = 5123
            assert client.send_transcribe("a.wav") == 1
            assert len(client._outbound.queue) == 1
        finally:
            client.close()

    def test_cancel_request_helper(self):
        client, published = _client()
        try:
            future = client.request_transcribe("a.wav")
            assert future is not None
            assert client.cancel_request(1) is True
            assert client.cancel_request(1) is False
            assert client.cancel_request(4242) is False
            action = route_frame(json.loads(_result_frame(1)), published.append, on_result=client._take_result)
            assert action == "result"
            assert published != []
        finally:
            client.close()


class TestSessionWakeup:
    async def test_queued_forward_drains_without_waiting_for_heartbeat(self, monkeypatch):
        """A forward queued mid-recv must send promptly (C4 abort path).

        With a 30 s heartbeat interval, a drain that only happened once
        per loop iteration would stall up to 30 s; the wake-up must cut
        that to milliseconds. Bounds (0.5 s sleeps vs 10 s limit) leave
        wide margin on either side.
        """
        monkeypatch.setenv("VOICE_TYPER_IPC_TOKEN", "t")
        monkeypatch.setattr(worker_client, "_HEARTBEAT_SECONDS", 30.0)
        published: list = []
        client = WorkerClient(publish=published.append)
        client._port = 5123
        release = threading.Event()
        result = json.dumps({"type": "transcribe_offline_result", "data": {"text": "x", "latency_ms": 1}})

        class _BlockingWS(_FakeWS):
            def __init__(self) -> None:
                super().__init__([])
                self._served = False

            async def recv(self):
                # Cooperative wait: a blocking Event.wait here would
                # freeze the loop this recv runs on.
                for _ in range(500):
                    if release.is_set():
                        if self._served:
                            raise _EndOfScriptError
                        self._served = True
                        return result
                    await asyncio.sleep(0.05)
                raise _EndOfScriptError

        ws = _BlockingWS()
        try:
            session = asyncio.ensure_future(client._run_session(ws, client._generation))
            await asyncio.sleep(0.5)
            t0 = time.perf_counter()
            assert client.send_transcribe("b.wav") == 1
            await asyncio.sleep(0.5)
            release.set()
            with pytest.raises(_EndOfScriptError):
                await asyncio.wait_for(asyncio.shield(session), timeout=20)
            assert time.perf_counter() - t0 < 10.0
            bodies = [json.loads(f) for f in ws.sent]
            assert bodies[1]["cmd"] == "transcribe_offline"
        finally:
            client.close()
