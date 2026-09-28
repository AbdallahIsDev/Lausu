"""Unit tests for the slim-side C6 worker streaming session + client branches."""

from __future__ import annotations

import concurrent.futures
import json
from types import SimpleNamespace

import numpy as np
from voice_typer.server import worker_streaming
from voice_typer.server.worker_client import route_frame
from voice_typer.server.worker_streaming import WorkerStreamingSession


class _FakeClient:
    def __init__(self) -> None:
        self.sent: list = []
        self.acked = True
        self._seq = 0
        self.aborts: list = []
        self.port = 5123

    def open_streaming_session(self, config, timeout=None):
        self._seq += 1
        self.sent.append(("open", dict(config)))
        future: concurrent.futures.Future[dict] = concurrent.futures.Future()
        if self.acked:
            future.set_result({"opened": True})
        return (self._seq, future)

    def expect_streaming_result(self, request_id, timeout=None):
        future: concurrent.futures.Future[dict] = concurrent.futures.Future()
        self._result_future = future
        return future

    def enqueue_frames(self, frames) -> bool:
        self.sent.extend(("frame", f) for f in frames)
        return True

    def send_abort(self, request_id) -> bool:
        self.aborts.append(request_id)
        return True

    def cancel_request(self, request_id) -> bool:
        return True


class _DeadClient(_FakeClient):
    def open_streaming_session(self, config, timeout=None):
        return None


def _recorder(samples=16000):
    return SimpleNamespace(snapshot=lambda: np.zeros(samples, dtype=np.float32))


def _config():
    return SimpleNamespace(
        chunk_seconds=12.0,
        step_seconds=5.0,
        left_overlap_seconds=3.0,
        right_guard_seconds=1.5,
        min_first_chunk_seconds=6.0,
        silence_threshold=0.003,
    )


class TestStart:
    def test_open_failure_means_build_in_process(self):
        session = WorkerStreamingSession(_recorder(), _DeadClient(), _config(), 16000, cycle_id="c1")
        assert session.start() is False
        assert session._request_id is None

    def test_open_ack_starts_push_driver(self):
        client = _FakeClient()
        session = WorkerStreamingSession(_recorder(), client, _config(), 16000, cycle_id="c1")
        try:
            assert session.start() is True
            assert session._request_id == 1
            assert session.is_running
            assert client.sent[0][0] == "open"
            assert client.sent[0][1]["cycle_id"] == "c1"
            assert client.sent[0][1]["sample_rate"] == 16000
        finally:
            session.cancel(blocking=True)


class TestFinalize:
    def test_finalize_returns_worker_text(self):
        client = _FakeClient()
        session = WorkerStreamingSession(_recorder(8000), client, _config(), 16000, cycle_id="c9")
        try:
            assert session.start() is True
            session._result_future.set_result({"text": "streamed hello", "error": None})
            assert session.finalize(np.zeros(8000, dtype=np.float32)) == "streamed hello"
            finalize_frames = [json.loads(f) for kind, f in client.sent if kind == "frame" and "finalize" in f]
            assert len(finalize_frames) == 1
            assert finalize_frames[0]["id"] == 1
        finally:
            session.cancel(blocking=True)

    def test_finalize_error_becomes_empty_text(self):
        client = _FakeClient()
        session = WorkerStreamingSession(_recorder(8000), client, _config(), 16000)
        try:
            assert session.start() is True
            session._result_future.set_result({"text": "", "error": "boom"})
            assert session.finalize(np.zeros(8000, dtype=np.float32)) == ""
        finally:
            session.cancel(blocking=True)

    def test_finalize_without_start_is_empty(self):
        session = WorkerStreamingSession(_recorder(), _FakeClient(), _config(), 16000)
        assert session.finalize(np.zeros(100, dtype=np.float32)) == ""


class TestCancel:
    def test_cancel_aborts_worker_session(self):
        client = _FakeClient()
        session = WorkerStreamingSession(_recorder(), client, _config(), 16000)
        try:
            assert session.start() is True
            session.cancel(blocking=True)
            assert client.aborts == [1]
            assert not session.is_running
        finally:
            session.cancel(blocking=True)


