"""Unit tests for ADR-0025 C6 worker-side streaming (build only, no slim cutover).

Covers overlap/tail-dedup correctness with synthetic windows, out-of-order
pushes, abort-mid-session, finalize correctness, and FakeWS session tests
(open/push/finalize frames, unknown-id errors). No real model is loaded:
word inference is scripted through monkeypatched seams.
"""

from __future__ import annotations

import asyncio
import base64
import json

import numpy as np
from voice_typer.server._paths import IPC_TOKEN_ENV_VAR
from voice_typer.worker import _ws_server as ws_server
from voice_typer.worker.streaming import SessionConfig, StreamingSession, Word


def _words(texts: list[str], start: float, step: float = 1.0, length: float = 0.9) -> list[Word]:
    return [Word(text, start + i * step, start + i * step + length) for i, text in enumerate(texts)]


def _audio_b64(seconds: float, amplitude: float = 0.1, sample_rate: int = 16000) -> str:
    return base64.b64encode(np.full(int(seconds * sample_rate), amplitude, dtype=np.float32).tobytes()).decode("ascii")


def _test_config(**overrides) -> SessionConfig:
    base = {
        "sample_rate": 16000,
        "chunk_seconds": 12.0,
        "step_seconds": 5.0,
        "min_first_chunk_seconds": 6.0,
        "left_overlap_seconds": 3.0,
        "right_guard_seconds": 1.5,
        "cycle_id": "cycle-1",
    }
    base.update(overrides)
    return SessionConfig.from_dict(base)


class TestOverlapCorrectness:
    def test_overlapping_windows_neither_duplicate_nor_drop(self):
        session = StreamingSession(1, _test_config())
        window1 = _words([f"w{i}" for i in range(12)], 0.0)
        assert session.commit_window(window1, 12.0)[0] == " ".join(f"w{i}" for i in range(10))
        window2 = _words([f"w{i}" for i in range(9, 17)], 9.0)
        assert session.commit_window(window2, 17.0)[0] == "w10 w11 w12 w13 w14"
        assert session.committed_text.split() == [f"w{i}" for i in range(15)]
        window3 = _words([f"w{i}" for i in range(14, 22)], 14.0)
        assert session.commit_window(window3, 22.0)[0] == "w15 w16 w17 w18 w19"
        assert session.committed_text.split() == [f"w{i}" for i in range(20)]

    def test_exact_redelivery_is_dropped(self):
        session = StreamingSession(1, _test_config())
        session.commit_window(_words(["hello", "world"], 0.0), 12.0)
        assert session.commit_window(_words(["hello", "world"], 0.0), 17.0) == ("", [])
        assert session.committed_text == "hello world"

    def test_tail_merge_keeps_only_words_past_the_boundary(self):
        session = StreamingSession(1, _test_config())
        session.commit_window(_words(["a", "b", "c"], 0.0), 12.0)
        merged = session.commit_tail(_words(["b", "c", "d"], 1.0))
        assert merged == "a b c d"


class TestSessionPushOrder:
    def test_out_of_order_push_is_an_error_and_keeps_state(self):
        session = StreamingSession(7, _test_config())
        assert session.append_chunk(1, _audio_b64(1.0)) is not None
        assert session.duration_seconds == 0.0
        assert session.append_chunk(0, _audio_b64(1.0)) is None
        assert session.append_chunk(1, _audio_b64(1.0)) is None
        assert session.duration_seconds == 2.0

    def test_bad_payload_is_an_error(self):
        session = StreamingSession(7, _test_config())
        assert session.append_chunk(0, "!!!not-base64!!!") is not None
        assert session.append_chunk(0, base64.b64encode(b"odd").decode("ascii")) is not None

    def test_first_window_gated_until_min_audio(self):
        session = StreamingSession(7, _test_config(min_first_chunk_seconds=6.0))
        assert session.append_chunk(0, _audio_b64(2.0)) is None
        assert session.due_window() is None
        assert session.append_chunk(1, _audio_b64(5.0)) is None
        due = session.due_window()
        assert due is not None
        assert due[0] == 0.0


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


class _LiveWS(_ScriptedWS):
    """Fake socket fed frame-by-frame so the test can wait between frames."""

    def __init__(self, auth_frame: str) -> None:
        super().__init__(auth_frame, [])
        self.queue: asyncio.Queue = asyncio.Queue()

    async def _iterate(self):
        while True:
            item = await self.queue.get()
            if isinstance(item, BaseException):
                raise item
            yield item


