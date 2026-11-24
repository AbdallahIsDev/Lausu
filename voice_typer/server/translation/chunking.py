"""Opt-in chunking and segment-alignment helpers for Stage B.

ADR-0021 §5.2 locks the dictation path to ONE request for the whole Stage A
text. Nothing in the dictation pipeline calls this module. These helpers exist
for the local benchmark and for a future, owner-approved media Stage B: they
never drop characters and never move timestamps.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

DEFAULT_MAX_CHARS = 1600
_SENTENCE_SPLIT = re.compile(r"((?<=[.!?。！？؟])\s+|\n+)")
_WORD_WITH_TAIL = re.compile(r"\s+|\S+\s*")


def _units(text: str, max_chars: int) -> Iterable[str]:
    """Yield sentence parts, falling back to word units for very long parts."""
    for part in _SENTENCE_SPLIT.split(text):
        if not part:
            continue
        if len(part) <= max_chars:
            yield part
        else:
            for word in _WORD_WITH_TAIL.findall(part):
                if len(word) > max_chars:
                    for start in range(0, len(word), max_chars):
                        yield word[start : start + max_chars]
                else:
                    yield word


def bounded_chunks(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Split on sentence boundaries, packing units up to ``max_chars``.

    ``"".join(bounded_chunks(text)) == text`` always holds; protected-span
    markers contain no whitespace, so they are never cut in half.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    chunks: list[str] = []
    current: list[str] = []
    used = 0
    for unit in _units(text, max_chars):
        if current and used + len(unit) > max_chars:
            chunks.append("".join(current))
            current, used = [], 0
        current.append(unit)
        used += len(unit)
    if current:
        chunks.append("".join(current))
    return chunks


def translate_segments(
    segments: Iterable[dict[str, Any]],
    translate_fn: Callable[[str], str],
    *,
    text_key: str = "text",
) -> list[dict[str, Any]]:
    """Translate segment text while keeping every other field byte-identical.

    Start/end times, speaker ids and ordering belong to Stage A; a future media
    Stage B replaces only the text. Errors are the caller's responsibility so
    the ADR-0021 failure rule (original text + one notice) stays in one place.
    """
    out: list[dict[str, Any]] = []
    for segment in segments:
        copy = dict(segment)
        copy[text_key] = translate_fn(str(segment.get(text_key, "")))
        out.append(copy)
    return out
