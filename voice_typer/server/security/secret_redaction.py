"""Secret redaction helpers: API keys, bearer tokens, URL userinfo.

Extracted verbatim from :mod:`voice_typer.server.security.redaction`
(callers import these names from that facade). Pattern ORDER inside each
function is semantic (specific prefixed / labeled forms run before the
generic catch-all; flag forms run before bare ``key=value`` forms) and
is preserved exactly.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from voice_typer.server.security.secret_patterns import (
    _BINARY_LABEL_RE,
    _DASH_JOINED_FULL_RE,
    _FLAG_KEY_PATTERNS,
    _HASH_LABEL_RE,
    _KEY_PATTERNS,
    _MIN_REDACT_LEN,
    _PROPSET_LABEL_RE,
    _PUBLIC_ENV_VAR_NAMES,
    _TEARDOWN_LABEL_RE,
    _THREAD_LABEL_RE,
    _flag_sub,
    _public_config_field_names,
    _public_ipc_command_names,
)


def redact_secret(value: object, *, aggressive: bool = False) -> str:
    """Redact API keys and bearer tokens from a value.

        Parameters
        ----------
        value : object
            Any value; non-strings are stringified via ``str(value)``.
        aggressive : bool, default False
    when True, BYPASS the ``_MIN_REDACT_LEN`` short-string
            guard so bare short secrets (e.g. a 12-char bare API key with
            no ``Bearer``/``Token``/``--token=`` prefix) are still passed
            through :func:`redact_api_keys`. Use this only in contexts
            where short bare secrets are plausible (e.g. the crash
            excepthook path that dumps arbitrary object repr() into the
            crash marker, or an env-var audit). Default False so ordinary
            log lines retain the short-string guard against false positives
            on ordinary words.

        Returns
        -------
        str
            The value with likely-secret substrings replaced by
            ``"<prefix>***"`` (for prefixed patterns like ``Bearer``) or
            ``"***"`` (for bare keys).  Short strings (under
            ``_MIN_REDACT_LEN`` characters and not matching any prefix
            pattern) are returned unchanged so ordinary error messages
            aren't mangled. UNLESS ``aggressive=True`` is passed, in which
            case the short-string guard is skipped.

        Notes
        -----
        This is a best-effort heuristic.  It will not catch every possible
        secret format, and it may occasionally redact a non-secret that
        happens to look like one.  The goal is to make log-grepping for
        leaked keys reliable, not to provide cryptographic guarantees.

        SEC-9: explicit flag / key=value forms (``--token=abc``,
        ``--token abc``, ``token=abc``) are matched BEFORE the
        ``_MIN_REDACT_LEN`` short-string guard because the keyword
        constraint makes them specific enough to be safe on short inputs.

    known gap: a BARE short secret (e.g. a 12-char bare API
        key with no keyword prefix) is NOT redacted when
        ``aggressive=False``. The ``_MIN_REDACT_LEN`` guard (default 20)
        skips generic-pattern application on short strings to avoid
        false-positives on ordinary words (e.g. ``"helloworld"`` would
        match the 20+ char alphanumeric run pattern but isn't a secret).
        Callers in security-critical contexts where bare short secrets are
        plausible SHOULD pass ``aggressive=True`` to bypass the length
        guard. The crash-excepthook path and env-var audit are the two
        known callers that benefit from this opt-in.
    """
    if value is None:
        return "None"
    if not isinstance(value, str):
        value = str(value)
    # SEC-9: apply the specific flag / key=value patterns first so
    redacted = value
    for pat in _FLAG_KEY_PATTERNS:
        redacted = pat.sub(_flag_sub, redacted)
    # Early-exit for short strings: skip the more-generic patterns
    if not aggressive and len(value) < _MIN_REDACT_LEN:
        return redacted
    # delegate the API-key-pattern application to the shared
    return redact_api_keys(redacted)


def redact_api_keys(text: str, *, replacement: str = "***") -> str:
    """Redact API keys and bearer tokens from ``text`` (configurable marker).

        This is the **canonical API-key redaction helper** for the codebase.
        It applies :data:`_KEY_PATTERNS` (Bearer / Token / ``sk-`` / generic
        20+ char alphanumeric run) to ``text`` and substitutes each match
        with ``replacement``. Patterns that capture a prefix group
        (``Bearer `` / ``Token ``) preserve the prefix; the secret portion
        is replaced. Patterns without a prefix group replace the whole
        match.

    (DRY consolidation): prior to this helper, the API-key
        pattern knowledge was duplicated between this module
        (:data:`_KEY_PATTERNS`) and ``credential_store._API_KEY_RE``
        (a separate single-regex with different thresholds). The two
        representations drifted, the credential_store version missed
        ``Bearer`` / ``Token`` auth and required 32+ chars for the generic
        catch-all, while this module's version matched 20+ chars and
        recognized the auth-header prefixes. ``redact_api_keys`` is now the
        single source of truth: :func:`redact_secret` (log-message
        redaction, default ``"***"``) and
        ``credential_store._redact_sensitive`` (IPC-bound keyring-exception
        redaction, ``"[redacted]"``) both call it.

        Parameters
        ----------
        text : str
            The text to redact. Must already be a string, callers
            converting from ``object`` should call ``str(value)`` first,
            or use :func:`redact_secret` which does that automatically.
        replacement : str
            The substring to substitute for each redacted secret. Defaults
            to ``"***"`` (the conventional log-redaction marker used by
            :func:`redact_secret`). Use ``"[redacted]"`` for IPC-bound
            messages that the renderer surfaces to the user (matching the
            convention used by ``credential_store._redact_sensitive``).

        Returns
        -------
        str
            ``text`` with every match from :data:`_KEY_PATTERNS` replaced
            by ``replacement`` (or ``prefix + replacement`` for prefix
            patterns).

        Notes
        -----
        Unlike :func:`redact_secret`, this helper:

        - Does **not** apply the SEC-9 flag / ``key=value`` patterns
          (:data:`_FLAG_KEY_PATTERNS`). Those patterns are specific to
          log-message redaction where CLI flag forms (``--token=abc``)
          are common; IPC-bound keyring exception messages don't contain
          flag forms, so applying them there would be needless work (and
          a behavior change for ``credential_store._redact_sensitive``,
          which never had them).
        - Does **not** apply the :data:`_MIN_REDACT_LEN` short-string
          early-exit guard. Short inputs are still effectively pass-through
          because the generic 20+ char alphanumeric pattern only fires on
          long runs, and the prefix patterns (``Bearer`` / ``Token`` /
          ``sk-``) are specific enough to be safe on any length.
        - Does **not** stringify non-string input. Callers must convert
          explicitly (or use :func:`redact_secret`).
    """

    # hoisted _sub out of the loop (was re-created per pattern per call
    def _sub(m: re.Match[str]) -> str:
        if m.lastindex:
            # Pattern has a prefix group (e.g. "Bearer ").  Keep
            return m.group(1) + replacement
        # No prefix group, redact the whole match.
        return replacement

    # Labeled-value shields (see ``_HASH_LABEL_RE`` /
    shields: list[str] = []

    def _shield(m: re.Match[str]) -> str:
        shields.append(m.group(0))
        return f"KEPT{len(shields) - 1:04d}X"

    text = _HASH_LABEL_RE.sub(_shield, text)
    text = _PROPSET_LABEL_RE.sub(_shield, text)
    text = _THREAD_LABEL_RE.sub(_shield, text)
    text = _BINARY_LABEL_RE.sub(_shield, text)
    text = _TEARDOWN_LABEL_RE.sub(_shield, text)

    # Generic 20+ char alphanumeric pattern (last entry in
    generic_pat = _KEY_PATTERNS[-1]

    def _generic_sub(m: re.Match[str]) -> str:
        token = m.group()
        if token in _PUBLIC_ENV_VAR_NAMES:
            return token
        # Config field NAMES are public schema vocabulary (same
        if token in _public_config_field_names():
            return token
        if token in _public_ipc_command_names():
            return token
        return replacement

    for pat in _KEY_PATTERNS[:-1]:
        text = pat.sub(_sub, text)
    text = generic_pat.sub(_generic_sub, text)
    stripped = text.strip()
    if len(stripped) >= _MIN_REDACT_LEN and _DASH_JOINED_FULL_RE.fullmatch(stripped):
        text = replacement
    for i, original in enumerate(shields):
        text = text.replace(f"KEPT{i:04d}X", original, 1)
    return text


def redact_url(url: str) -> str:
    """Redact credentials from a URL.

        Strips the userinfo component (``user:pass@``), preserving the
        scheme, host, port, and path so the URL remains useful for
        debugging, and then chains through :func:`redact_secret` so any
        secret-bearing substring *elsewhere* in the URL is also masked.

    pre-fix, only the userinfo component was stripped. A URL
        like ``https://api.example.com/?key=sk-…`` or
        ``https://api.example.com/?access_token=…``: where the credential
        lives in the query string rather than the userinfo, survived
        redaction verbatim. Any caller that logged the URL (e.g.
        :class:`voice_typer.server._http_safety._NoRedirectHandler` puts
        the redirect target into ``HTTPError.url`` and the error message)
        would leak the query-string secret. Chaining through
        :func:`redact_secret` with ``aggressive=True`` masks query-string
        ``key=value`` / ``token=value`` / ``access_token=value`` forms
        (via :data:`_FLAG_KEY_PATTERNS`) AND bare ``sk-…`` / ``Bearer …``
        / 20+ char alphanumeric runs (via :data:`_KEY_PATTERNS`).

        The chained :func:`redact_secret` pass runs with
        ``aggressive=True`` so short bare secrets (e.g. a 12-char
        ``?key=abc`` value, or a 16-char ``?t=shorttoken``) are also
        masked, the short-string guard from :func:`redact_secret` would
        otherwise skip generic-pattern application on URLs whose total
        length happens to be < 20 chars (rare, but possible for
        ``https://a.b/?k=secret``).
    """
    if not url:
        return url
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return url
    if parsed.username or parsed.password:
        # Reconstruct without userinfo
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        url = parsed._replace(netloc=netloc).geturl()
    # chain through redact_secret so query-string / path
    return redact_secret(url, aggressive=True)