async def _wait_for(predicate, timeout: float = 5.0):
    """Poll until predicate holds; the loop must pump scheduled tasks meanwhile."""
    import time as _time

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out waiting for condition")


def _open_frame(session_id: int, config: dict | None = None) -> str:
    return json.dumps({"cmd": "streaming_session_open", "id": session_id, "data": {"config": config or {}}})


def _push_frame(session_id: int, index: int, payload_b64: str) -> str:
    return json.dumps(
        {"cmd": "streaming_session_push", "id": session_id, "data": {"index": index, "payload_b64": payload_b64}}
    )


def _finalize_frame(session_id: int) -> str:
    return json.dumps({"cmd": "streaming_session_finalize", "id": session_id, "data": {}})


def _small_config() -> dict:
    return {
        "sample_rate": 16000,
        "chunk_seconds": 2.0,
        "step_seconds": 1.0,
        "min_first_chunk_seconds": 1.0,
        "left_overlap_seconds": 0.5,
        "right_guard_seconds": 0.5,
        "cycle_id": "cycle-9",
    }


def _script_words(offset_words: dict[float, str]):
    def _fake(raw: bytes, sample_rate: int, offset_seconds: float, language: str | None) -> list[Word]:
        return [Word(text, offset, offset + 0.4) for offset, text in sorted(offset_words.items())]

    return _fake


