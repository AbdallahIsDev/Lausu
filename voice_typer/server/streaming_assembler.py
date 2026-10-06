"""StreamingTextAssembler: commit timestamped words only after they are
outside the unsafe tail.

Carries the RACE-031 pins (seen-timestamps dedup set, batch-then-lock)
with the code they describe. Split from ``voice_typer.server.streaming``
(create-first); the facade re-exports the class.

"""

from __future__ import annotations

import collections
import logging
import math
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field

from voice_typer.server.streaming_windows import AudioWindow, WordTiming
from voice_typer.server.text_cleanup import _token_key

# Same logger object as the pre-split facade: caplog tests set levels on
# ``voice_typer.server.streaming`` for the records emitted here.
log = logging.getLogger("voice_typer.server.streaming")

@dataclass
class StreamingTextAssembler:
    """Commit timestamped words only after they are outside the unsafe tail."""

    # cap _words to prevent unbounded growth. Pre-fix this
    _MAX_WORDS = 10000
    # per-key bounded deque maxlen for _word_key_index. 8 entries
    _WORD_KEY_INDEX_MAXLEN = 8
    _words: collections.deque[WordTiming] = field(
        default_factory=lambda: collections.deque(maxlen=StreamingTextAssembler._MAX_WORDS)
    )
    # number of items evicted from the front of ``_words``.
    _base_offset: int = 0
    # RACE-031: the seen-timestamps set is the streaming dedup
    _MAX_SEEN_TIMESTAMPS = 50000
    _seen_timestamps: set[tuple[float, float]] = field(default_factory=set)
    _word_key_index: dict[str, collections.deque[int]] = field(default_factory=dict)
    last_committed_time: float = 0.0
    _lock: threading.RLock = field(default_factory=threading.RLock)
    # cache the sorted committed_text and invalidate on mutation
    _committed_text_cache: str | None = field(default=None)
    _words_dirty: bool = field(default=True)

    @property
    def committed_text(self) -> str:
        with self._lock:
            # return cached result if no mutations since last read
            if not self._words_dirty and self._committed_text_cache is not None:
                return self._committed_text_cache
            # PERF- sort at read time since we deferred sorting
            words_list = list(self._words)
            words_list.sort(key=lambda w: (w.start_seconds, w.end_seconds))
            self._committed_text_cache = " ".join(word.word for word in words_list)
            self._words_dirty = False
            return self._committed_text_cache

    def add_window(
        self,
        window: AudioWindow,
        words: Iterable[WordTiming],
        right_guard_seconds: float,
    ) -> str:
        return self.add_words(
            words,
            commit_horizon_seconds=window.end_seconds - right_guard_seconds,
        )

    def add_words(
        self,
        words: Iterable[WordTiming],
        commit_horizon_seconds: float,
    ) -> str:
        # RACE-031: batch-then-lock is the contention approximation.
        candidates = []
        for word in words:
            if word.end_seconds > commit_horizon_seconds:
                continue
            text = word.word.strip()
            if not text:
                continue
            candidates.append(word)

        with self._lock:
            return self._add_words_unlocked(candidates, commit_horizon_seconds)

    def _add_words_unlocked(
        self,
        words: Iterable[WordTiming],
        commit_horizon_seconds: float,
    ) -> str:
        # hard-cap on the dedup set BEFORE the loop. The
        if len(self._seen_timestamps) > self._MAX_SEEN_TIMESTAMPS:
            self._seen_timestamps = set()
        committed: list[str] = []
        for word in words:
            if word.end_seconds > commit_horizon_seconds:
                continue
            timestamp_key = (
                round(word.start_seconds, 3),
                round(word.end_seconds, 3),
            )
            if timestamp_key in self._seen_timestamps:
                continue

            text = word.word.strip()
            if not text:
                continue
            candidate = WordTiming(
                text,
                start_seconds=word.start_seconds,
                end_seconds=word.end_seconds,
            )
            if self._has_near_duplicate_unlocked(candidate):
                self._seen_timestamps.add(timestamp_key)
                continue
            self._seen_timestamps.add(timestamp_key)
            self._insert_word_unlocked(candidate)
            committed.append(text)
            self.last_committed_time = max(
                self.last_committed_time,
                word.end_seconds,
            )
            # invalidate cached text on mutation
            self._words_dirty = True
        # Prune committed words that are well before the commit horizon
        if math.isfinite(commit_horizon_seconds):
            prune_threshold = commit_horizon_seconds - 5.0
            if prune_threshold > 0:
                self._prune_old_entries(prune_threshold)
        # when ``commit_horizon_seconds == math.inf`` (the
        return " ".join(committed)

    def _prune_old_entries(self, threshold: float) -> None:
        """Prune dedup structures for old entries; never remove from _words.

        _words is the output accumulator and must keep all committed entries.
        Only _seen_timestamps and _word_key_index are pruned to limit memory.

        previously rebuilt ``_word_key_index`` from scratch
        on every prune. With a 5-min session and 200+ words, this was
        O(n) every few seconds. We now remove only the indices that
        pointed to evicted timestamps, but since _words is never
        pruned, the indices stay valid; we only need to drop stale
        entries from the timestamp set. The word_key_index is left
        alone (it doesn't grow unboundedly because it's keyed on
        distinct words, not timestamps).
        """
        # Prune old timestamps from dedup set
        new_timestamps: set[tuple[float, float]] = set()
        for ts in self._seen_timestamps:
            if ts[1] >= threshold:
                new_timestamps.add(ts)
        if len(new_timestamps) == len(self._seen_timestamps):
            return
        self._seen_timestamps = new_timestamps
        # do NOT rebuild _word_key_index, it's keyed on

    def _insert_word_unlocked(self, word: WordTiming):
        """Insert a word, maintaining sorted order.

        PERF- previously this did a linear scan + list.insert
        (O(n) per insert, O(n^2) per session) and then shifted all
        index entries.  Now we just append and defer sorting to
        commit time, the words are already approximately in order
        (streaming chunks arrive sequentially), so a full sort at
        commit is O(n log n) vs the O(n^2) insert pattern.

        enforce maxlen on _words. When the list exceeds
        _MAX_WORDS, evict the oldest entry and log a warning.
        """
        # detect imminent eviction BEFORE appending so we
        if self._words.maxlen is not None and len(self._words) >= self._words.maxlen:
            # Peek the leftmost item; deque.append will evict it.
            evicted_word = self._words[0]
            evicted_absolute_idx = self._base_offset  # current offset → 0 in deque
            #  do NOT log evicted_word.word at any level —
            log.warning(
                "[STREAMING] Word list exceeded %d entries; evicted oldest (idx=%d)",
                self._MAX_WORDS,
                evicted_absolute_idx,
            )
            log.debug(
                "[STREAMING] Evicted word (%d chars) (debug only)",
                len(evicted_word.word),
            )
            # Bump base offset so all future absolute-index → deque-index
            self._base_offset += 1
            # Drop the index entry pointing at the evicted word. Other
            for key, indices in list(self._word_key_index.items()):
                if evicted_absolute_idx in indices:
                    new_indices = collections.deque(
                        (i for i in indices if i != evicted_absolute_idx),
                        maxlen=self._WORD_KEY_INDEX_MAXLEN,
                    )
                    if new_indices:
                        self._word_key_index[key] = new_indices
                    else:
                        del self._word_key_index[key]
            # also drop the evicted word's (start, end) timestamp
            evicted_ts_key = (
                round(evicted_word.start_seconds, 3),
                round(evicted_word.end_seconds, 3),
            )
            self._seen_timestamps.discard(evicted_ts_key)

        key = _token_key(word.word)
        # Absolute index = base_offset + current deque length (before append).
        absolute_idx = self._base_offset + len(self._words)
        self._words.append(word)
        if key:
            # use a bounded deque (maxlen=_WORD_KEY_INDEX_MAXLEN)
            existing = self._word_key_index.get(key)
            if existing is None:
                self._word_key_index[key] = collections.deque((absolute_idx,), maxlen=self._WORD_KEY_INDEX_MAXLEN)
            else:
                existing.append(absolute_idx)
        # invalidate cached text on mutation
        self._words_dirty = True

    def _has_near_duplicate_unlocked(self, word: WordTiming) -> bool:
        key = _token_key(word.word)
        if not key:
            return False
        matching_indices = self._word_key_index.get(key, [])
        for abs_idx in matching_indices:
            # convert absolute index → deque index.
            deque_idx = abs_idx - self._base_offset
            if deque_idx < 0 or deque_idx >= len(self._words):
                continue
            existing = self._words[deque_idx]
            if (
                abs(existing.start_seconds - word.start_seconds) <= 0.25
                and abs(existing.end_seconds - word.end_seconds) <= 0.25
            ):
                return True
        return False
