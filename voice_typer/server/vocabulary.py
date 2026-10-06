"""User vocabulary store (C-PERSIST-1 categories).

Facade over the store's concerns, composed as mixins: persistence
(``vocabulary_persistence``), apply engine (``vocabulary_apply``), with
the schema constants in ``vocabulary_constants``. Every constant is
re-exported here, so ``from voice_typer.server.vocabulary import
CATEGORIES / VOCAB_FILENAME / MAX_*`` keeps resolving.

The entry mutators stay in this module because they read the SEC-011
limits from THIS module's globals, which keeps the
``monkeypatch.setattr(vocabulary, "MAX_CORRECTIONS_ENTRIES", ...)`` test
hook working.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from voice_typer.server.vocabulary_apply import VocabularyApplyMixin
from voice_typer.server.vocabulary_constants import (
    _LEGACY_VOCAB_FILENAME,
    BUNDLED_CORRECTIONS_PATH,
    CATEGORIES,  # noqa: F401  # facade re-export
    MAX_CORRECTIONS_ENTRIES,
    MAX_PATTERN_LENGTH,
    MAX_REPLACEMENT_LENGTH,
    VOCAB_FILENAME,
)
from voice_typer.server.vocabulary_persistence import VocabularyPersistenceMixin

if TYPE_CHECKING:
    from voice_typer.server.correction_usage import CorrectionUsageTracker

log = logging.getLogger(__name__)


class VocabularyManager(VocabularyPersistenceMixin, VocabularyApplyMixin):
    """Manages custom vocabulary entries across 6 categories."""

    def __init__(
        self,
        config_dir: Path | None = None,
        bundled_path: Path | None = None,
        usage_tracker: CorrectionUsageTracker | None = None,
    ):
        """``usage_tracker``: optional shared"""
        if config_dir is None:
            from voice_typer.server.config import _config_dir

            config_dir = _config_dir()
        self._config_dir = config_dir
        self._usage_tracker: CorrectionUsageTracker | None = usage_tracker
        self._user_path = config_dir / VOCAB_FILENAME
        # One-time migration of the legacy prefixed name
        _legacy = config_dir / _LEGACY_VOCAB_FILENAME
        if _legacy.exists() and not self._user_path.exists():
            try:
                _legacy.rename(self._user_path)
                log.debug(
                    "[VOCAB] migrated legacy %s -> %s",
                    _LEGACY_VOCAB_FILENAME,
                    VOCAB_FILENAME,
                )
            except OSError as exc:
                log.debug("[VOCAB] legacy file migration failed: %s", exc)

        if bundled_path is None:
            # use the shared BUNDLED_CORRECTIONS_PATH constant.
            bundled_path = BUNDLED_CORRECTIONS_PATH
        self._bundled_path = bundled_path

        # Route user-vocabulary persistence through PersistedJSON
        from voice_typer.server.secure_file_io import PersistedJSON

        self._user_store: Any = PersistedJSON(self._user_path, default={})

        # Active merged data: {category: data}
        self._data: dict[str, Any] = {}
        # Deletion tombstones: {category: [key | [wrong, correct], ...]}.
        self._deleted: dict[str, list] = {}
        # guards read-modify-write mutations of self._data (add/remove/
        self._lock = threading.Lock()
        # Raw bundled defaults (as loaded by ``_load_bundled``, before any
        self._bundled_raw: dict[str, Any] = {}
        # Combined-alternation regex cache for phrase-level categories
        self._combined_phrase_cache: (
            dict[str, tuple[re.Pattern[str], dict[str, tuple[str, str]]] | tuple[()]] | None
        ) = None
        self._load_and_merge()

    def _load_bundled(self) -> dict:
        """Load the bundled corrections.json."""
        if not self._bundled_path.exists():
            return {}
        try:
            # use _secure_read_text to prevent symlink-TOCTOU attacks
            from voice_typer.server.config import _secure_read_text

            raw = _secure_read_text(self._bundled_path, encoding="utf-8")
            data = json.loads(raw)
            return self._normalize_data(data)
        except Exception as exc:
            log.warning("[VOCAB] Failed to load bundled: %s", exc)
            return {}

    def add_entry(self, category: str, key: str, value: str) -> bool:
        """Add an entry to a dict-based category (misspellings, technical_terms, names, products)."""
        if category not in ("misspellings", "technical_terms", "names", "products"):
            log.error("[VOCAB] Cannot add dict entry to list category %s", category)
            return False
        if len(key) > MAX_PATTERN_LENGTH:
            log.warning("[VOCAB] Pattern exceeds MAX_PATTERN_LENGTH (%d > %d), rejecting", len(key), MAX_PATTERN_LENGTH)
            return False
        if len(value) > MAX_REPLACEMENT_LENGTH:
            log.warning(
                "[VOCAB] Replacement exceeds MAX_REPLACEMENT_LENGTH (%d > %d), rejecting",
                len(value),
                MAX_REPLACEMENT_LENGTH,
            )
            return False
        with self._lock:
            if not isinstance(self._data.get(category), dict):
                self._data[category] = {}
            cat_data = self._data[category]
            if not isinstance(cat_data, dict):
                return False
            if len(cat_data) >= MAX_CORRECTIONS_ENTRIES:
                log.warning(
                    "[VOCAB] Category %s has reached MAX_CORRECTIONS_ENTRIES (%d), rejecting",
                    category,
                    MAX_CORRECTIONS_ENTRIES,
                )
                return False
            # snapshot for rollback.
            had_key = key in cat_data
            old_value = cat_data.get(key)
            cat_data[key] = value
            # Re-adding an entry clears its deletion tombstone so the
            self._deleted.setdefault(category, [])
            if key in self._deleted[category]:
                self._deleted[category].remove(key)
        try:
            self._save_user()
        except Exception:
            # roll back the in-memory mutation.
            with self._lock:
                if had_key:
                    cat_data[key] = old_value
                elif key in cat_data:
                    del cat_data[key]
            raise
        # invalidate pattern cache on mutation.
        self._invalidate_pattern_cache()
        return True

    def remove_entry(self, category: str, key: str) -> bool:
        """Remove an entry from a dict-based category."""
        removed = False
        old_value: Any = None
        cat_data: Any = None
        tombstoned = False
        with self._lock:
            cat_data = self._data.get(category)
            if isinstance(cat_data, dict) and key in cat_data:
                old_value = cat_data[key]
                del cat_data[key]
                # Record a deletion tombstone so removing a BUNDLED
                self._deleted.setdefault(category, [])
                if key not in self._deleted[category]:
                    self._deleted[category].append(key)
                    tombstoned = True
                removed = True
        if removed:
            try:
                self._save_user()
            except Exception:
                # roll back the in-memory mutation (and tombstone).
                with self._lock:
                    if isinstance(cat_data, dict):
                        cat_data[key] = old_value
                    if tombstoned and key in self._deleted.get(category, []):
                        self._deleted[category].remove(key)
                raise
            # invalidate pattern cache on mutation.
            self._invalidate_pattern_cache()
        return removed

    def add_phrase(self, category: str, wrong: str, correct: str) -> bool:
        """Add an entry to a list-based category (phrase_corrections, extra_word_patterns)."""
        if category not in ("phrase_corrections", "extra_word_patterns"):
            log.error("[VOCAB] Cannot add list entry to dict category %s", category)
            return False
        if len(wrong) > MAX_PATTERN_LENGTH:
            log.warning(
                "[VOCAB] Phrase pattern exceeds MAX_PATTERN_LENGTH (%d > %d), rejecting", len(wrong), MAX_PATTERN_LENGTH
            )
            return False
        if len(correct) > MAX_REPLACEMENT_LENGTH:
            log.warning(
                "[VOCAB] Phrase replacement exceeds MAX_REPLACEMENT_LENGTH (%d > %d), rejecting",
                len(correct),
                MAX_REPLACEMENT_LENGTH,
            )
            return False
        with self._lock:
            if not isinstance(self._data.get(category), list):
                self._data[category] = []
            cat_data = self._data[category]
            if not isinstance(cat_data, list):
                return False
            if len(cat_data) >= MAX_CORRECTIONS_ENTRIES:
                log.warning(
                    "[VOCAB] Category %s has reached MAX_CORRECTIONS_ENTRIES (%d), rejecting",
                    category,
                    MAX_CORRECTIONS_ENTRIES,
                )
                return False
            new_entry = [wrong, correct]
            cat_data.append(new_entry)
            # Re-adding a phrase clears its deletion tombstone (mirrors
            self._deleted.setdefault(category, [])
            with contextlib.suppress(ValueError):
                self._deleted[category].remove(list(new_entry))
        try:
            self._save_user()
        except Exception:
            # roll back the in-memory mutation (and un-tombstone).
            with self._lock, contextlib.suppress(ValueError):
                cat_data.remove(new_entry)
            raise
        # invalidate pattern cache on mutation.
        self._invalidate_pattern_cache()
        return True

    def remove_phrase(self, category: str, index: int) -> bool:
        """Remove a phrase entry by index."""
        removed = False
        old_entry: Any = None
        cat_data: Any = None
        tombstoned = False
        tombstone_pair: Any = None
        with self._lock:
            cat_data = self._data.get(category)
            if isinstance(cat_data, list) and 0 <= index < len(cat_data):
                old_entry = cat_data.pop(index)
                # Record a deletion tombstone so removing a BUNDLED
                self._deleted.setdefault(category, [])
                tombstone_pair = list(old_entry) if isinstance(old_entry, (list, tuple)) else old_entry
                if tombstone_pair not in self._deleted[category]:
                    self._deleted[category].append(tombstone_pair)
                    tombstoned = True
                removed = True
        if removed:
            try:
                self._save_user()
            except Exception:
                # roll back the in-memory mutation (and tombstone).
                with self._lock:
                    if isinstance(cat_data, list):
                        cat_data.insert(index, old_entry)
                    if tombstoned and tombstone_pair in self._deleted.get(category, []):
                        self._deleted[category].remove(tombstone_pair)
                raise
        # invalidate pattern cache on mutation.
        self._invalidate_pattern_cache()
        return removed

    def import_json(self, json_str: str, *, merge: bool = True) -> tuple[int, int]:
        """Import vocabulary from a JSON string.

        Returns a tuple ``(categories_imported, dropped_entries)``.
        """
        try:
            data = json.loads(json_str)
            data = self._normalize_data(data)

            # within the SEC-011 resource limits even when the
            dropped = 0
            validated: dict[str, Any] = {}
            for cat in CATEGORIES:
                if cat not in data or data[cat] is None:
                    continue
                raw = data[cat]
                if cat in ("misspellings", "technical_terms", "names", "products"):
                    if not isinstance(raw, dict):
                        continue
                    filtered: dict[str, str] = {}
                    for k, v in raw.items():
                        k_str = k if isinstance(k, str) else str(k)
                        v_str = v if isinstance(v, str) else str(v)
                        if len(k_str) > MAX_PATTERN_LENGTH:
                            dropped += 1
                            continue
                        if len(v_str) > MAX_REPLACEMENT_LENGTH:
                            dropped += 1
                            continue
                        filtered[k_str] = v_str
                    existing_cat = self._data.get(cat)
                    existing_len = len(existing_cat) if isinstance(existing_cat, dict) else 0
                    new_len = len(filtered)
                    would_be = existing_len + new_len if merge else new_len
                    if would_be > MAX_CORRECTIONS_ENTRIES:
                        log.warning(
                            "[VOCAB] Category %s would exceed MAX_CORRECTIONS_ENTRIES "
                            "(existing=%d, new=%d, cap=%d) | dropping %d entries from import",
                            cat,
                            existing_len,
                            new_len,
                            MAX_CORRECTIONS_ENTRIES,
                            new_len,
                        )
                        dropped += new_len
                        continue
                    # only register non-empty categories so the
                    if filtered:
                        validated[cat] = filtered
                else:
                    # List-based category (phrase_corrections, extra_word_patterns).
                    if not isinstance(raw, list):
                        continue
                    filtered_list: list[list[str]] = []
                    for entry in raw:
                        if not isinstance(entry, list | tuple) or len(entry) < 2:
                            dropped += 1
                            continue
                        bad, good = entry[0], entry[1]
                        bad_str = bad if isinstance(bad, str) else str(bad)
                        good_str = good if isinstance(good, str) else str(good)
                        if len(bad_str) > MAX_PATTERN_LENGTH or len(good_str) > MAX_REPLACEMENT_LENGTH:
                            dropped += 1
                            continue
                        filtered_list.append([bad_str, good_str])
                    existing_cat = self._data.get(cat)
                    existing_len = len(existing_cat) if isinstance(existing_cat, list) else 0
                    new_len = len(filtered_list)
                    would_be = existing_len + new_len if merge else new_len
                    if would_be > MAX_CORRECTIONS_ENTRIES:
                        log.warning(
                            "[VOCAB] Category %s would exceed MAX_CORRECTIONS_ENTRIES "
                            "(existing=%d, new=%d, cap=%d) | dropping %d entries from import",
                            cat,
                            existing_len,
                            new_len,
                            MAX_CORRECTIONS_ENTRIES,
                            new_len,
                        )
                        dropped += new_len
                        continue
                    # only register non-empty categories so the
                    if filtered_list:
                        validated[cat] = filtered_list

            if dropped:
                log.warning(
                    "[VOCAB] Dropped %d entries from import (oversized or over-cap)",
                    dropped,
                )

            count = 0
            with self._lock:
                # snapshot for rollback. Shallow-copy the
                snapshot: dict[str, Any] = {}
                for cat, val in self._data.items():
                    if isinstance(val, dict):
                        snapshot[cat] = dict(val)
                    elif isinstance(val, list):
                        snapshot[cat] = list(val)
                    else:
                        snapshot[cat] = val
                for cat in CATEGORIES:
                    if cat not in validated:
                        continue
                    if merge:
                        if cat in ("misspellings", "technical_terms", "names", "products"):
                            if not isinstance(self._data.get(cat), dict):
                                self._data[cat] = {}
                            cat_dict = self._data[cat]
                            if isinstance(cat_dict, dict) and isinstance(validated[cat], dict):
                                cat_dict.update(validated[cat])
                        else:
                            if not isinstance(self._data.get(cat), list):
                                self._data[cat] = []
                            cat_list = self._data[cat]
                            if isinstance(cat_list, list) and isinstance(validated[cat], list):
                                cat_list.extend(validated[cat])
                    else:
                        self._data[cat] = validated[cat]
                    count += 1
            if count:
                try:
                    self._save_user()
                except Exception:
                    # roll back the in-memory mutation.
                    with self._lock:
                        self._data.clear()
                        self._data.update(snapshot)
                    raise
            # invalidate pattern cache on import.
            self._invalidate_pattern_cache()
            return count, dropped
        except Exception:
            log.exception("[VOCAB] Import failed")
            return 0, 0
