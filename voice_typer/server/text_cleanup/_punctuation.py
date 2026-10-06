"""Terminal punctuation + question detection for text cleanup.

Auto-punctuation is OFF by default (enabled via config) and guarded
against URLs, file paths, inline code and template variables.
``_looks_like_question`` is also consumed directly by
``ai_enhancement.py`` through the ``text_cleanup`` package. Moved
verbatim out of ``text_cleanup._engine``, which re-exports every name.
"""

from __future__ import annotations

import re
from typing import Final

from ._corrections_data import _QUESTION_OPENERS

# precompile the regexes used in _looks_like_question. Previously
_RE_SENTENCE_SPLIT = re.compile(r"[.!?]\s+")
_RE_WORD_CHARS = re.compile(r"[A-Za-z']+")

# minimum word count before ``_add_safe_terminal_punctuation``
_MIN_WORDS_FOR_TERMINAL_PUNCTUATION: Final[int] = 4

# Patterns that should NOT get terminal punctuation appended
_NO_PUNCTUATION_PATTERNS = [
    re.compile(r"https?://"),  # URLs
    re.compile(r"\.(com|org|net|io|dev)$", re.IGNORECASE),  # Domain names
    re.compile(r"[\\/]"),  # File paths
    re.compile(r"`[^`]*`"),  # Inline code
    re.compile(r"\{\{.*\}\}"),  # Template variables
    re.compile(r"\{.*\}"),  # Variable placeholders
]


def _add_safe_terminal_punctuation(text: str) -> str:
    """Add terminal punctuation with safety guards for URLs, paths, code.

    This version of auto-punctuation checks for patterns that should
    NOT receive punctuation before appending.
    """
    if not text or text[-1] in ".!?":
        return text

    # Check safety patterns, don't add punctuation if any match
    for pattern in _NO_PUNCTUATION_PATTERNS:
        if pattern.search(text):
            return text

    words = text.split()
    # the magic ``4``-word cutoff was extracted to a named
    if len(words) <= _MIN_WORDS_FOR_TERMINAL_PUNCTUATION:
        return text

    if _looks_like_question(text):
        return f"{text}?"
    return f"{text}."


def _looks_like_question(text: str) -> bool:
    """Detect whether the final sentence looks like a question.

        Uses a conservative set of question openers that excludes "how"
        and "what" to avoid false positives on declarative sentences.

    uses the module-level precompiled ``_RE_SENTENCE_SPLIT`` and
        ``_RE_WORD_CHARS`` patterns instead of ``re.split`` / ``re.findall``
        with uncompiled string patterns.
    """
    sentence = _RE_SENTENCE_SPLIT.split(text.strip())[-1]
    words = _RE_WORD_CHARS.findall(sentence.lower())
    if not words:
        return False
    if words[0] in _QUESTION_OPENERS:
        return True
    question_starters = {
        ("do", "you"),
        ("did", "you"),
        ("can", "you"),
        ("could", "you"),
        ("would", "you"),
        ("should", "we"),
    }
    return len(words) >= 2 and tuple(words[:2]) in question_starters
