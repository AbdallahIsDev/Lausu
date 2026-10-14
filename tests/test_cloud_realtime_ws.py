"""WS IO tests for the realtime burst-append session (fake transport only)."""

from __future__ import annotations

import asyncio
import json
import threading

import pytest
from voice_typer.server.asr_errors import (
    CloudAuthError,
    CloudEmptyResponseError,
    CloudEngineError,
    CloudNetworkError,
)
from voice_typer.server.cloud._realtime import (
    WS_MAX_MESSAGE_BYTES,
    WS_REALTIME_URL,
    build_append_envelope,
    build_commit_envelope,
    build_session_update,
)
from voice_typer.server.cloud._realtime_ws import _OPEN_TIMEOUT_S, transcribe_via_realtime


@pytest.fixture(autouse=True)
def _allow_url(monkeypatch):
    from voice_typer.server import cloud_engines

    calls: list[str] = []
    monkeypatch.setattr(
        cloud_engines,
        "assert_url_allowed",
        lambda url, **kwargs: calls.append(url),
    )
    return calls


class FakeWS:
    def __init__(self, script):
        self._script = list(script)
        self.sent: list[str] = []
        self.close_called = False

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        if not self._script:
            await asyncio.sleep(60)
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        # Real WS frames arrive as text; serialize dicts the same way.
        if isinstance(item, dict):
            return json.dumps(item)
        return item

    async def close(self):
        self.close_called = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        self.close_called = True
        return False


class FakeAuthCloseError(Exception):
    def __init__(self, code=4010):
        super().__init__(f"closing connection: {code} unauthorized")
        self.code = code


class FakeHandshakeAuthError(Exception):
    def __init__(self):
        super().__init__("handshake failed with status 401")
        self.status_code = 401


def _connect_factory(ws, record):
    def _connect(url, **kwargs):
        record["url"] = url
        record["kwargs"] = kwargs
        return ws

    return _connect


def _run(frames, script, **kwargs):
    ws = FakeWS(script)
    record: dict = {}
    result = transcribe_via_realtime(
        api_key="test-key",
        model="gpt-live-transcribe",
        pcm24k_frames=frames,
        connect=_connect_factory(ws, record),
        **kwargs,
    )
    return result, ws, record


def test_url_headers_and_allowlist(_allow_url):
    _, _, record = _run(
        [b"\x01\x02"],
        [{"type": "conversation.item.input_audio_transcription.completed", "transcript": "hi"}],
    )
    assert record["url"] == WS_REALTIME_URL
    assert record["kwargs"]["additional_headers"] == {
        "Authorization": "Bearer test-key",
        "OpenAI-Beta": "realtime=v1",
    }
    assert record["kwargs"]["max_size"] == WS_MAX_MESSAGE_BYTES
    assert _allow_url == ["https://api.openai.com/v1/realtime?intent=transcription"]


def test_session_update_frames_and_commit_order():
    frames = [b"\x01\x02", b"\x03\x04\x05"]
    _, ws, _ = _run(
        frames,
        [{"type": "conversation.item.input_audio_transcription.completed", "transcript": "hi"}],
    )
    assert json.loads(ws.sent[0]) == build_session_update("gpt-live-transcribe")
    assert [json.loads(s) for s in ws.sent[1:-1]] == [
        build_append_envelope(f) for f in frames
    ]
    assert json.loads(ws.sent[-1]) == build_commit_envelope()


def test_deltas_buffered_completed_wins():
    result, _, _ = _run(
        [b"\x01"],
        [
            {"type": "session.updated"},
            {
                "type": "conversation.item.input_audio_transcription.delta",
                "delta": "stale ",
            },
            {
                "type": "conversation.item.input_audio_transcription.delta",
                "delta": "part ",
            },
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "transcript": "final text",
            },
        ],
    )
    assert result == "final text"


def test_completed_without_deltas():
    result, _, _ = _run(
        [b"\x01"],
        [{"type": "conversation.item.input_audio_transcription.completed", "transcript": "solo"}],
    )
    assert result == "solo"


def test_completed_empty_raises():
    with pytest.raises(CloudEmptyResponseError):
        _run(
            [b"\x01"],
            [{"type": "conversation.item.input_audio_transcription.completed"}],
        )


