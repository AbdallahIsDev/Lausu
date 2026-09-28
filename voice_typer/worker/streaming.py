"""Worker-side streaming transcription state (ADR-0025 C6, build only).

Mirrors the slim-core window planner + overlap/tail-dedup design from
``voice_typer.server.streaming`` and ``docs/duplicated-text.md``
without importing it: the worker must not depend on slim ASR modules,
so this file is stdlib-only (plus lazy numpy at inference time) and
carries its own planner math and assembler state.

No slim-side cutover happens here: the slim core keeps constructing
``StreamingTranscriptionSession`` until a later lane subscribes to the
``transcription_partial`` pushes this module's frames feed.
"""

from __future__ import annotations

import array
import base64
import collections
import logging
import math
import threading
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("voice_typer.worker")

_ASR_SAMPLE_RATE = 16_000
# Same per-chunk ceiling as the C3 samples path: one push frame must
# itself respect the 1 MiB WS frame cap after base64 expansion.
_MAX_PUSH_PAYLOAD_B64 = 1_400_000
# A runaway client must not grow a session without bound; ten minutes
# of 16 kHz float32 is ~38 MiB, far past any real dictation.
_MAX_SESSION_SECONDS = 600.0
_NEAR_DUPLICATE_SECONDS = 0.25
_MAX_WORDS = 10000
_MAX_SEEN_TIMESTAMPS = 50000


@dataclass(frozen=True)
class Word:
    """One timestamped word in global session time."""

    word: str
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class SessionConfig:
    """Timing settings for one worker-side streaming session."""

    chunk_seconds: float = 12.0
    step_seconds: float = 5.0
    left_overlap_seconds: float = 3.0
    right_guard_seconds: float = 1.5
    min_first_chunk_seconds: float = 6.0
    silence_threshold: float = 0.003
    sample_rate: int = _ASR_SAMPLE_RATE
    cycle_id: str = ""
    language: str | None = None

    @classmethod
    def from_dict(cls, data: Any) -> SessionConfig:
        """Build from the open command's ``config`` dict (unknown keys ignored)."""
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("config must be an object")
        known = {f for f in cls.__dataclass_fields__ if f not in ("sample_rate", "cycle_id", "language")}
        kwargs: dict[str, Any] = {}
        for key in known:
            if key in data:
                value = data[key]
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValueError(f"config {key!r} must be a number")
                if not math.isfinite(float(value)) or float(value) <= 0:
                    raise ValueError(f"config {key!r} must be a positive number")
                kwargs[key] = float(value)
        sample_rate = data.get("sample_rate", _ASR_SAMPLE_RATE)
        if isinstance(sample_rate, bool) or not isinstance(sample_rate, int):
            raise ValueError("config 'sample_rate' must be an integer")
        if not 1000 <= sample_rate <= 192000:
            raise ValueError(f"config sample_rate {sample_rate} out of range")
        kwargs["sample_rate"] = sample_rate
        cycle_id = data.get("cycle_id", "")
        if cycle_id is not None and not isinstance(cycle_id, str):
            raise ValueError("config 'cycle_id' must be a string")
        kwargs["cycle_id"] = cycle_id or ""
        language = data.get("language")
        if language is not None and not isinstance(language, str):
            raise ValueError("config 'language' must be a string")
        kwargs["language"] = language
        return cls(**kwargs)


