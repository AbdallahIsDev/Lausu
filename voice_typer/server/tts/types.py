"""Shared contracts for the local text-to-speech subsystem.

This module exists so that every TTS engine speaks one request/result shape and
the compare harness never branches on engine identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

#: Sample rate every engine in this subsystem must emit (both models decode to
#: 22.05 kHz for Magpie/NanoCodec and 44.1 kHz for Audio8; callers resample or
#: accept per-engine rates, so the field is reported, never assumed).
DEFAULT_SAMPLE_RATE = 24_000


class TtsError(RuntimeError):
    """Raised when an engine cannot synthesize (missing pack, crash, timeout)."""


@dataclass(frozen=True)
class TtsRequest:
    """One utterance to synthesize.

    ``reference_wav``/``reference_text`` are only meaningful for engines with
    zero-shot cloning (Audio8). Engines without cloning ignore them.
    """

    text: str
    language: str | None = None
    voice: str | None = None
    reference_wav: Path | None = None
    reference_text: str | None = None


@dataclass(frozen=True)
class TtsResult:
    """Outcome of one synthesis, with the numbers a stress test needs."""

    engine: str
    wav_path: Path
    duration_s: float
    wall_s: float
    sample_rate: int

    @property
    def realtime_factor(self) -> float:
        """Seconds of audio produced per second of compute (higher is better)."""
        if self.wall_s <= 0:
            return 0.0
        return self.duration_s / self.wall_s


@runtime_checkable
class TtsBackend(Protocol):
    """Structural contract every engine adapter must satisfy.

    ``available`` is a cheap filesystem probe (no model load): it answers
    "could this engine run right now" so the compare harness can skip a
    missing pack instead of failing the whole run.
    """

    name: str

    @property
    def available(self) -> bool:
        """True when the runtime binary and model files are present."""
        ...

    def synthesize(self, request: TtsRequest, output_wav: Path) -> TtsResult:
        """Render ``request`` to ``output_wav`` and report timings."""
        ...
