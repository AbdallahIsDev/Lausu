"""Token-level cleanup rules for text cleanup.

Token-key normalization (PERF-PIPE) plus the state-free token transforms:
self-correction removal, adjacent duplicate-phrase removal, and near
duplicate-word removal. Moved verbatim out of ``text_cleanup._engine``,
which re-exports every name here. The corrections-backed misspelling rule
stays in ``_engine`` because it reads the live active-misspellings state.
"""

from __future__ import annotations

import functools
import re

from ._corrections_data import _INTENTIONAL_REPEAT_WORDS

# PERF-PIPE: precompile the regex used in _token_key at module level.
_RE_TOKEN_KEY = re.compile(r"^\W+|\W+$")


@functools.lru_cache(maxsize=4096)
def _token_key(token: str) -> str:
    # PERF-PIPE: use precompiled regex instead of re.sub(pattern, ...)
    return _RE_TOKEN_KEY.sub("", token).lower()


def _clean_self_corrections_tokens(tokens: list[str]) -> list[str]:
    """Token-based core of ``_clean_self_corrections``.

    factored out so ``clean_transcribed_text`` can tokenize the
    dictation once and pass the token list through the four token-based
    helpers without re-splitting + re-joining between each step.
    """
    output: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        if i + 1 < n:
            key1 = _token_key(tokens[i])
            key2 = _token_key(tokens[i + 1])
            if key1 and key2 and key1 != key2:
                # Direct prefix/suffix match (e.g., "talk" → "talking")
                if key2.startswith(key1) or key1.startswith(key2):
                    output.append(tokens[i + 1])
                    i += 2
                    continue
                # Shared root with common prefix of 4+ chars
                if len(key1) >= 4 and len(key2) >= 4:
                    common = 0
                    for a, b in zip(key1, key2, strict=False):
                        if a == b:
                            common += 1
                        else:
                            break
                    if common >= 4:
                        output.append(tokens[i + 1])
                        i += 2
                        continue
        output.append(tokens[i])
        i += 1
    return output


def _clean_self_corrections(text: str) -> str:
    """Remove self-correction patterns like 'talk talking' → 'talking'."""
    return " ".join(_clean_self_corrections_tokens(text.split(" ")))


def _remove_adjacent_duplicate_phrases_tokens(tokens: list[str]) -> list[str]:
    """Token-based core of ``_remove_adjacent_duplicate_phrases`` ()."""
    output: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        duplicate_len = _duplicate_phrase_length(tokens, i)
        if duplicate_len:
            output.extend(tokens[i : i + duplicate_len])
            i += duplicate_len * 2
        else:
            output.append(tokens[i])
            i += 1
    return output


def _remove_adjacent_duplicate_phrases(text: str) -> str:
    return " ".join(_remove_adjacent_duplicate_phrases_tokens(text.split(" ")))


def _duplicate_phrase_length(tokens: list[str], index: int) -> int:
    max_len = min(4, (len(tokens) - index) // 2)
    for size in range(max_len, 0, -1):
        left = [_token_key(token) for token in tokens[index : index + size]]
        right = [_token_key(token) for token in tokens[index + size : index + (size * 2)]]
        if left == right and any(left):
            if size == 1 and left[0] in _INTENTIONAL_REPEAT_WORDS:
                continue
            return size
    return 0


def _remove_near_duplicate_words_tokens(tokens: list[str]) -> list[str]:
    """Token-based core of ``_remove_near_duplicate_words`` ()."""
    output: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        if i + 1 < n:
            key1 = _token_key(tokens[i])
            key2 = _token_key(tokens[i + 1])
            if key1 and key2 and key1 != key2:
                if len(key1) < 4 or len(key2) < 4:
                    output.append(tokens[i])
                    i += 1
                    continue
                if key1 in _INTENTIONAL_REPEAT_WORDS or key2 in _INTENTIONAL_REPEAT_WORDS:
                    output.append(tokens[i])
                    i += 1
                    continue
                if abs(len(key1) - len(key2)) <= 2 and (key1 in key2 or key2 in key1):
                    longer = tokens[i] if len(key1) >= len(key2) else tokens[i + 1]
                    output.append(longer)
                    i += 2
                    continue
        output.append(tokens[i])
        i += 1
    return output


def _remove_near_duplicate_words(text: str) -> str:
    """Remove adjacent words where one is a substring of the other."""
    return " ".join(_remove_near_duplicate_words_tokens(text.split(" ")))