def test_failed_raises():
    with pytest.raises(CloudEngineError):
        _run(
            [b"\x01"],
            [{"type": "conversation.item.input_audio_transcription.failed"}],
        )


def test_auth_close_raises():
    with pytest.raises(CloudAuthError):
        _run([b"\x01"], [FakeAuthCloseError()])


def test_handshake_auth_raises(_allow_url):

    def _connect(url, **kwargs):
        raise FakeHandshakeAuthError()

    with pytest.raises(CloudAuthError):
        transcribe_via_realtime(
            api_key="bad-key",
            model="gpt-live-transcribe",
            pcm24k_frames=[b"\x01"],
            connect=_connect,
        )
    assert _allow_url, "allowlist must run before connect"


def test_stall_hits_overall_deadline():
    with pytest.raises(CloudNetworkError):
        _run([b"\x01"], [], overall_timeout_s=0.3)


def test_handshake_carries_open_timeout():
    _, _, record = _run(
        [b"\x01\x02"],
        [{"type": "conversation.item.input_audio_transcription.completed", "transcript": "hi"}],
    )
    assert record["kwargs"]["open_timeout"] == _OPEN_TIMEOUT_S


def test_hung_handshake_bounded_by_join(monkeypatch):
    import voice_typer.server.cloud._realtime_ws as realtime_ws

    class HangingWS(FakeWS):
        async def __aenter__(self):
            await asyncio.sleep(5)
            return self

    monkeypatch.setattr(realtime_ws, "_JOIN_SLACK_S", 0.2)
    monkeypatch.setattr(realtime_ws, "_OPEN_TIMEOUT_S", 0.2)
    ws = HangingWS([])
    with pytest.raises(CloudNetworkError, match="timed out"):
        transcribe_via_realtime(
            api_key="test-key",
            model="gpt-live-transcribe",
            pcm24k_frames=[b"\x01\x02"],
            connect=_connect_factory(ws, {}),
            overall_timeout_s=0.5,
        )


def test_listed_auth_close_codes_raise():
    for code in (4001, 4010, 4401):
        with pytest.raises(CloudAuthError):
            _run([b"\x01"], [FakeAuthCloseError(code)])


def test_malformed_binary_frame_skipped():
    result, _, _ = _run(
        [b"\x01\x02"],
        [
            b"\xff\xfe\x00not-utf8",
            {"type": "conversation.item.input_audio_transcription.completed", "transcript": "hi"},
        ],
    )
    assert result == "hi"


def test_hung_send_bounded():
    class HangingSendWS(FakeWS):
        async def send(self, data):
            await asyncio.sleep(60)

    ws = HangingSendWS(
        [{"type": "conversation.item.input_audio_transcription.completed", "transcript": "hi"}]
    )
    with pytest.raises(CloudNetworkError, match="timed out"):
        transcribe_via_realtime(
            api_key="test-key",
            model="gpt-live-transcribe",
            pcm24k_frames=[b"\x01\x02"],
            connect=_connect_factory(ws, {}),
            overall_timeout_s=0.5,
        )


def test_abort_closes_and_raises():
    event = threading.Event()
    timer = threading.Timer(0.1, event.set)
    timer.start()
    try:
        with pytest.raises(CloudEngineError, match="abort"):
            _run([b"\x01"], [], abort_event=event, overall_timeout_s=30.0)
    finally:
        timer.cancel()


def test_abort_close_called():
    event = threading.Event()
    event.set()
    ws = FakeWS([])
    record: dict = {}
    with pytest.raises(CloudEngineError):
        transcribe_via_realtime(
            api_key="test-key",
            model="gpt-live-transcribe",
            pcm24k_frames=[b"\x01"],
            abort_event=event,
            connect=_connect_factory(ws, record),
            overall_timeout_s=30.0,
        )
    assert ws.close_called is True


def test_empty_frames_raise_before_connect():
    record: dict = {}
    ws = FakeWS([])
    with pytest.raises(CloudEmptyResponseError):
        transcribe_via_realtime(
            api_key="test-key",
            model="gpt-live-transcribe",
            pcm24k_frames=[b"", b""],
            connect=_connect_factory(ws, record),
        )
    assert record == {}
    assert ws.sent == []


def test_oversize_message_raises():
    with pytest.raises(CloudEngineError):
        _run([b"\x01"], ["x" * (WS_MAX_MESSAGE_BYTES + 1)])
