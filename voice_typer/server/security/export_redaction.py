"""Unified PII + secret redaction pipeline for diagnostic exports.

Extracted verbatim from :mod:`voice_typer.server.security.redaction`
(callers import it from that facade / the legacy
``voice_typer.server._secrets`` shim).
"""

from __future__ import annotations

from voice_typer.server.security.secret_redaction import redact_secret


def redact_for_export(text: str) -> str:
    """Unified PII + secret redaction pipeline for diagnostic exports.

    History: the codebase once ran two parallel PII-redaction pipelines
    (one per diagnostic exporter). The second exporter is gone, its
    module was deleted as dead code, so this helper is now the single
    source of truth for "redact this text before it lands in a
    diagnostic bundle / startup-error log". The remaining exporter
    routes through it, so a future redaction improvement (a new
    pattern, a new keyword, a tighter threshold) only has to land in
    one place.

    Pipeline ():
          1. :func:`redact_pii`: applies the PII patterns (email, phone,
             SSN, CC, IBAN) and then runs :func:`redact_secret` (non-
             aggressive) + :func:`redact_url` internally.
          2. :func:`redact_secret(…, aggressive=True)`: a second pass
             with the short-string guard *bypassed* so bare short secrets
             (e.g. a 12-char bare API key with no ``Bearer`` / ``--token=``
             prefix) that survived the non-aggressive pass inside
             ``redact_pii`` are now masked. Idempotent on already-redacted
             text, the ``***`` mask doesn't match the secret patterns.

        Parameters
        ----------
        text : str
            The text to redact. Must already be a string, callers
            converting from ``object`` should call ``str(value)`` first.

        Returns
        -------
        str
            ``text`` with PII patterns replaced by token markers
            (``[EMAIL]``, ``[PHONE]``, …) and secret patterns replaced by
            ``<prefix>***`` / ``***``.

        Notes
        -----
        :func:`redact_pii` is defined in this same module (the merged
        redaction module). The lazy import through the package namespace
        is retained so the call-time patchability the tests rely on keeps
        working: they monkeypatch ``voice_typer.server.security.redact_pii``
        (the package re-export) and expect the patch to take effect on the
        next call, resolving the name through the package at call time
        guarantees exactly that.
    """
    # Lazy import through the package namespace keeps test monkeypatches
    from voice_typer.server.security import redact_pii

    return redact_secret(redact_pii(text), aggressive=True)