def _token_key(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


@dataclass
class TextAssembler:
    """Commit timestamped words only after they leave the unsafe tail."""

    _words: collections.deque[Word] = field(default_factory=lambda: collections.deque(maxlen=_MAX_WORDS))
    _base_offset: int = 0
    _seen_timestamps: set[tuple[float, float]] = field(default_factory=set)
    _word_key_index: dict[str, collections.deque[int]] = field(default_factory=dict)
    last_committed_time: float = 0.0
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _committed_text_cache: str | None = field(default=None)
    _words_dirty: bool = field(default=True)

    @property
    def committed_text(self) -> str:
        with self._lock:
            if not self._words_dirty and self._committed_text_cache is not None:
                return self._committed_text_cache
            ordered = sorted(self._words, key=lambda w: (w.start_seconds, w.end_seconds))
            self._committed_text_cache = " ".join(word.word for word in ordered)
            self._words_dirty = False
            return self._committed_text_cache

    def add_window(self, window_end_seconds: float, words: Any, right_guard_seconds: float) -> tuple[str, list[Word]]:
        """Commit words ending before the unsafe tail; return (new text, new words)."""
        normalized = _normalize_words(words)
        horizon = window_end_seconds - right_guard_seconds
        candidates = [word for word in normalized if word.end_seconds <= horizon]
        with self._lock:
            committed = self._add_unlocked(candidates, horizon)
            return (" ".join(word.word for word in committed), committed)

    def add_tail(self, words: Any) -> str:
        """Merge finalize-tail words with no horizon; return the full committed text."""
        normalized = _normalize_words(words)
        with self._lock:
            self._add_unlocked(normalized, math.inf)
            return self.committed_text

    def _add_unlocked(self, words: list[Word], commit_horizon_seconds: float) -> list[Word]:
        if len(self._seen_timestamps) > _MAX_SEEN_TIMESTAMPS:
            self._seen_timestamps = set()
        committed: list[Word] = []
        for word in words:
            if word.end_seconds > commit_horizon_seconds:
                continue
            timestamp_key = (round(word.start_seconds, 3), round(word.end_seconds, 3))
            if timestamp_key in self._seen_timestamps:
                continue
            if self._has_near_duplicate_unlocked(word):
                self._seen_timestamps.add(timestamp_key)
                continue
            self._seen_timestamps.add(timestamp_key)
            self._insert_unlocked(word)
            committed.append(word)
            self.last_committed_time = max(self.last_committed_time, word.end_seconds)
            self._words_dirty = True
        if math.isfinite(commit_horizon_seconds):
            self._prune_unlocked(commit_horizon_seconds - 5.0)
        return committed

    def _prune_unlocked(self, threshold: float) -> None:
        if threshold <= 0:
            return
        kept = {ts for ts in self._seen_timestamps if ts[1] >= threshold}
        if len(kept) != len(self._seen_timestamps):
            self._seen_timestamps = kept

    def _insert_unlocked(self, word: Word) -> None:
        if self._words.maxlen is not None and len(self._words) >= self._words.maxlen:
            evicted = self._words[0]
            self._base_offset += 1
            for key, indices in list(self._word_key_index.items()):
                remaining = collections.deque((i for i in indices if i != self._base_offset - 1), maxlen=8)
                if remaining:
                    self._word_key_index[key] = remaining
                else:
                    del self._word_key_index[key]
            self._seen_timestamps.discard((round(evicted.start_seconds, 3), round(evicted.end_seconds, 3)))
        absolute_idx = self._base_offset + len(self._words)
        self._words.append(word)
        key = _token_key(word.word)
        if key:
            self._word_key_index.setdefault(key, collections.deque(maxlen=8)).append(absolute_idx)
        self._words_dirty = True

    def _has_near_duplicate_unlocked(self, word: Word) -> bool:
        key = _token_key(word.word)
        if not key:
            return False
        for abs_idx in self._word_key_index.get(key, []):
            deque_idx = abs_idx - self._base_offset
            if deque_idx < 0 or deque_idx >= len(self._words):
                continue
            existing = self._words[deque_idx]
            if (
                abs(existing.start_seconds - word.start_seconds) <= _NEAR_DUPLICATE_SECONDS
                and abs(existing.end_seconds - word.end_seconds) <= _NEAR_DUPLICATE_SECONDS
            ):
                return True
        return False


def _normalize_words(words: Any) -> list[Word]:
    """Coerce engine word outputs (slim WordTiming objects or dicts) to local Words."""
    if words is None:
        return []
    normalized: list[Word] = []
    for item in words:
        if isinstance(item, Word):
            word, start, end = item.word, item.start_seconds, item.end_seconds
        elif isinstance(item, dict):
            word, start, end = item.get("word"), item.get("start_seconds"), item.get("end_seconds")
        else:
            word = getattr(item, "word", None)
            start = getattr(item, "start_seconds", None)
            end = getattr(item, "end_seconds", None)
        if not isinstance(word, str):
            raise TypeError("word text must be a string")
        if start is None or end is None:
            raise TypeError("word timestamps are required")
        start_f, end_f = float(start), float(end)
        if not (math.isfinite(start_f) and math.isfinite(end_f)):
            raise ValueError("word timestamps must be finite")
        if end_f < start_f:
            raise ValueError("word end must be >= start")
        text = word.strip()
        if text:
            normalized.append(Word(text, start_f, end_f))
    return normalized


class StreamingSession:
    """Per-connection streaming state: PCM buffer, planner cursor, assembler."""

    def __init__(self, session_id: int, config: SessionConfig) -> None:
        self.session_id = session_id
        self.config = config
        self._pcm: array.array[float] = array.array("f")
        self._next_index = 0
        self._last_window_end: float | None = None
        self.assembler = TextAssembler()

    @property
    def duration_seconds(self) -> float:
        return len(self._pcm) / self.config.sample_rate

    @property
    def committed_text(self) -> str:
        return self.assembler.committed_text

    def append_chunk(self, index: Any, payload_b64: Any) -> str | None:
        """Append one push chunk in index order; return an error string or None."""
        if isinstance(index, bool) or not isinstance(index, int):
            return "chunk index must be an integer"
        if index != self._next_index:
            return f"chunk index {index} out of order, expected {self._next_index}"
        if not isinstance(payload_b64, str) or len(payload_b64) > _MAX_PUSH_PAYLOAD_B64:
            return "chunk payload too large"
        try:
            raw = base64.b64decode(payload_b64, validate=True)
        except Exception:
            return "chunk payload is not valid base64"
        if len(raw) % 4 != 0:
            return "chunk payload is not float32 PCM"
        if (len(self._pcm) + len(raw) // 4) / self.config.sample_rate > _MAX_SESSION_SECONDS:
            return "session audio exceeds the length cap"
        chunk = array.array("f")
        chunk.frombytes(raw)
        self._pcm.extend(chunk)
        self._next_index += 1
        return None

    def due_window(self) -> tuple[float, float, float] | None:
        """Plan the next window; return (start, end, commit_horizon) or None."""
        duration = self.duration_seconds
        if self._last_window_end is None:
            if duration < self.config.min_first_chunk_seconds:
                return None
            start = 0.0
            requested_end = min(duration, self.config.chunk_seconds)
        else:
            requested_end = self._last_window_end + self.config.step_seconds
            if duration < requested_end:
                return None
            requested_end = min(duration, requested_end)
            start = max(0.0, self._last_window_end - self.config.left_overlap_seconds)
        end = self._choose_boundary(start, requested_end)
        self._last_window_end = end
        return (start, end, end - self.config.right_guard_seconds)

    def _choose_boundary(self, start: float, requested_end: float) -> float:
        search_seconds = min(1.0, requested_end - start)
        if search_seconds <= 0:
            return requested_end
        rate = self.config.sample_rate
        search_start = int(round((requested_end - search_seconds) * rate))
        search_end = int(round(requested_end * rate))
        search = self._pcm[search_start:search_end]
        if len(search) == 0:
            return requested_end
        frame_size = max(1, int(0.05 * rate))
        best_rms = math.inf
        best_index: int | None = None
        for offset in range(0, len(search), frame_size):
            frame = search[offset : offset + frame_size]
            if len(frame) == 0:
                continue
            mean_square = sum(float(sample) * float(sample) for sample in frame) / len(frame)
            rms = math.sqrt(mean_square)
            if rms < best_rms:
                best_rms = rms
                best_index = offset + len(frame)
        if best_index is None or best_rms > self.config.silence_threshold:
            return requested_end
        return (search_start + best_index) / rate

    def window_bytes(self, start_seconds: float, end_seconds: float) -> bytes:
        """Raw float32 PCM slice for one planned window."""
        rate = self.config.sample_rate
        start_sample = min(len(self._pcm), int(round(start_seconds * rate)))
        end_sample = min(len(self._pcm), int(round(end_seconds * rate)))
        return self._pcm[start_sample:end_sample].tobytes()

    def commit_window(self, words: Any, window_end_seconds: float) -> tuple[str, list[Word]]:
        """Commit one window's words; return (newly committed text, words)."""
        return self.assembler.add_window(window_end_seconds, words, self.config.right_guard_seconds)

    def finalize_plan(self) -> tuple[str, float, bytes]:
        """Plan the finalize pass: ("batch", 0, full) or ("tail", offset, slice)."""
        if not self.assembler.committed_text:
            return ("batch", 0.0, self._pcm.tobytes())
        tail_start = max(0.0, self.assembler.last_committed_time - self.config.left_overlap_seconds)
        rate = self.config.sample_rate
        start_sample = min(len(self._pcm), int(round(tail_start * rate)))
        return ("tail", tail_start, self._pcm[start_sample:].tobytes())

    def commit_tail(self, words: Any) -> str:
        """Merge finalize-tail words; return the full committed text.

        Mirrors the slim ``_finalize_impl`` merge boundary: tail words
        ending at or before the last committed time are already covered
        and must not re-enter (an engine boundary variant like tail
        "PackWorker" over committed "pack"+"worker" would otherwise
        survive the token-exact near-dup check as a duplicate).
        """
        boundary = self.assembler.last_committed_time
        normalized = _normalize_words(words)
        fresh = [word for word in normalized if word.end_seconds > boundary]
        return self.assembler.add_tail(fresh)


def to_16k_array(raw: bytes, sample_rate: int) -> Any:
    """Decode float32 PCM bytes to a 16 kHz numpy array (shared resampler when needed)."""
    import numpy as _np

    audio = _np.frombuffer(raw, dtype=_np.float32).copy().reshape(-1)
    if int(sample_rate) == _ASR_SAMPLE_RATE:
        return audio
    from voice_typer.server.recording.resampling import resample_audio

    return resample_audio(audio, int(sample_rate), _ASR_SAMPLE_RATE, log=log)


def transcribe_window_words(raw: bytes, sample_rate: int, offset_seconds: float, language: str | None) -> list[Word]:
    """Run word-timestamp inference over one window slice; return normalized Words."""
    if len(raw) == 0:
        return []
    from voice_typer.worker._transcribe import get_transcriber

    audio = to_16k_array(raw, sample_rate)
    if len(audio) == 0:
        return []
    engine = get_transcriber()._ensure_engine(language)
    transcribe_words = getattr(engine, "transcribe_words", None)
    if not callable(transcribe_words):
        raise RuntimeError("active backend has no transcribe_words; streaming unavailable")
    return _normalize_words(transcribe_words(audio, offset_seconds=offset_seconds))


__all__ = [
    "SessionConfig",
    "StreamingSession",
    "TextAssembler",
    "Word",
    "to_16k_array",
    "transcribe_window_words",
]
