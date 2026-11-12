"""Verdict-cache predicate for pinned model files.

This file exists so that a pinned file's cached digest may skip
re-hashing only when every freshness signal agrees. See
docs/code-notes/security-config.md#model-integrity-cache for the
residual same-user forgery note.
"""

from __future__ import annotations

import hmac
from typing import Any


def verdict_cache_hit(entry: Any, *, mtime_ns: int, size: int, expected_hash: str) -> bool:
    """Return True only when a cache entry may decide a pinned verdict.

    Requires ALL of: entry is a dict, its ``mtime_ns`` and ``size``
    are plain ints equal to the file's current stat, ``size`` is
    positive, and its ``sha256`` equals the pinned manifest hash.
    mtime alone never hits: a size mismatch misses even when mtime
    matches, as does a cached digest that differs from the pin.
    """
    if not isinstance(entry, dict):
        return False
    if not isinstance(expected_hash, str) or not expected_hash:
        return False
    cached_mtime = entry.get("mtime_ns")
    cached_size = entry.get("size")
    cached_sha = entry.get("sha256")
    # bool is an int subclass; a JSON bool must not pose as metadata.
    if type(cached_mtime) is not int or type(cached_size) is not int:
        return False
    if cached_mtime != mtime_ns or cached_size != size:
        return False
    # Empty pinned files never satisfy the verdict.
    if size <= 0:
        return False
    if not isinstance(cached_sha, str):
        return False
    return hmac.compare_digest(cached_sha, expected_hash)
