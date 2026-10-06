"""Streaming window/config primitives: :class:`StreamingConfig`,
:class:`WordTiming`, :class:`AudioWindow` and :class:`AudioWindowPlanner`.

Split from ``voice_typer.server.streaming`` (create-first); the facade
re-exports every name so the historical import path keeps resolving.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from voice_typer.server._lazy_import import lazy_module

np = lazy_module("numpy")

@dataclass(frozen=True)
class StreamingConfig:
    """Timing and safety settings for streaming transcription."""

    enabled: bool = False
    chunk_seconds: float = 12.0
    step_seconds: float = 5.0
    left_overlap_seconds: float = 3.0
    right_guard_seconds: float = 1.5
    min_first_chunk_seconds: float = 6.0
    silence_threshold: float = 0.003


@dataclass(frozen=True)
class WordTiming:
    """One timestamped word in global recording time."""

    word: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True, eq=False)
class AudioWindow:
    """A slice of 16 kHz mono audio and its global time bounds.

    PERF-EQ: ``eq=False`` is set so the dataclass-generated __eq__
    doesn't fire. The custom __eq__ uses a lightweight identity/
    scalar comparison instead of np.array_equal (which is O(n) in
    the audio length). For test utilities that need full array
    comparison, use ``np.array_equal(a.audio, b.audio)`` directly.
    """

    audio: np.ndarray
    start_seconds: float
    end_seconds: float

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AudioWindow):
            return NotImplemented
        # PERF-EQ: compare scalar fields first (O(1)); only compare
        if self.start_seconds != other.start_seconds or self.end_seconds != other.end_seconds:
            return False
        # Same object or same underlying buffer → equal
        if self.audio is other.audio:
            return True
        # Different objects with same scalars, compare shapes then hash
        if self.audio.shape != other.audio.shape:
            return False
        return bool(np.array_equal(self.audio, other.audio))

    def __hash__(self) -> int:
        # hash on the scalar fields; audio is unhashable but
        return hash((self.start_seconds, self.end_seconds))


@dataclass
class AudioWindowPlanner:
    """Plan overlapping audio windows as recording audio grows."""

    config: StreamingConfig = field(default_factory=StreamingConfig)
    _last_window_end_seconds: float | None = None

    def next_window(self, audio: np.ndarray, sample_rate: int) -> AudioWindow | None:
        duration_seconds = len(audio) / sample_rate
        if self._last_window_end_seconds is None:
            if duration_seconds < self.config.min_first_chunk_seconds:
                return None
            requested_start_seconds = 0.0
            requested_end_seconds = min(duration_seconds, self.config.chunk_seconds)
        else:
            requested_end_seconds = self._last_window_end_seconds + self.config.step_seconds
            if duration_seconds < requested_end_seconds:
                return None
            requested_end_seconds = min(duration_seconds, requested_end_seconds)
            requested_start_seconds = max(
                0.0,
                self._last_window_end_seconds - self.config.left_overlap_seconds,
            )

        end_seconds = self._choose_boundary(
            audio=audio,
            sample_rate=sample_rate,
            requested_start_seconds=requested_start_seconds,
            requested_end_seconds=requested_end_seconds,
        )
        start_sample = int(round(requested_start_seconds * sample_rate))
        end_sample = int(round(end_seconds * sample_rate))
        # PROVENANCE INVARIANT, read before touching this window slice:
        window = AudioWindow(
            audio=audio[start_sample:end_sample],
            start_seconds=requested_start_seconds,
            end_seconds=end_seconds,
        )
        self._last_window_end_seconds = end_seconds
        return window

    def _choose_boundary(
        self,
        audio: np.ndarray,
        sample_rate: int,
        requested_start_seconds: float,
        requested_end_seconds: float,
    ) -> float:
        """Find the best boundary point between audio windows.

        previously returned the CENTER of the quietest frame
        (best_index = index + len(frame) // 2), which is offset by half
        a frame from where the next voice should start. Now returns the
        END of the quietest frame (best_index = index + len(frame)),
        which is the start of the next voice segment.
        """
        search_seconds = min(1.0, requested_end_seconds - requested_start_seconds)
        if search_seconds <= 0:
            return requested_end_seconds

        search_start = int(round((requested_end_seconds - search_seconds) * sample_rate))
        search_end = int(round(requested_end_seconds * sample_rate))
        search = audio[search_start:search_end]
        if len(search) == 0:
            return requested_end_seconds

        frame_size = max(1, int(0.05 * sample_rate))
        best_rms = float("inf")
        best_index = None
        for index in range(0, len(search), frame_size):
            frame = search[index : index + frame_size]
            if len(frame) == 0:
                continue
            rms = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))
            if rms < best_rms:
                best_rms = rms
                # use end of the quietest frame (index +
                best_index = index + len(frame)

        if best_index is None or best_rms > self.config.silence_threshold:
            return requested_end_seconds
        return (search_start + best_index) / sample_rate
