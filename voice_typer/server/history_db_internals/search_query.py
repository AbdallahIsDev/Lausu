"""Query shaping for history search (LIKE escaping, FTS5, CJK/trigram).

Pure string helpers: they decide which index a query can use and build the
matching pattern; the SQL execution lives in ``search``.
"""

from __future__ import annotations

import re

# Search / LIKE / FTS5 helpers


def prepare_like_search_pattern(query: str) -> str:
    """Build a bounded LIKE pattern where user wildcards stay literal."""
    # ``_MAX_SEARCH_QUERY_CHARS`` lives on the history_db module so tests
    from voice_typer.server import history_db as _hd

    capped_query = query[: _hd._MAX_SEARCH_QUERY_CHARS]
    escaped_query = capped_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped_query}%"


def is_fts_compatible_query(query: str) -> bool:
    """True when FTS5 can serve the query; separator-only queries fall back to LIKE."""
    from voice_typer.server import history_db as _hd

    capped = query[: _hd._MAX_SEARCH_QUERY_CHARS]
    # ``\W`` matches [^a-zA-Z0-9_] in ASCII mode, but with re.UNICODE
    stripped = re.sub(r"[\W_]+", "", capped, flags=re.UNICODE)
    return bool(stripped)


# Scripts unicode61 cannot substring-match (CJK runs index as one token);
_CJK_WIDE_CODEPOINT_RANGES: tuple[tuple[int, int], ...] = (
    (0x1100, 0x11FF),
    (0x3000, 0x303F),
    (0x3040, 0x30FF),
    (0x3130, 0x318F),
    (0x31F0, 0x31FF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0xAC00, 0xD7AF),
    (0xFF00, 0xFFEF),
    (0x20000, 0x2FA1F),
)


def has_cjk_or_wide_chars(query: str) -> bool:
    """True when the query needs the LIKE path for CJK/fullwidth substring semantics."""
    from voice_typer.server import history_db as _hd

    capped = query[: _hd._MAX_SEARCH_QUERY_CHARS]
    return any(lo <= codepoint <= hi for codepoint in map(ord, capped) for lo, hi in _CJK_WIDE_CODEPOINT_RANGES)


# Trigram indexes only 3-char substrings; shorter CJK queries stay on LIKE.
_TRIGRAM_MIN_QUERY_CHARS = 3


def _build_trigram_phrase(query: str) -> str:
    """Build the FTS5 MATCH phrase for the trigram CJK path."""
    return '"' + query.replace('"', '""') + '"'


def is_trigram_cjk_query(query: str) -> bool:
    """True when the query should use the trigram CJK index."""
    from voice_typer.server import history_db as _hd

    capped = query[: _hd._MAX_SEARCH_QUERY_CHARS]
    return len(capped) >= _TRIGRAM_MIN_QUERY_CHARS and has_cjk_or_wide_chars(capped)


def sanitize_fts_query(query: str) -> str:
    """Escape FTS5 syntax so user input matches as literals."""
    from voice_typer.server import history_db as _hd

    capped = query[: _hd._MAX_SEARCH_QUERY_CHARS]
    tokens = capped.split()
    if not tokens:
        # Shouldn't happen (caller checks is_fts_compatible_query), but
        return '""'
    # Wrap each token in double quotes. Escape any embedded double
    quoted = []
    for tok in tokens:
        escaped_tok = tok.replace('"', '""')
        quoted.append(f'"{escaped_tok}"')
    return " ".join(quoted)
