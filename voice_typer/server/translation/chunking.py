"""Stage B token-bounded chunking for final text that would not fit the model.

Short text keeps the single ADR-0021 §5.2 call. Group chunking is only a
fallback for over-long text: it keeps the skip decision, glossary and protected
spans intact and uses the one already-loaded runtime.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from voice_typer.server.translation.prompt import _SCRIPTS

CONTEXT_TOKENS = 4096
MAX_OUTPUT_TOKENS = 1024
# Measured with the installed /tokenize endpoint: system 15 + user shell 22 +
# template framing 17 = 54 tokens. Glossary (<=24 pins) and marker list can add
# hundreds more, so reserve them instead of adding a tokenizer round-trip.
SHELL_RESERVE_TOKENS = 768
SAFETY_MARGIN_TOKENS = 128
SAFE_INPUT_TOKENS = CONTEXT_TOKENS - MAX_OUTPUT_TOKENS - SHELL_RESERVE_TOKENS - SAFETY_MARGIN_TOKENS

# Tokens per character measured on the installed model (build b12521-6f311d7ad):
# English max 0.1924, Arabic max 0.2983, rounded up. Unmeasured scripts get
# deliberately higher densities so the estimate never undercounts.
_LATIN_PER_CHAR = 0.20
_ARABIC_PER_CHAR = 0.32
_CYRILLIC_PER_CHAR = 0.60
_DEVANAGARI_PER_CHAR = 0.80
_HAN_PER_CHAR = 1.00
_SPACE_PER_CHAR = 0.20
_OTHER_PER_CHAR = 0.50

DEFAULT_MAX_CHARS = 1600
_SENTENCE_SPLIT = re.compile(r"((?<=[.!?。！？؟])\s+|\n+)")
_PARAGRAPH_SPLIT = re.compile(r"(\n+)")
_WORD_WITH_TAIL = re.compile(r"\s+|\S+\s*")


def estimate_tokens(text: str) -> int:
    """Conservative token estimate from measured per-script densities."""
    total = 0.0
    for char in text:
        if char.isspace():
            total += _SPACE_PER_CHAR
        elif _SCRIPTS["han"].match(char):
            total += _HAN_PER_CHAR
        elif _SCRIPTS["devanagari"].match(char):
            total += _DEVANAGARI_PER_CHAR
        elif _SCRIPTS["cyrillic"].match(char):
            total += _CYRILLIC_PER_CHAR
        elif _SCRIPTS["arabic"].match(char):
            total += _ARABIC_PER_CHAR
        elif _SCRIPTS["latin"].match(char):
            total += _LATIN_PER_CHAR
        else:
            total += _OTHER_PER_CHAR
    return math.ceil(total)


def _paragraph_units(text: str) -> Iterable[str]:
    parts = _PARAGRAPH_SPLIT.split(text)
    for index in range(0, len(parts), 2):
        content = parts[index]
        separator = parts[index + 1] if index + 1 < len(parts) else ""
        if content or separator:
            yield content + separator


def _sentence_units(text: str) -> Iterable[str]:
    for part in _SENTENCE_SPLIT.split(text):
        if part:
            yield part


def _hard_split(text: str, max_tokens: int) -> Iterable[str]:
    """Last resort for one over-long sentence: whitespace, then char cut."""
    for word in _WORD_WITH_TAIL.findall(text):
        if len(word) <= max_tokens:
            yield word
        else:
            for start in range(0, len(word), max_tokens):
                yield word[start : start + max_tokens]


def group_chunks(text: str, max_tokens: int = SAFE_INPUT_TOKENS) -> list[str]:
    """Group consecutive sentences into bounded chunks; join returns the input.

    Paragraph boundaries win; a paragraph that is itself too long falls back to
    sentence boundaries, then whitespace. Protected markers contain no
    whitespace, so none of those boundaries can cut one in half.
    """
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    chunks: list[str] = []
    current: list[str] = []
    used = 0

    def flush() -> None:
        nonlocal used
        if current:
            chunks.append("".join(current))
            current.clear()
            used = 0

    for paragraph in _paragraph_units(text):
        estimate = estimate_tokens(paragraph)
        if used + estimate <= max_tokens:
            current.append(paragraph)
            used += estimate
            continue
        if estimate <= max_tokens:
            flush()
            current.append(paragraph)
            used = estimate
            continue
        flush()
        for unit in _sentence_units(paragraph):
            unit_estimate = estimate_tokens(unit)
            if unit_estimate > max_tokens:
                for piece in _hard_split(unit, max_tokens):
                    piece_estimate = estimate_tokens(piece)
                    if used + piece_estimate > max_tokens:
                        flush()
                    current.append(piece)
                    used += piece_estimate
                continue
            if used + unit_estimate > max_tokens:
                flush()
            current.append(unit)
            used += unit_estimate
    flush()
    return chunks


def boundary_separator(left: str, right: str) -> str:
    """Only the whitespace that actually sat between two source chunks."""
    return left[len(left.rstrip()) :] + right[: len(right) - len(right.lstrip())]


def join_translations(chunks: Sequence[str], translations: Sequence[str]) -> str:
    """Re-attach each source separator; never invent one (C-TRANS-2)."""
    if len(chunks) != len(translations):
        raise ValueError("chunk and translation counts must match")
    if not translations:
        return ""
    out = [translations[0]]
    for index in range(1, len(translations)):
        out.append(boundary_separator(chunks[index - 1], chunks[index]))
        out.append(translations[index])
    return "".join(out)


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
