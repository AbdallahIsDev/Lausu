"""Persistence layer of the user vocabulary store.

Loads bundled corrections + the user file (PersistedJSON, atomic write +
.bak), merges them with the ``_deleted`` tombstones, and exposes the
read/export surface. Moved verbatim out of
``voice_typer.server.vocabulary``; the facade composes this mixin into
``VocabularyManager`` and re-exports nothing new (the methods stay on
the class). Entry-limit constants are read through the facade only in the
entry mutators, which remain in ``vocabulary.py``, and ``_load_bundled``
stays there too (SEC-002 pins its secure read to that module).
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from voice_typer.server.vocabulary_constants import CATEGORIES

# Logger name intentionally stays ``voice_typer.server.vocabulary`` so log
# records (caplog filters, file handler routing) are unchanged.
log = logging.getLogger("voice_typer.server.vocabulary")


class VocabularyPersistenceMixin:
    """Load / merge / save / read surface of ``VocabularyManager``.

    Host-state contract: ``self._config_dir``, ``self._user_path``,
    ``self._bundled_path`` (set by ``VocabularyManager.__init__``);
    ``self._user_store`` (PersistedJSON), ``self._data`` (merged
    ``{category: data}``), ``self._deleted`` (tombstones),
    ``self._bundled_raw`` (raw bundled defaults), and ``self._lock``.
    """

    _data: dict[str, Any]
    _deleted: dict[str, list[Any]]
    _bundled_path: Path
    _bundled_raw: dict[str, Any]
    _user_store: Any
    _lock: threading.Lock

    if TYPE_CHECKING:
        # Provided by ``VocabularyManager`` / ``VocabularyApplyMixin``.
        def _load_bundled(self) -> dict: ...
        def _invalidate_pattern_cache(self) -> None: ...

    def _load_and_merge(self) -> None:
        """Load bundled corrections then merge user vocabulary on top."""
        # Start with bundled corrections
        bundled = self._load_bundled()
        # Keep the RAW defaults around so the diff-style save path can
        self._bundled_raw = bundled
        user = self._load_user()

        # Deletion tombstones (reserved ``_deleted`` key in the user file)
        self._deleted = {}
        raw_deleted = user.get("_deleted")
        if isinstance(raw_deleted, dict):
            self._deleted = {
                cat: (list(v) if isinstance(v, list) else []) for cat, v in raw_deleted.items() if cat in CATEGORIES
            }

        # Merge: user extends bundled
        for cat in CATEGORIES:
            bundled_cat = bundled.get(cat)
            user_cat = user.get(cat)

            if cat in ("misspellings", "technical_terms", "names", "products"):
                # Dict-based: user keys override bundled
                merged = dict(bundled_cat) if isinstance(bundled_cat, dict) else {}
                if isinstance(user_cat, dict):
                    merged.update(user_cat)
                self._data[cat] = merged
            elif cat in ("phrase_corrections", "extra_word_patterns"):
                # List-based: user entries are appended
                merged = list(bundled_cat) if isinstance(bundled_cat, list) else []
                if isinstance(user_cat, list):
                    merged.extend(user_cat)
                self._data[cat] = merged
            else:
                # Fallback
                self._data[cat] = user_cat if user_cat is not None else bundled_cat

        # Apply deletion tombstones: bundled (or previously user-added)
        for cat in CATEGORIES:
            removed = self._deleted.get(cat)
            if not removed:
                continue
            if cat in ("misspellings", "technical_terms", "names", "products"):
                cat_data = self._data.get(cat)
                if isinstance(cat_data, dict):
                    for k in removed:
                        if isinstance(k, str):
                            cat_data.pop(k, None)
            else:
                cat_data = self._data.get(cat)
                if isinstance(cat_data, list):
                    removed_pairs = {tuple(r) for r in removed if isinstance(r, (list, tuple)) and len(r) >= 2}
                    if removed_pairs:
                        self._data[cat] = [
                            e
                            for e in cat_data
                            if not (isinstance(e, (list, tuple)) and len(e) >= 2 and tuple(e) in removed_pairs)
                        ]

        # invalidate pattern cache after data reload.
        self._invalidate_pattern_cache()

    def _load_user(self) -> dict:
        """Load the user vocabulary file."""
        data = self._user_store.load()
        if not isinstance(data, dict):
            return {}
        return self._normalize_data(data)

    @staticmethod
    def _normalize_data(data: dict) -> dict:
        """Normalize raw JSON data into canonical category format."""
        if not isinstance(data, dict):
            return {
                cat: ({} if cat in ("misspellings", "technical_terms", "names", "products") else [])
                for cat in CATEGORIES
            }
        result: dict[str, Any] = {}
        for cat in CATEGORIES:
            val = data.get(cat)
            if cat in ("misspellings", "technical_terms", "names", "products"):
                result[cat] = dict(val) if isinstance(val, dict) else {}
            elif cat in ("phrase_corrections", "extra_word_patterns"):
                result[cat] = list(val) if isinstance(val, list) else []
            else:
                result[cat] = val
        # Carry the reserved ``_deleted`` tombstone key through
        if isinstance(data.get("_deleted"), dict):
            result["_deleted"] = {
                cat: (list(v) if isinstance(v, list) else [])
                for cat, v in data["_deleted"].items()
                if cat in CATEGORIES
            }
        return result

    def _save_user(self) -> None:
        """Save only user vocabulary data (not bundled) to the user file."""
        from voice_typer.server.retry import delay_for_attempt, sleep_interruptible

        max_retries = 3
        save_delays = (0.05, 0.10)
        # track the final failure so we can raise after the
        final_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                # PersistedJSON.save handles atomic write + .bak
                payload: dict[str, Any] = dict(self._data)
                if self._deleted:
                    payload["_deleted"] = self._deleted
                self._user_store.save(payload, durability=False)
                log.debug("[VOCAB] Saved user vocabulary")
                return
            except PermissionError as exc:
                final_exc = exc
                if attempt < max_retries - 1:
                    backoff = delay_for_attempt(save_delays, attempt)
                    log.warning(
                        "[VOCAB] PermissionError on save (attempt %d/%d), retrying in %.0fms: %s",
                        attempt + 1,
                        max_retries,
                        backoff * 1000,
                        exc,
                    )
                    sleep_interruptible(backoff)
                else:
                    log.exception(
                        "[VOCAB] Failed to save user vocabulary after %d attempts: %s",
                        max_retries,
                        exc,
                    )
            except OSError as exc:
                final_exc = exc
                # use log.exception so the traceback is
                log.exception("[VOCAB] Failed to save user vocabulary")
                break
        # surface the failure to callers so they can roll back
        if final_exc is not None:
            raise final_exc

    def get_category(self, category: str) -> object:
        """Get all entries for a category."""
        with self._lock:
            if category in ("misspellings", "technical_terms", "names", "products"):
                return dict(self._data.get(category, {}))
            return list(self._data.get(category, []))

    def get_all(self) -> dict:
        """Return a shallow copy of all merged data."""
        with self._lock:
            return {cat: (dict(v) if isinstance(v, dict) else list(v)) for cat, v in self._data.items()}

    def export_json(self) -> str:
        """Export all vocabulary as JSON string."""
        return json.dumps(self._data, indent=2, ensure_ascii=False)
