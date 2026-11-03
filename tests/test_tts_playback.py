"""Asynchronous playback: one clip at a time, stoppable, never blocks the caller."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from voice_typer.server.tts import playback


class _FakeStream:
    """sounddevice/soundfile stand-in with event-driven completion."""

    def __init__(self) -> None:
        self.frames = 12_000
        self.sample_rate = 24_000
        self.play_calls: list[tuple[int, int]] = []
        self.stop_calls = 0
        self.fail_with: Exception | None = None
        self._started = threading.Event()
        self._release = threading.Event()

    # sounddevice surface
    def play(self, data: np.ndarray, sample_rate: int) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.play_calls.append((len(data), sample_rate))
        self._started.set()

    def wait(self) -> None:
        self._started.wait(timeout=5.0)
        self._release.wait(timeout=5.0)
        self._release.clear()

    def stop(self) -> None:
        self.stop_calls += 1
        self._release.set()

    def finish_naturally(self) -> None:
        self._started.set()
        self._release.set()

    # soundfile surface
    def read(self, _path: str, *, dtype: str, always_2d: bool):
        return np.zeros((self.frames, 1), dtype=np.float32), self.sample_rate


@pytest.fixture()
def stream(monkeypatch: pytest.MonkeyPatch) -> _FakeStream:
    fake = _FakeStream()
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    monkeypatch.setitem(sys.modules, "soundfile", fake)
    playback.shutdown_playback()
    # shutdown calls the fake's stop(), which would make the next wait()
    # return instantly; start every test from a clean, blocked stream.
    fake._started.clear()
    fake._release.clear()
    yield fake
    playback.shutdown_playback()


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_start_playback_returns_before_the_clip_ends(stream: _FakeStream) -> None:
    result: list[tuple[bool, str | None]] = []

    duration = playback.start_playback(Path("clip.wav"), on_finished=lambda i, e: result.append((i, e)))

    assert duration == pytest.approx(0.5, abs=0.01)
    assert stream.play_calls == [(12_000, 24_000)]
    # Still in flight: the caller was not blocked and the callback has not run.
    assert result == []
    stream.finish_naturally()
    assert _wait_for(lambda: bool(result))
    assert result == [(False, None)]


def test_stop_playback_interrupts_and_reports(stream: _FakeStream) -> None:
    result: list[tuple[bool, str | None]] = []
    playback.start_playback(Path("clip.wav"), on_finished=lambda i, e: result.append((i, e)))

    assert _wait_for(lambda: bool(stream.play_calls))
    assert playback.stop_playback() is True

    assert _wait_for(lambda: bool(result))
    assert result == [(True, None)]
    assert stream.stop_calls >= 1


def test_a_device_error_is_reported_not_raised(stream: _FakeStream) -> None:
    stream.fail_with = RuntimeError("PortAudio: no default output device")
    result: list[tuple[bool, str | None]] = []

    playback.start_playback(Path("clip.wav"), on_finished=lambda i, e: result.append((i, e)))

    assert _wait_for(lambda: bool(result))
    interrupted, error = result[0]
    assert interrupted is False
    assert error is not None and "no default output" in error


def test_play_wav_still_blocks_and_reports_duration(stream: _FakeStream) -> None:
    stream.finish_naturally()

    assert playback.play_wav(Path("clip.wav")) == pytest.approx(0.5, abs=0.01)
    assert stream.play_calls == [(12_000, 24_000)]


def test_is_playing_tracks_the_worker(stream: _FakeStream) -> None:
    playback.start_playback(Path("clip.wav"))
    assert _wait_for(lambda: playback.is_playing())
    playback.stop_playback()
    assert _wait_for(lambda: not playback.is_playing())


def test_unreadable_audio_raises_before_playback(stream: _FakeStream) -> None:
    def boom(_path: str, *, dtype: str, always_2d: bool):
        raise OSError("bad wav")

    stream.read = boom  # type: ignore[method-assign]

    with pytest.raises(playback.PlaybackError, match="unreadable audio"):
        playback.start_playback(Path("clip.wav"))


def test_import_failure_is_a_playback_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name in {"sounddevice", "soundfile"}:
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "sounddevice", raising=False)
    monkeypatch.delitem(sys.modules, "soundfile", raising=False)

    with pytest.raises(playback.PlaybackError):
        playback.play_wav(Path("clip.wav"))
