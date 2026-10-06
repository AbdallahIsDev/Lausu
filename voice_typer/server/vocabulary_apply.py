"""Apply engine of the user vocabulary store.

Builds the combined-alternation regex for the phrase-level categories and
applies both phrase and word corrections to transcribed text, recording
usage hits. Moved verbatim out of ``voice_typer.server.vocabulary``;
the facade composes this mixin into ``VocabularyManager``.

Logger name intentionally stays ``voice_typer.server.vocabulary`` so log
records (caplog filters, file handler routing) are unchanged.
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from voice_typer.server.correction_usage import CorrectionUsageTracker

log = logging.getLogger("voice_typer.server.vocabulary")


class VocabularyApplyMixin:
    """Combined-regex cache + ``apply_to_text`` of ``VocabularyManager``.

    Host-state contract: ``self._data`` (merged ``{category: data}``),
    ``self._lock`` (guards read-modify-write), ``self._config_dir``, and
    ``self._usage_tracker`` / ``self._combined_phrase_cache``.
    """

    _data: dict[str, Any]
    _lock: threading.Lock
    _config_dir: Path
    _usage_tracker: CorrectionUsageTracker | None
    _combined_phrase_cache: dict[str, tuple[re.Pattern[str], dict[str, tuple[str, str]]] | tuple[()]] | None

    def _invalidate_pattern_cache(self) -> None:
        """invalidate the compiled-pattern cache. Called on any mutation."""
        self._combined_phrase_cache = None

    def _get_combined_phrase_pattern(self, category: str) -> tuple[re.Pattern[str], dict[str, tuple[str, str]]] | None:
        """Build (or fetch from cache) the combined-alternation regex for a

        Returns ``(pattern, lookup)`` where ``pattern`` is a single
        """
        if self._combined_phrase_cache is None:
            self._combined_phrase_cache = {}
        cached = self._combined_phrase_cache.get(category)
        if cached is not None:
            return cached or None  # (empty sentinel) → None
        with self._lock:
            entries = self._data.get(category, [])
            if not isinstance(entries, list) or not entries:
                self._combined_phrase_cache[category] = ()  # negative cache
                return None
            sorted_entries = sorted(
                (e for e in entries if isinstance(e, list | tuple) and len(e) >= 2),
                key=lambda e: len(e[0]),
                reverse=True,
            )
            if not sorted_entries:
                self._combined_phrase_cache[category] = ()  # negative cache
                return None
            lookup: dict[str, tuple[str, str]] = {}
            alternations: list[str] = []
            for entry in sorted_entries:
                key = entry[0].lower()
                if key in lookup:
                    # Duplicate original (case-insensitive), first
                    continue
                lookup[key] = (entry[1], entry[0])
                alternations.append(re.escape(entry[0]))
        pattern = re.compile("(?:" + "|".join(alternations) + ")", re.IGNORECASE)
        compiled: tuple[re.Pattern[str], dict[str, tuple[str, str]]] = (pattern, lookup)
        self._combined_phrase_cache[category] = compiled
        return compiled

    @property
    def usage_tracker(self) -> CorrectionUsageTracker:
        """The shared per-correction usage tracker (see correction_usage.py)."""
        if self._usage_tracker is None:
            from voice_typer.server.correction_usage import CorrectionUsageTracker

            self._usage_tracker = CorrectionUsageTracker(self._config_dir)
        return self._usage_tracker

    def apply_to_text(self, text: str, *, track_usage: bool = True) -> str:
        """Apply vocabulary corrections to transcribed text."""
        # Pre-compiled regex + the memoized token-key normalizer, shared
        from voice_typer.server.text_cleanup import _RE_MISSPELL_WRAP, _token_key

        # (category, original, count) hits for the usage tracker.
        hits: list[tuple[str, str, int]] = []

        # Phrase-level corrections. ONE combined-alternation pass per
        for cat in ("phrase_corrections", "extra_word_patterns"):
            combined = self._get_combined_phrase_pattern(cat)
            if combined is None:
                continue
            pattern, lookup = combined
            counts: dict[str, int] = {}

            def _phrase_repl(
                m: re.Match[str],
                _lookup: dict[str, tuple[str, str]] = lookup,
                _counts: dict[str, int] = counts,
            ) -> str:
                key = m.group(0).lower()
                _counts[key] = _counts.get(key, 0) + 1
                return _lookup[key][0]

            text, _total = pattern.subn(_phrase_repl, text)
            for key, count in counts.items():
                hits.append((cat, lookup[key][1], count))

        # Word-level corrections, single tokenization pass shared
        with self._lock:
            word_cats = [(cat, self._data.get(cat)) for cat in ("misspellings", "technical_terms", "names", "products")]

        tokens = text.split(" ")
        for cat, entries in word_cats:
            # Skip non-dicts and empty categories, avoids the per-token
            if not isinstance(entries, dict) or not entries:
                continue
            for i, token in enumerate(tokens):
                key = _token_key(token)
                correction = entries.get(key)
                if correction is not None:
                    match = _RE_MISSPELL_WRAP.match(token)
                    tokens[i] = f"{match.group(1)}{correction}{match.group(3)}" if match else correction
                    hits.append((cat, key, 1))
        text = " ".join(tokens)

        if track_usage and hits:
            try:
                self.usage_tracker.record_corrections(hits)
            except Exception:
                # Usage tracking must NEVER break the dictation path.
                log.warning("[VOCAB] Failed to record correction usage", exc_info=True)

        return text
