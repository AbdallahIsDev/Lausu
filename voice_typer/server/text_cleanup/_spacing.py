"""Whitespace / punctuation-spacing normalization for text cleanup.

Holds the precompiled spacing regexes (PERF-004) and the single
``_normalize_spacing`` pass. Moved verbatim out of ``text_cleanup._engine``,
which re-exports both names so historical import paths keep resolving.
"""

from __future__ import annotations

import re

# PERF-004: precompile all regex patterns at module level to avoid
_RE_SPACING_WS = re.compile(r"\s+")
_RE_SPACING_PUNCT_BEFORE = re.compile(r"\s+([,.;:!?])")
_RE_SPACING_PUNCT_AFTER = re.compile(r"([,.;:!?])(?=[^\s,.;:!?])")


def _normalize_spacing(text: str) -> str:
    # PERF-004: use precompiled patterns
    text = _RE_SPACING_WS.sub(" ", text).strip()
    text = _RE_SPACING_PUNCT_BEFORE.sub(r"\1", text)
    text = _RE_SPACING_PUNCT_AFTER.sub(r"\1 ", text)
    return text.strip()
