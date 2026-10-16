"""VolumeBackend / MicVolumeBackend ABCs + VolumeState."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class VolumeState:
    """Immutable snapshot of system volume for save/restore."""

    linear: float
    muted: bool


class VolumeBackend(ABC):
    """Abstract platform volume controller."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier, e.g. ``'pycaw (WASAPI)'``."""

    @property
    @abstractmethod
    def supports_per_session(self) -> bool:
        """``True`` if the backend can duck individual audio sessions
        (Windows ``ISimpleAudioVolume``).  ``False`` = master-volume only."""

    @abstractmethod
    def initialize(self) -> bool:
        """Set up the backend (open devices, load libraries).

        Returns ``True`` if the backend is ready for use, ``False`` if
        """

    @abstractmethod
    def get_state(self) -> VolumeState | None:
        """Read current volume + mute state.

        Returns ``None`` on failure (device disconnected, API error).
        """

    @abstractmethod
    def set_linear(self, level: float, muted: bool | None = None) -> bool:
        """Set volume in perceptual-linear scale.

        Returns ``True`` on success, ``False`` on failure.
        """

    def fade_to(
        self,
        target_linear: float,
        duration_ms: int = 150,
        steps: int = 10,
    ) -> bool:
        """Ramp volume to *target_linear* over *duration_ms*."""
        current = self.get_state()
        if current is None:
            return self.set_linear(target_linear)

        if duration_ms <= 0 or steps <= 1 or self._set_linear_is_subprocess:
            return self.set_linear(target_linear)

        start = current.linear
        sleep_s = duration_ms / steps / 1000.0
        for i in range(1, steps + 1):
            t = i / steps
            val = start + (target_linear - start) * t
            val = max(0.0, min(1.0, val))
            self.set_linear(val)
            if i < steps:
                time.sleep(sleep_s)
        return True

    # Used by ``fade_to`` to decide whether to multi-step (in-process
    @property
    def _set_linear_is_subprocess(self) -> bool:
        """Return ``True`` if :meth:`set_linear` spawns a subprocess."""
        return False

    # Smart ducking: if no application is currently playing audio

    def is_speaker_active(self) -> bool:
        """Return ``True`` if audio output is currently playing."""
        return True

    # Smart-duck background monitor polls ``is_speaker_active()`` every

    @property
    def recommended_poll_interval_ms(self) -> int:
        """Recommended smart-duck poll interval in milliseconds."""
        return 500

    @property
    def min_poll_interval_ms(self) -> int:
        """Minimum safe smart-duck poll interval in milliseconds."""
        return 0

    def get_other_sessions(self) -> list:
        """Return other audio sessions for per-session ducking."""
        return []

    def duck_other_sessions(self, level: float) -> bool:
        """Duck all foreign audio sessions to *level*.

        Returns ``True`` if any sessions were ducked, ``False`` otherwise.
        """
        return False

    def restore_other_sessions(self) -> bool:
        """Restore foreign audio sessions to their pre-duck volume.

        Only meaningful on Windows with per-session support enabled.
        """
        return False


class MicVolumeBackend(ABC):
    """Abstract platform controller for the capture-endpoint input gain.

    A separate ABC from :class:`VolumeBackend` (not a subclass): an input
    endpoint has no mute and no per-session surface, so inheriting the
    duck/restore/session API would only produce no-op stubs. The two share
    only the ``initialize`` / read / write shape.

    Failure logging is deliberately left to the caller: the guard polls
    every couple of seconds and owns the "warn after N consecutive
    failures" policy in ONE place, so per-platform backends log at DEBUG.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier, e.g. ``'pycaw (WASAPI capture)'``."""

    @property
    @abstractmethod
    def supports_set(self) -> bool:
        """``False`` when the OS exposes no settable input gain.

        Most built-in macOS mics have none. The renderer then shows the
        guard message WITHOUT a restore button rather than pretending a
        write that the OS will ignore.
        """

    @abstractmethod
    def initialize(self) -> bool:
        """Set up the backend. ``False`` = no usable capture endpoint."""

    @abstractmethod
    def get_level(self) -> float | None:
        """Read the capture gain in [0.0, 1.0]; ``None`` on failure."""

    @abstractmethod
    def set_level(self, level: float) -> bool:
        """Write the capture gain; ``False`` on failure."""
