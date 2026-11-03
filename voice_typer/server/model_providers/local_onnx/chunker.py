"""Sentence-packed chunking for small local text models.

Measured on the owner's dictations: a 2B int4 model copies its input past ~150
words, so every local polish call is bounded by sentence-packed chunks that never
cut mid-sentence.
"""

from __future__ import annotations

import re

MIN_CHUNK_WORDS = 120
MAX_CHUNK_WORDS = 200

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n{2,}")
_CLAUSE_BREAK = re.compile(r"(?<=[,;:])\s+")


def _words(text: str) -> int:
    return len(text.split())


def _split_long_sentence(sentence: str, max_words: int) -> list[str]:
    """Split one over-long sentence on clause boundaries, then words."""
    if _words(sentence) <= max_words:
        return [sentence]
    parts: list[str] = []
    current: list[str] = []
    for clause in _CLAUSE_BREAK.split(sentence):
        if _words(clause) > max_words:
            words = clause.split()
            for start in range(0, len(words), max_words):
                parts.append(" ".join(words[start : start + max_words]))
            continue
        candidate = " ".join([*current, clause]).strip()
        if current and _words(candidate) > max_words:
            parts.append(" ".join(current))
            current = [clause]
        else:
            current.append(clause)
    if current:
        parts.append(" ".join(current))
    return [p.strip() for p in parts if p.strip()]


def _sentences(text: str, max_words: int) -> list[str]:
    out: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        out.extend(_split_long_sentence(sentence, max_words))
    return out


def chunk_sentences(
    text: str,
    *,
    min_words: int = MIN_CHUNK_WORDS,
    max_words: int = MAX_CHUNK_WORDS,
) -> list[str]:
    """Pack whole sentences into chunks of at most ``max_words`` words.

    A chunk closes only when adding the next sentence would exceed
    ``max_words`` (so ``min_words`` is a preference, never a reason to cut a
    sentence); a trailing chunk shorter than half of ``min_words`` is merged
    backwards so no call receives a fragment.
    """
    if max_words <= 0:
        raise ValueError("max_words must be positive")
    text = (text or "").strip()
    if not text:
        return []
    sentences = _sentences(text, max_words)
    chunks: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        if current and _words(" ".join([*current, sentence])) > max_words:
            chunks.append(" ".join(current))
            current = [sentence]
            continue
        current.append(sentence)
    if current:
        if chunks and _words(" ".join(current)) < min_words // 2:
            chunks[-1] = f"{chunks[-1]} {' '.join(current)}"
        else:
            chunks.append(" ".join(current))
    return [c.strip() for c in chunks if c.strip()]


__all__ = [
    "MAX_CHUNK_WORDS",
    "MIN_CHUNK_WORDS",
    "chunk_sentences",
]
