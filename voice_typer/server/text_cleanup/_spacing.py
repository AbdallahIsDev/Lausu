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


def _space_after_punct(match: re.Match[str]) -> str:
    """Insert the separating space, except between two digits.

    ``1.7`` is a decimal, not a sentence break: blindly padding every dot
    turned every number into ``1. 7``.
    """
    punct = match.group(1)
    if punct == ".":
        text = match.string
        start = match.start()
        if 0 < start < len(text) - 1 and text[start - 1].isdigit() and text[start + 1].isdigit():
            return punct
    return punct + " "


def _normalize_spacing(text: str) -> str:
    # PERF-004: use precompiled patterns
    text = _RE_SPACING_WS.sub(" ", text).strip()
    text = _RE_SPACING_PUNCT_BEFORE.sub(r"\1", text)
    text = _RE_SPACING_PUNCT_AFTER.sub(_space_after_punct, text)
    return text.strip()
