"""WAV measurement helpers for the TTS subsystem.

This module exists so engine adapters never import an audio library directly:
one place converts a rendered file into the duration/sample-rate pair every
result carries.
"""

from __future__ import annotations

from pathlib import Path

import soundfile as sf  # type: ignore[import-untyped]

from voice_typer.server.tts.types import TtsError


def probe_wav(path: Path) -> tuple[float, int]:
    """Return ``(duration_seconds, sample_rate)`` for a rendered WAV.

    A zero-byte or malformed file is an engine failure, not an empty result:
    both runtimes write a WAV even when they produce silence, so a file that
    cannot be read means the render did not actually happen.
    """
    if not path.is_file() or path.stat().st_size == 0:
        raise TtsError(f"engine produced no audio at {path}")
    try:
        info = sf.info(str(path))
    except Exception as exc:  # soundfile raises its own error family
        raise TtsError(f"unreadable WAV at {path}: {exc}") from exc
    if info.frames <= 0:
        raise TtsError(f"WAV at {path} has zero frames")
    return float(info.frames) / float(info.samplerate), int(info.samplerate)
