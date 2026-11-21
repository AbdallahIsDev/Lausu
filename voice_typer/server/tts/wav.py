"""WAV measurement helpers for the TTS subsystem.

This module exists so engine adapters never import an audio library directly:
one place converts a rendered file into the duration/sample-rate pair every
result carries.
"""

from __future__ import annotations

import wave
from pathlib import Path

from voice_typer.server.tts.types import TtsError


def probe_wav(path: Path) -> tuple[float, int]:
    """Return ``(duration_seconds, sample_rate)`` for a rendered WAV.

    A zero-byte or malformed file is an engine failure, not an empty result:
    both runtimes write a WAV even when they produce silence, so a file that
    cannot be read means the render did not actually happen.
    """
    if not path.is_file() or path.stat().st_size == 0:
        raise TtsError(f"engine produced no audio at {path}")
    # wave is stdlib: probing a rendered WAV needs no third-party audio stack.
    # soundfile stays a fallback for WAV flavours wave cannot open, never a
    # hard dependency (macOS arm64 excludes it from the lock file).
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            sample_rate = handle.getframerate()
    except (wave.Error, EOFError) as exc:
        try:
            import soundfile as sf  # type: ignore[import-untyped]
        except ImportError:
            raise TtsError(f"unreadable WAV at {path}: {exc}") from exc
        try:
            info = sf.info(str(path))
        except Exception as sf_exc:  # soundfile raises its own error family
            raise TtsError(f"unreadable WAV at {path}: {sf_exc}") from sf_exc
        frames, sample_rate = info.frames, info.samplerate
    if frames <= 0:
        raise TtsError(f"WAV at {path} has zero frames")
    return float(frames) / float(sample_rate), int(sample_rate)
