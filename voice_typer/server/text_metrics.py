"""Shared text measurements used by history writes and completion events."""

from __future__ import annotations


def count_words(text: str) -> int:
    """Whitespace-delimited word count used for the history ``word_count``."""
    return len(text.split())
