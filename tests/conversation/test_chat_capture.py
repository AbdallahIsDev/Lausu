"""ChatCapture: taps the level monitor's single stream and its bounded buffer.

No test opens an audio device: ``is_monitoring`` / ``start_monitoring`` are
patched on the capture module (the seam the class calls), and the monitor state
is driven directly. The worker's own cap branch is exercised through
``_process_level_chunk`` with a shrunk cap, so the test never waits 30 s.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from voice_typer.server.conversation import capture as capture_mod
from voice_typer.server.conversation.capture import ChatCapture
from voice_typer.server.level_monitor import worker as worker_mod
from voice_typer.server.level_monitor._state import _state

_CHAT_FIELDS = (
    "_chat_capture_active",
    "_chat_capture_chunks",
    "_chat_capture_cap_warned",
)


@pytest.fixture(autouse=True)
def _isolate_monitor_state():
    """Snapshot + restore the monitor fields these tests write."""
    saved: dict[str, Any] = {
        "chat_active": _state._chat_capture_active,
        "chat_warned": _state._chat_capture_cap_warned,
        "sample_rate": _state._monitor_sample_rate,
        "monitor_active": _state._monitor_active,
        "processor": _state._level_processor,
        "preview": _state._live_preview_active,
        "cap": _state._TEST_MAX_CHUNKS_CAP,
        "test_mode": _state._test_mode,
        "test_duration": _state._test_duration,
        "test_start": _state._test_start_time,
        "test_chunks": list(_state._test_chunks),
        "test_raw": list(_state._test_raw_chunks),
        "test_filtered": list(_state._test_filtered_chunks),
    }
    _state._chat_capture_chunks.clear()
    _state._chat_capture_active = False
    _state._chat_capture_cap_warned = False
    yield
    _state._chat_capture_chunks.clear()
    _state._chat_capture_active = saved["chat_active"]
    _state._chat_capture_cap_warned = saved["chat_warned"]
    _state._monitor_sample_rate = saved["sample_rate"]
    _state._monitor_active = saved["monitor_active"]
    _state._level_processor = saved["processor"]
    _state._live_preview_active = saved["preview"]
    _state._TEST_MAX_CHUNKS_CAP = saved["cap"]
    _state._test_mode = saved["test_mode"]
    _state._test_duration = saved["test_duration"]
    _state._test_start_time = saved["test_start"]
    _state._test_chunks.clear()
    _state._test_chunks.extend(saved["test_chunks"])
    _state._test_raw_chunks.clear()
    _state._test_raw_chunks.extend(saved["test_raw"])
    _state._test_filtered_chunks.clear()
    _state._test_filtered_chunks.extend(saved["test_filtered"])


def test_start_stop_returns_the_captured_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_mod, "is_monitoring", lambda: True)
    _state._monitor_sample_rate = 16000
    capture = ChatCapture()

    assert capture.start("mic-1") == 16000
    assert _state._chat_capture_active is True
    chunk = np.full(512, 0.25, dtype=np.float32)
    _state._chat_capture_chunks.append(chunk.copy())
    _state._chat_capture_chunks.append(chunk.copy())

    audio = capture.stop()

    assert audio.dtype == np.float32
    assert audio.shape == (1024,)
    assert np.allclose(audio, 0.25)
    assert _state._chat_capture_active is False
    assert len(_state._chat_capture_chunks) == 0


def test_cap_stops_capture_and_keeps_what_was_captured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_mod, "is_monitoring", lambda: True)
    _state._monitor_sample_rate = 16000
    _state._monitor_active = True
    _state._level_processor = None
    _state._live_preview_active = False
    # The real cap is 30 s of 48 kHz chunks; shrink it so the branch is
    # reachable without feeding 30 s of audio.
    _state._TEST_MAX_CHUNKS_CAP = 3
    capture = ChatCapture()
    capture.start()

    block = np.full(512, 0.1, dtype=np.float32)
    for _ in range(5):
        worker_mod._process_level_chunk(block, None)

    assert _state._chat_capture_active is False, "the cap must stop the capture"
    audio = capture.stop()
    assert audio.shape == (3 * 512,), "everything captured before the cap is kept"


def test_cap_is_thirty_seconds_of_chunks() -> None:
    # Pins the '30 s' half of the contract the shrunk-cap test above exercises.
    assert int(30 * 48000 / 512) + 1 == _state._TEST_MAX_CHUNKS_CAP


def test_capture_never_touches_mic_test_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_mod, "is_monitoring", lambda: True)
    _state._monitor_sample_rate = 16000
    before = (
        len(_state._test_chunks),
        len(_state._test_raw_chunks),
        len(_state._test_filtered_chunks),
        _state._test_mode,
        _state._test_duration,
        _state._test_start_time,
    )
    capture = ChatCapture()

    capture.start()
    _state._chat_capture_chunks.append(np.zeros(64, dtype=np.float32))
    capture.stop()

    after = (
        len(_state._test_chunks),
        len(_state._test_raw_chunks),
        len(_state._test_filtered_chunks),
        _state._test_mode,
        _state._test_duration,
        _state._test_start_time,
    )
    assert after == before, "chat capture must never write a _test_* field (C-MIC-18)"


def test_start_does_not_open_a_second_stream_while_monitoring(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str | None] = []

    def fake_start_monitoring(mic_id: str | None = None) -> dict[str, Any]:
        opened.append(mic_id)
        return {"success": True}

    monkeypatch.setattr(capture_mod, "is_monitoring", lambda: True)
    monkeypatch.setattr(capture_mod, "start_monitoring", fake_start_monitoring)
    _state._monitor_sample_rate = 16000
    capture = ChatCapture()

    capture.start("mic-1")

    assert opened == [], "an already-running monitor owns the only InputStream"
    capture.cancel()


def test_start_opens_the_monitor_when_it_is_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str | None] = []

    def fake_start_monitoring(mic_id: str | None = None) -> dict[str, Any]:
        opened.append(mic_id)
        _state._monitor_sample_rate = 16000
        return {"success": True}

    monkeypatch.setattr(capture_mod, "is_monitoring", lambda: False)
    monkeypatch.setattr(capture_mod, "start_monitoring", fake_start_monitoring)
    capture = ChatCapture()

    assert capture.start("mic-2") == 16000
    assert opened == ["mic-2"], "the chat path arms the monitor, it never opens its own stream"
    capture.cancel()


def test_start_raises_when_the_monitor_cannot_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_mod, "is_monitoring", lambda: False)
    monkeypatch.setattr(capture_mod, "start_monitoring", lambda mic_id=None: {"success": False})
    capture = ChatCapture()

    with pytest.raises(RuntimeError):
        capture.start()

    assert _state._chat_capture_active is False


def test_cancel_drops_the_buffer_without_decoding_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_mod, "is_monitoring", lambda: True)
    _state._monitor_sample_rate = 16000
    capture = ChatCapture()
    capture.start()
    _state._chat_capture_chunks.append(np.zeros(128, dtype=np.float32))

    capture.cancel()

    assert _state._chat_capture_active is False
    assert len(_state._chat_capture_chunks) == 0
