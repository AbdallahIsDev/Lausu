"""PII redaction filter and pipeline (SEC-009).

Extracted verbatim from :mod:`voice_typer.server.security.redaction`
(callers import these names from that facade). Pipeline ORDER is
semantic: home-path scrub, fast-trigger gate, control-char escape, PII
patterns, then secret redaction plus URL-userinfo scrubbing.

``PIIRedactionFilter.filter`` resolves ``_redact_text`` through the
facade at call time: tests monkeypatch
``voice_typer.server.security.redaction._redact_text``.
"""

from __future__ import annotations

import logging
import re
import traceback as _traceback

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.security.home_path_redaction import _redact_home_path_in_text
from voice_typer.server.security.secret_redaction import redact_secret, redact_url

_facade = lazy_module("voice_typer.server.security.redaction")


# ─── SEC-009: PII Redaction Filter ──────────────────────────────────────

# fast-path trigger for ``_redact_text``.  The redaction pass
_FAST_TRIGGER = re.compile(r"[@+]|\d{3,}|Bearer|Token|sk-|key=|(?<![/\\])[A-Za-z0-9_\-]{20,}(?![/\\])|[\x00-\x1f\x7f]")

# C0 control characters (plus DEL) that must be escaped before
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

def _escape_control_chars(text: str) -> str:
    """Replace C0 control characters with visible escapes.

    ``\n`` → the literal two-char sequence ``\\n``, ``\r`` → ``\\r``,
    ``\t`` → ``\\t``, and any other C0 control char / DEL → a
    ``\\xNN`` escape. The JSON formatter is unaffected (``json.dumps``
    escapes newlines anyway); the text formatters now emit the escaped
    form so a dictated ``"Hello\n[CRITICAL] fake"`` cannot forge a
    second disk line.
    """

    def _esc(m: re.Match[str]) -> str:
        ch = m.group(0)
        if ch == "\n":
            return "\\n"
        if ch == "\r":
            return "\\r"
        if ch == "\t":
            return "\\t"
        return f"\\x{ord(ch):02x}"

    return _CONTROL_CHAR_RE.sub(_esc, text)

def _redact_text(text: str, *, escape_control_chars: bool = True) -> str:
    """Apply PII + API-secret + URL-credential + home-path redaction to *text*.

    When ``escape_control_chars`` is True (default) C0 control chars are
    escaped so a payload cannot forge extra log lines. The
    ``PIIRedactionFilter`` traceback path passes False to preserve
    multi-line traceback readability, its structural newlines are not
    user-controlled, so there is no forgery risk there.

    shared helper used by :class:`PIIRedactionFilter` for both
    the formatted log message and the formatted traceback.  Order
    matters:

    1. PII patterns (email / phone / SSN / CC) are applied first so
       the specific token names (``[EMAIL]``, ``[PHONE]``, …) appear
       in the output rather than the more aggressive ``***`` mask
       produced by :func:`redact_secret`.
    2. :func:`redact_secret` is then applied to catch API keys and
       bearer tokens (``Bearer …``, ``Token …``, ``sk-…``, 20+ char
       bare tokens).  It is a no-op for strings shorter than 20
       characters, so short log lines are untouched.
    3. :func:`redact_url` strips ``user:pass@`` userinfo from URLs.
       Gated on ``"@" in text`` so the comparatively expensive
       :func:`urllib.parse.urlparse` call is skipped for the vast
       majority of log records that contain no ``@``.

    The redaction helpers are imported from :mod:`voice_typer.server._secrets`
    so the secret-matching patterns stay defined in exactly one place
    (no duplicated regexes).

    a single :data:`_FAST_TRIGGER` scan gates the whole pass.
    Every trigger in the alternation is a *necessary* condition for at
    least one downstream pattern to match, so a miss lets us return
    *text* unchanged without issuing the 8-12 ``re.sub`` calls (a
    5-10x speedup for the common log line that carries no secret /
    PII / URL-credential trigger).
    """
    # step 0, redact the home-directory prefix unconditionally.
    text = _redact_home_path_in_text(text)
    # fast path, no trigger means no pattern can match, so
    if not _FAST_TRIGGER.search(text):
        return text
    # Escape C0 control chars BEFORE the PII patterns so a
    if escape_control_chars:
        text = _escape_control_chars(text)
    for pattern, replacement in PIIRedactionFilter._PATTERNS:
        text = pattern.sub(replacement, text)
    text = redact_secret(text)
    if "@" in text:
        text = redact_url(text)
    return text