class TestRouteBranches:
    def test_opened_resolves_but_does_not_publish(self):
        published: list = []
        seen: dict = {}
        action = route_frame(
            {"type": "streaming_session_opened", "id": 4, "data": {"opened": True}},
            published.append,
            on_result=lambda rid, res: seen.update({rid: res}),
        )
        assert action == "streaming_opened"
        assert seen == {4: {"opened": True}}
        assert published == []

    def test_streaming_result_resolves_without_publish(self):
        published: list = []
        seen: dict = {}
        action = route_frame(
            {"type": "streaming_session_result", "id": 6, "data": {"text": "t", "error": None}},
            published.append,
            on_result=lambda rid, res: seen.update({rid: res}),
        )
        assert action == "streaming_result"
        assert seen == {6: {"text": "t", "error": None}}
        assert published == []

    def test_partial_publishes_worker_shape(self):
        published: list = []
        action = route_frame(
            {
                "type": "transcription_partial",
                "id": 6,
                "data": {"text": "hel", "cycle_id": "c", "is_final": False, "words": []},
            },
            published.append,
        )
        assert action == "partial"
        assert published == [
            {
                "type": "transcription_partial",
                "data": {"text": "hel", "cycle_id": "c", "is_final": False, "words": []},
            }
        ]


class TestAssemblerPortFidelity:
    """Worker assembler must behave exactly like the slim original.

    Same word sequences through each side's real finalize-tail path
    must produce identical text. In particular the live boundary
    variant (committed "pack"+"worker" vs tail "PackWorker") must merge
    clean on both sides via the merge-boundary filter.
    """

    def _words(self, *triples):
        from types import SimpleNamespace

        return [SimpleNamespace(word=w, start_seconds=s, end_seconds=e) for w, s, e in triples]

    def _slim_merge(self, committed, tail):
        from voice_typer.server.streaming import AudioWindow, StreamingTextAssembler

        slim = StreamingTextAssembler()
        window = AudioWindow(audio=np.zeros(8, dtype=np.float32), start_seconds=0.0, end_seconds=8.0)
        slim.add_window(window, committed, right_guard_seconds=1.5)
        boundary = max(w.end_seconds for w in committed)
        fresh = [w for w in tail if w.end_seconds > boundary]
        slim.add_words(fresh, commit_horizon_seconds=float("inf"))
        return slim.committed_text

    def _worker_merge(self, committed, tail):
        from types import SimpleNamespace

        from voice_typer.worker.streaming import StreamingSession

        session = StreamingSession(99, SimpleNamespace(sample_rate=16000))
        session.assembler.add_window(8.0, committed, 1.5)
        return session.commit_tail(tail)

    def test_identical_sequences_identical_text(self):
        committed = self._words(("hello", 0.0, 0.4), ("world", 0.5, 0.9))
        tail = self._words(("world", 0.5, 0.9), ("again", 1.0, 1.4))
        assert self._worker_merge(committed, tail) == self._slim_merge(committed, tail) == "hello world again"

    def test_boundary_variant_merges_clean_on_both(self):
        committed = self._words(("runtime", 4.0, 4.4), ("pack", 4.5, 4.8), ("worker", 5.0, 5.4))
        tail = self._words(("PackWorker", 4.5, 4.9), ("worker", 5.0, 5.4), ("handoff", 5.5, 5.9))
        slim_text = self._slim_merge(committed, tail)
        worker_text = self._worker_merge(committed, tail)
        assert worker_text == slim_text
        assert "PackWorker" not in worker_text
        assert worker_text == "runtime pack worker handoff"


