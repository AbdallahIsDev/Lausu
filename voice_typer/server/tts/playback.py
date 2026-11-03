"""Playback of synthesized speech on the default output device.

This module exists so the TTS service can speak a rendered WAV without the
renderer or the recording path. Playback is asynchronous: the caller returns as
soon as the clip starts, so the Models page's single control can show "stop"
while audio is still in flight. Imports stay inside the functions because a
headless test or a machine with no output device must not fail at import time.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from voice_typer.server.tts.types import TtsError

log = logging.getLogger(__name__)

#: Serializes playback so two replies never talk over each other.
_playback_lock = threading.Lock()
#: Set while a clip should keep playing; cleared to interrupt it.
_stop_event = threading.Event()
_thread: threading.Thread | None = None
_thread_lock = threading.Lock()

#: PortAudio wording when there is no usable output device.
_NO_OUTPUT_HINTS = (
    "no default output",
    "no output device",
    "invalid device",
    "device unavailable",
    "error opening",
    "portaudio",
)


class PlaybackError(TtsError):
    """The clip could not be played (device missing or driver refused it)."""


def _classify(message: str) -> bool:
    """True when the failure is a missing/unusable output device."""
    lowered = message.lower()
    return any(hint in lowered for hint in _NO_OUTPUT_HINTS)


def _import_playback():
    """Import the audio stack lazily so headless imports stay cheap."""
    try:
        import sounddevice as sd
        import soundfile as sf  # type: ignore[import-untyped]
    except Exception as exc:  # pragma: no cover - dependency is in base install
        raise PlaybackError(f"audio playback unavailable: {exc}") from exc
    return sd, sf


def _read(path: Path):
    _sd, sf = _import_playback()
    try:
        data, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception as exc:
        raise PlaybackError(f"unreadable audio at {path}: {exc}") from exc
    return data, float(sample_rate)


def play_wav(path: Path) -> float:
    """Play ``path`` to completion; return its duration in seconds."""
    sd, _sf = _import_playback()
    data, sample_rate = _read(path)
    duration = float(len(data) / sample_rate)
    with _playback_lock:
        try:
            sd.play(data, sample_rate)
            sd.wait()
        except Exception as exc:
            raise PlaybackError(f"could not play synthesized speech: {exc}") from exc
    log.debug("[TTS] played %.2fs of audio from %s", duration, path)
    return duration


def start_playback(
    path: Path,
    *,
    on_finished: Callable[[bool, str | None], None] | None = None,
) -> float:
    """Start ``path`` on a worker thread and return its duration immediately.

    ``on_finished(interrupted, error)`` runs once the clip stops: ``interrupted``
    is True for a ``stop_playback()`` call, ``error`` is a message when the
    device refused the clip (never raised into the caller's thread).
    """
    global _thread
    sd, _sf = _import_playback()
    data, sample_rate = _read(path)
    duration = float(len(data) / sample_rate)
    _stop_event.clear()

    def _run() -> None:
        interrupted = False
        error: str | None = None
        with _playback_lock:
            try:
                if not _stop_event.is_set():
                    sd.play(data, sample_rate)
                    sd.wait()
            except Exception as exc:
                interrupted = _stop_event.is_set()
                if not interrupted:
                    error = f"{type(exc).__name__}: {exc}"
                    log.warning("[TTS] playback failed: %s", error)
            finally:
                interrupted = interrupted or _stop_event.is_set()
                _stop_event.clear()
        if on_finished is not None:
            try:
                on_finished(interrupted, error)
            except Exception:
                log.debug("[TTS] playback callback failed", exc_info=True)

    # daemon=True: a stuck audio device must never keep the app alive on quit.
    thread = threading.Thread(target=_run, name="tts-playback", daemon=True)
    with _thread_lock:
        _thread = thread
    thread.start()
    log.debug("[TTS] playback started (%.2fs of audio)", duration)
    return duration


def stop_playback() -> bool:
    """Interrupt any in-flight playback; True when a clip was active."""
    with _thread_lock:
        active = _thread is not None and _thread.is_alive()
    _stop_event.set()
    try:
        import sounddevice as sd

        sd.stop()
    except Exception:
        log.debug("[TTS] stop_playback failed", exc_info=True)
    log.debug("[TTS] playback stop requested (active=%s)", active)
    return active


def shutdown_playback(grace_s: float = 2.0) -> None:
    """Stop playback and wait briefly for the worker (app teardown)."""
    global _thread
    stop_playback()
    with _thread_lock:
        thread = _thread
        _thread = None
    if thread is not None and thread.is_alive():
        thread.join(timeout=grace_s)


def is_playing() -> bool:
    """True while a playback worker is alive."""
    with _thread_lock:
        return _thread is not None and _thread.is_alive()


__all__ = [
    "PlaybackError",
    "is_playing",
    "play_wav",
    "shutdown_playback",
    "start_playback",
    "stop_playback",
]