class TestStreamingSessionFrames:
    async def test_open_acks_and_rejects_bad_config(self, monkeypatch):
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")
        auth = json.dumps({"type": "auth", "token": "tok"})
        ws = _ScriptedWS(
            auth,
            [_open_frame(3, _small_config()), _open_frame(4, {"sample_rate": "fast"}), _DoneError()],
        )
        await ws_server._handle_connection(
            ws, prewarm_ran=False, stop_event=asyncio.Event(), shutdown_timer=ws_server._ShutdownTimer()
        )
        bodies = [json.loads(f) for f in ws.sent]
        assert {"type": "streaming_session_opened", "id": 3, "data": {"opened": True}} in bodies
        errors = [b for b in bodies if b.get("type") == "streaming_session_result" and b.get("id") == 4]
        assert len(errors) == 1 and errors[0]["data"]["error"] is not None

    async def test_unknown_session_is_a_structured_error_never_silence(self, monkeypatch):
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")
        auth = json.dumps({"type": "auth", "token": "tok"})
        ws = _ScriptedWS(auth, [_push_frame(77, 0, ""), _finalize_frame(78), _DoneError()])
        await ws_server._handle_connection(
            ws, prewarm_ran=False, stop_event=asyncio.Event(), shutdown_timer=ws_server._ShutdownTimer()
        )
        bodies = [json.loads(f) for f in ws.sent]
        by_id = {b.get("id"): b for b in bodies if b.get("type") == "streaming_session_result"}
        assert set(by_id) == {77, 78}
        assert all(b["data"]["error"] for b in by_id.values())

    async def test_push_drives_partial_then_finalize_merges(self, monkeypatch):
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")
        monkeypatch.setattr(
            ws_server, "transcribe_window_words", _script_words({0.0: "hello", 0.5: "world", 1.4: "again"})
        )
        auth = json.dumps({"type": "auth", "token": "tok"})
        ws = _LiveWS(auth)
        task = asyncio.ensure_future(
            ws_server._handle_connection(
                ws, prewarm_ran=False, stop_event=asyncio.Event(), shutdown_timer=ws_server._ShutdownTimer()
            )
        )
        await ws.queue.put(_open_frame(5, _small_config()))
        await _wait_for(
            lambda: any(json.loads(f).get("type") == "streaming_session_opened" for f in ws.sent),
        )
        await ws.queue.put(_push_frame(5, 0, _audio_b64(2.0)))
        await _wait_for(
            lambda: any(json.loads(f).get("type") == "transcription_partial" for f in ws.sent),
        )
        await ws.queue.put(_finalize_frame(5))
        await ws.queue.put(_DoneError())
        await task
        await asyncio.sleep(0.5)
        bodies = [json.loads(f) for f in ws.sent]
        partials = [b for b in bodies if b.get("type") == "transcription_partial" and b.get("id") == 5]
        assert len(partials) == 1
        partial = partials[0]["data"]
        assert partial["cycle_id"] == "cycle-9" and partial["is_final"] is False
        assert partial["text"] == "hello world"
        assert [w["word"] for w in partial["words"]] == ["hello", "world"]
        finals = [b for b in bodies if b.get("type") == "streaming_session_result" and b.get("id") == 5]
        assert len(finals) == 1
        assert finals[0]["data"] == {"text": "hello world again", "error": None}

    async def test_finalize_tears_down_the_session(self, monkeypatch):
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")
        monkeypatch.setattr(ws_server, "transcribe_window_words", _script_words({0.0: "hi"}))
        auth = json.dumps({"type": "auth", "token": "tok"})
        ws = _LiveWS(auth)
        task = asyncio.ensure_future(
            ws_server._handle_connection(
                ws, prewarm_ran=False, stop_event=asyncio.Event(), shutdown_timer=ws_server._ShutdownTimer()
            )
        )
        await ws.queue.put(_open_frame(6, _small_config()))
        await _wait_for(
            lambda: any(json.loads(f).get("type") == "streaming_session_opened" for f in ws.sent),
        )
        await ws.queue.put(_push_frame(6, 0, _audio_b64(2.0)))
        await _wait_for(
            lambda: any(json.loads(f).get("type") == "transcription_partial" for f in ws.sent),
        )
        await ws.queue.put(_finalize_frame(6))
        await ws.queue.put(_finalize_frame(6))
        await ws.queue.put(_DoneError())
        await task
        await asyncio.sleep(0.5)
        bodies = [json.loads(f) for f in ws.sent]
        finals = [b for b in bodies if b.get("type") == "streaming_session_result" and b.get("id") == 6]
        assert len(finals) == 2
        assert sorted(f["data"]["text"] for f in finals) == ["", "hi"]
        assert [f["data"]["error"] for f in finals if f["data"]["text"] == ""] == ["unknown streaming session"]

    async def test_abort_mid_session_drops_state(self, monkeypatch):
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")

        def _slow(raw: bytes, sample_rate: int, offset_seconds: float, language: str | None) -> list[Word]:
            import time as _time

            _time.sleep(0.3)
            return [Word("late", offset_seconds, offset_seconds + 0.4)]

        monkeypatch.setattr(ws_server, "transcribe_window_words", _slow)
        auth = json.dumps({"type": "auth", "token": "tok"})
        ws = _ScriptedWS(
            auth,
            [
                _open_frame(9, _small_config()),
                _push_frame(9, 0, _audio_b64(2.0)),
                json.dumps({"cmd": "abort_request", "id": 9, "data": {}}),
                _push_frame(9, 1, _audio_b64(1.0)),
                _DoneError(),
            ],
        )
        await ws_server._handle_connection(
            ws, prewarm_ran=False, stop_event=asyncio.Event(), shutdown_timer=ws_server._ShutdownTimer()
        )
        await asyncio.sleep(0.8)
        bodies = [json.loads(f) for f in ws.sent]
        assert {"type": "abort_ack", "id": 9, "data": {"aborted": True}} in bodies
        late = [b for b in bodies if b.get("type") == "streaming_session_result" and b.get("id") == 9]
        assert len(late) == 1 and late[0]["data"]["error"] == "request aborted"
        assert [b for b in bodies if b.get("type") == "transcription_partial"] == []

    async def test_finalize_without_committed_audio_uses_batch(self, monkeypatch):
        monkeypatch.setenv(IPC_TOKEN_ENV_VAR, "tok")

        class _BatchOnly:
            def transcribe_array(self, audio, sample_rate, language):
                return {"text": "batch text", "error": None}

        monkeypatch.setattr("voice_typer.worker._transcribe.get_transcriber", lambda: _BatchOnly())
        auth = json.dumps({"type": "auth", "token": "tok"})
        ws = _ScriptedWS(auth, [_open_frame(11, _small_config()), _finalize_frame(11), _DoneError()])
        await ws_server._handle_connection(
            ws, prewarm_ran=False, stop_event=asyncio.Event(), shutdown_timer=ws_server._ShutdownTimer()
        )
        await asyncio.sleep(0.5)
        bodies = [json.loads(f) for f in ws.sent]
        finals = [b for b in bodies if b.get("type") == "streaming_session_result" and b.get("id") == 11]
        assert len(finals) == 1
        assert finals[0]["data"]["text"] == "batch text"
