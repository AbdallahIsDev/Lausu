"""Playback of synthesized speech on the default output device.

This module exists so the TTS service can speak a rendered WAV without the
renderer or the recording path: imports stay inside the function because a
headless test or a machine with no output device must not fail at import time.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from voice_typer.server.tts.types import TtsError

log = logging.getLogger(__name__)

#: Serializes playback so two replies never talk over each other.
_playback_lock = threading.Lock()


def play_wav(path: Path) -> float:
    """Play ``path`` to completion; return its duration in seconds."""
    try:
        import sounddevice as sd
        import soundfile as sf
    except Exception as exc:  # pragma: no cover - dependency is in base install
        raise TtsError(f"audio playback unavailable: {exc}") from exc

    data, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    duration = len(data) / float(sample_rate)
    with _playback_lock:
        try:
            sd.play(data, sample_rate)
            sd.wait()
        except Exception as exc:
            raise TtsError(f"could not play synthesized speech: {exc}") from exc
    log.debug("[TTS] played %.2fs of audio from %s", duration, path)
    return duration


def stop_playback() -> None:
    """Interrupt any in-flight playback (best effort)."""
    try:
        import sounddevice as sd

        sd.stop()
    except Exception:
        log.debug("[TTS] stop_playback failed", exc_info=True)