class PIIRedactionFilter(logging.Filter):
    """Redact potential PII and API secrets from log messages.

    Patterns redacted:
      - Email addresses → ``[EMAIL]``
      - Phone numbers (US-style 7-digit) → ``[PHONE]``
      - Phone numbers (international, E.164-ish) → ``[PHONE]``
        (covers ``+1 (415) 555-2671``, ``+44 20 7946 0958``,
        ``+86 10 1234 5678``; requires at least 7 trailing digits)
      - IBAN (international bank account number) → ``[IBAN]``
        (``GB82WEST12345698765432``,
        ``DE89370400440532013000``; 2-letter country + 2 check digits
        + 10-30 BBAN chars)
      - SSN-like patterns → ``[SSN]``
      - Credit-card-like patterns → ``[CC]``
      - API keys / bearer tokens (``Bearer …``, ``Token …``, ``sk-…``,
        20+ char bare tokens) → ``<prefix>***`` or ``***``
        (via :func:`voice_typer.server._secrets.redact_secret`)
      - URL-embedded credentials (``user:pass@host``) → credentials
        stripped, host preserved
        (via :func:`voice_typer.server._secrets.redact_url`)
      - Filesystem paths containing the user's home directory
        (``/home/alice/…``, ``/Users/alice/…``,
        ``C:\\Users\\alice\\…``) → home prefix replaced with ``~``
        (via :func:`voice_typer.server._secrets._redact_home_path`)

    Known limitations (NOT redacted, too high a false-positive rate
    on ordinary numeric text):

      - **US ABA routing numbers** (9-digit ``021000021`` form): the
        pattern is just 9 digits with no country prefix or check-digit
        structure; matching it would redact every 9-digit order ID,
        zip+4 extension, and timestamp fragment in operator logs.
        Operators who need routing-number redaction should add it
        explicitly at the call site (e.g. via a per-message
        ``re.sub`` before logging).

      - **Generic 9-20 digit numbers** (potential account / customer
        IDs): same false-positive concern.

    in addition to the formatted log message, the filter also
    pre-formats and redacts the traceback when ``record.exc_info`` is
    set.  The redacted text is cached on ``record.exc_text`` so any
    subsequent :class:`logging.Formatter` that appends ``exc_text``
    (including the default :meth:`logging.Formatter.format`) emits the
    redacted version.  This catches exceptions whose ``str(exc)``
    carries an API key: e.g. a ``requests.exceptions.ConnectionError``
    whose message includes ``?key=sk-…``: which would otherwise be
    emitted verbatim by ``log.error("...: %s", exc,
    exc_info=True)`` style call sites.

    The filter is idempotent: because a single instance is attached to
    several handlers (SEC-003), a record that already carries
    ``redacted_msg`` from a previous handler's pass is accepted
    (returns ``True``) WITHOUT re-running the scan, the first pass
    already mutated ``record.msg`` / ``record.exc_text`` in place, and
    redaction is idempotent, so the emitted bytes are unchanged.
    """

    _PATTERNS: list[tuple[re.Pattern[str], str]] = [
        # Email addresses
        (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
        # IBAN (international bank account number): 2-letter country
        (re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"), "[IBAN]"),
        # Phone numbers (US-style: 555-123-4567, 5551234567, 555.123.4567)
        (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE]"),
        # International phone numbers (E.164-ish and common domestic
        (re.compile(r"\+\d{1,3}[\s-]?\(?\d{1,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}\b"), "[PHONE]"),
        # SSN-like patterns
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
        # Credit card-like patterns
        (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CC]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        # file handler and the stderr handler (SEC-003, every sink must
        if getattr(record, "redacted_msg", None) is not None:
            return True

        msg = record.getMessage()
        msg = _facade._redact_text(msg)
        # mutation (the original SEC-009 behavior) because the existing
        record.redacted_msg = msg
        record.msg = msg
        record.args = ()

        # pre-format and redact the traceback so exceptions
        if record.exc_info:
            try:
                tb_text = "".join(_traceback.format_exception(*record.exc_info))
            except Exception:
                tb_text = ""
            if tb_text:
                # escape_control_chars=False: tracebacks keep their
                record.exc_text = _facade._redact_text(tb_text, escape_control_chars=False)
        return True

# ─── SEC-009: PII Redaction Helper ──────────────────────────────────────


def redact_pii(text: str) -> str:
    """Redact potential PII and API secrets from a text string.

    Standalone helper that applies the same redaction patterns as
    ``PIIRedactionFilter`` but can be used directly on arbitrary
    strings (e.g. before logging transcription text, error messages,
    or other user-visible content).

    previously this function only applied the four PII
    patterns (email / phone / SSN / CC). API keys, bearer tokens,
    and URL-embedded credentials passed through verbatim. The
    ``llm_polish.py`` docstring claimed API keys were covered, which
    was false. The function now also applies :func:`redact_secret`
    (API keys / bearer tokens) and :func:`redact_url` (URL userinfo)
    so it is a true single-call redaction helper. Existing callers
    that already chain ``redact_secret(redact_pii(...))`` see no
    behavioural change, both redactions are idempotent on already-
    redacted text.

    Patterns redacted:
      - Filesystem paths containing the user's home directory
        (``/home/alice/…``, ``/Users/alice/…``,
        ``C:\\Users\\alice\\…``) → home prefix replaced with ``~``
        (via :func:`_redact_home_path_in_text` /
        :func:`voice_typer.server._secrets._redact_home_path`)
      - Email addresses → [EMAIL]
      - Phone numbers (US-style 7-digit) → [PHONE]
      - Phone numbers (international, E.164-ish) → [PHONE]
        (``+1 (415) 555-2671``, ``+44 20 7946 0958``)
      - IBAN (international bank account number) → [IBAN]
        (``GB82WEST12345698765432``)
      - SSN-like patterns → [SSN]
      - Credit-card-like patterns → [CC]
      - API keys / bearer tokens (``Bearer …``, ``Token …``, ``sk-…``,
        20+ char bare tokens) → ``<prefix>***`` or ``***``
        (via :func:`voice_typer.server._secrets.redact_secret`)
      - URL-embedded credentials (``user:pass@host``) → credentials
        stripped, host preserved
        (via :func:`voice_typer.server._secrets.redact_url`)

    The home-path redaction runs FIRST (mirroring :func:`_redact_text`)
    so a bare path like ``/home/alice/.lausu/foo.log`` is
    sanitised before any of the pattern substitutions see it. This
    closes a PII leak in the cloud-LLM call path (``llm_polish.py``),
    the hallucination filter, the config sanitizer, and the diagnostic
    bundle exporter, all of which call ``redact_pii`` directly or
    indirectly via ``redact_for_export``.

    Known limitations (NOT matched): US ABA routing numbers
    (9-digit form, too high a false-positive rate on ordinary numeric
    text: see ``PIIRedactionFilter`` docstring for details).

    Parameters
    ----------
    text : str
        Input text that may contain PII.

    Returns
    -------
    str
        Text with PII patterns replaced by redaction tokens.
    """
    # step 0, redact the home-directory prefix unconditionally.
    text = _redact_home_path_in_text(text)
    for pattern, replacement in PIIRedactionFilter._PATTERNS:
        text = pattern.sub(replacement, text)
    # also redact API keys / bearer tokens (idempotent on
    text = redact_secret(text)
    # also strip URL userinfo. Gated on ``"@" in text`` for
    if "@" in text:
        text = redact_url(text)
    return text


# → SEC-009.


# stderr buffer) unredacted, defeating the SEC-009 /  redaction


def install_lastresort_pii_filter() -> logging.Handler:
    """Install PIIRedactionFilter on ``logging.lastResort``.

    Replaces Python's default last-resort handler (a bare
    :class:`logging.StreamHandler` writing to ``sys.stderr`` at
    WARNING level) with an equivalent handler that carries a
    :class:`PIIRedactionFilter`. This ensures third-party logger
    output (``keyring``, ``urllib3``, ``websockets``) is PII-redacted
    before reaching stderr, closing the gap documented above.

    Returns
    -------
    logging.Handler
        The new last-resort handler (also assigned to
        ``logging.lastResort``).

    Notes
    -----
    Idempotent. Safe to call multiple times, each call replaces the
    prior handler rather than stacking filters.
    """
    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)
    handler.addFilter(PIIRedactionFilter())
    logging.lastResort = handler
    return handler
