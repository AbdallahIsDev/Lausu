"""Protect non-translatable spans before a translation model call.

URLs, email addresses, inline code, numbers and product IDs must come back
byte-identical. They are swapped for opaque markers in the model prompt and
restored afterwards, so an otherwise correct translation cannot rewrite a
link, an identifier or a measurement. A second helper removes the same spans
for language detection, so a URL full of Latin letters never makes an Arabic
sentence look "mixed".
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# One pass, longest/most-specific first: a URL must win over the bare number
# that appears inside it, and an email over its own local-part digits.
_SPAN_RE = re.compile(
    r"(?P<url>https?://[^\s<>\"']+|www\.[^\s<>\"']+)"
    r"|(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    r"|(?P<code>`[^`\n]+`)"
    r"|(?P<number>\b\d+(?:[.,:/-]\d+)*(?:\s?(?:%|kg|km|cm|mm|px|ms|USD|EGP|\$|€))?\b)"
)


def protect_spans(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return ``(prompt_text, [(marker, original), ...])``.

    Markers are deliberately unlikely to be produced by a translator and are
    reinserted verbatim by :func:`restore_spans`.
    """
    spans: list[tuple[str, str]] = []

    def _sub(match: re.Match[str]) -> str:
        marker = f"\u27e6VT{len(spans)}\u27e7"  # ⟦VT0⟧
        spans.append((marker, match.group(0)))
        return marker

    return _SPAN_RE.sub(_sub, text), spans


def unprotected_text(text: str) -> str:
    """Text with protected spans removed, used for script-based detection."""
    return _SPAN_RE.sub(" ", text)


def restore_spans(text: str, spans: list[tuple[str, str]]) -> str:
    """Replace every marker with its original span; log anything dropped."""
    result = text
    for marker, original in spans:
        if marker in result:
            result = result.replace(marker, original)
        elif original not in result:
            log.warning("[TRANSLATE] protected span %s missing from model output", marker)
    return result