class TestCoordinatorSwitch:
    def _controller(self, monkeypatch, gate, client):
        import voice_typer.server.worker_path as worker_path_mod
        from voice_typer.server import streaming_session_coordinator as coord_mod, worker_client as worker_client_mod

        monkeypatch.setattr(worker_path_mod, "worker_path_available", lambda app: gate)
        monkeypatch.setattr(worker_client_mod, "get_shared_client", lambda: client)
        app = SimpleNamespace(
            recorder=_recorder(),
            models=SimpleNamespace(active_transcriber=lambda: SimpleNamespace(transcribe_words=lambda: None)),
            config=SimpleNamespace(
                streaming_transcription=True,
                streaming_chunk_seconds=12.0,
                streaming_step_seconds=5.0,
                streaming_left_overlap_seconds=3.0,
                streaming_right_guard_seconds=1.5,
                streaming_min_first_chunk_seconds=6.0,
                streaming_silence_threshold=0.003,
                sample_rate=16000,
                language="en",
            ),
            _cycle_id="cy",
        )
        controller = SimpleNamespace(_app=app, _sessions=[None])
        controller.set_streaming_session = lambda s: controller._sessions.__setitem__(0, s)
        return coord_mod, controller

    def test_worker_session_preferred_when_gate_open(self, monkeypatch):
        coord_mod, controller = self._controller(monkeypatch, (True, "ok"), _FakeClient())
        coord = coord_mod.StreamingSessionCoordinator()
        coord.start_streaming_session_if_enabled(controller)
        try:
            session = controller._sessions[0]
            assert isinstance(session, worker_streaming.WorkerStreamingSession)
        finally:
            if controller._sessions[0] is not None:
                controller._sessions[0].cancel(blocking=True)

    def test_gate_off_falls_back_to_in_process(self, monkeypatch):
        import voice_typer.server.streaming_session_coordinator as coord_mod
        from voice_typer.server import streaming as streaming_mod

        made = {}

        class _FakeInProcess:
            def __init__(self, **kwargs):
                made["built"] = True

            def start(self):
                made["started"] = True

        monkeypatch.setattr(coord_mod, "StreamingTranscriptionSession", _FakeInProcess)
        _, controller = self._controller(monkeypatch, (False, "worker_no_port"), _FakeClient())
        coord = coord_mod.StreamingSessionCoordinator()
        coord.start_streaming_session_if_enabled(controller)
        assert made.get("built") is True
        assert made.get("started") is True
        assert streaming_mod is not None

    def test_worker_backed_skips_in_process_when_worker_fails(self, monkeypatch):
        """WorkerBackedAsr has no word engine: worker failure must skip, not rebuild."""
        import voice_typer.server.streaming_session_coordinator as coord_mod
        from voice_typer.server.worker_backed_asr import WorkerBackedAsr

        made = {}

        class _FakeInProcess:
            def __init__(self, **kwargs):
                made["built"] = True

        monkeypatch.setattr(coord_mod, "StreamingTranscriptionSession", _FakeInProcess)
        _, controller = self._controller(monkeypatch, (False, "worker_no_port"), _DeadClient())
        controller._app.models.active_transcriber = lambda: WorkerBackedAsr()
        published: list = []
        monkeypatch.setattr(
            "voice_typer.server.streaming_session_coordinator.event_bus.publish",
            published.append,
        )
        coord = coord_mod.StreamingSessionCoordinator()
        coord.start_streaming_session_if_enabled(controller)
        assert made.get("built") is None
        assert controller._sessions[0] is None
        unsupported = [p for p in published if p.get("data", {}).get("supported") is False]
        assert unsupported, published

    def test_worker_backed_uses_worker_session_when_gate_open(self, monkeypatch):
        from voice_typer.server.worker_backed_asr import WorkerBackedAsr

        coord_mod, controller = self._controller(monkeypatch, (True, "ok"), _FakeClient())
        controller._app.models.active_transcriber = lambda: WorkerBackedAsr()
        coord = coord_mod.StreamingSessionCoordinator()
        coord.start_streaming_session_if_enabled(controller)
        try:
            session = controller._sessions[0]
            assert isinstance(session, worker_streaming.WorkerStreamingSession)
        finally:
            if controller._sessions[0] is not None:
                controller._sessions[0].cancel(blocking=True)
