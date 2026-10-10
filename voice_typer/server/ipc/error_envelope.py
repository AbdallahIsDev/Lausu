"""Typed IPC error-envelope contract and its builder.

One concern only: describe the shape of an error response (``type`` +
``data`` with a namespaced ``code``) and stamp it onto a handler's response
dict. The validators that produce most of these envelopes live in
:mod:`voice_typer.server.ipc.validation`, which re-exports both names.
"""

from __future__ import annotations

from typing import TypedDict

from voice_typer.server.ipc.error_codes import ErrorCodes


# Typed contract for the IPC error envelope. The TS side has a
class ErrorData(TypedDict, total=False):
    code: str
    message: str
    field: str
    command: str
    id: str | int


class _ErrorEnvelopeRequired(TypedDict):
    """Required keys on every error envelope.

    Split out so :class:`ErrorEnvelope` can extend it with ``id`` as
    an optional key (ad-hoc emitters only set ``id`` when a request id
    is available to echo back).
    """

    type: str  # always ``"error"`` for an error envelope
    data: ErrorData



class ErrorEnvelope(_ErrorEnvelopeRequired, total=False):
    """Canonical IPC error envelope.

    Required keys: ``type`` (``"error"``), ``data`` (an
    :class:`ErrorData` mapping). Optional key: ``id`` (echoed request
    id when available). This is the documented *contract* for every
    error envelope constructed in the IPC layer; ad-hoc dict literals
    at the construction sites are not type-checked against this
    TypedDict (the contract is documentation, not runtime
    enforcement, the return-type annotation on
    :func:`_validate_dict_payload` is plain ``dict[str, object]`` rather
    than :class:`ErrorEnvelope` because TypedDicts are invariant and
    not subtypes of ``dict``, so annotating the return as
    :class:`ErrorEnvelope` would flag every caller that returns the
    error directly from a ``-> dict | None`` handler. The contract is
    documented at construction sites via the
    ``# ErrorEnvelope contract: see validation.py`` comments and
    verified by ``tests/test_error_codes_registry.py``).
    """

    id: object | None


def _error_response(resp: dict, message: str, *, code: str = ErrorCodes.HANDLER_ERROR) -> dict:
    """Stamp an error envelope on ``resp`` and return it.

        The helper standardizes the catch-all ``except Exception`` envelope
        produced by handler mixins. Previously each handler did::

            except Exception as e:
                log.error("[IPC] <cmd> failed: %s", e, exc_info=True)
                resp["type"] = "error"
                resp["data"] = {"message": str(e)}
            return resp

        The ad-hoc envelope omitted the ``code`` field that every other
        error path (validation, dispatch safety net, rate limiter) sets.
        Clients branching on ``code`` silently fell through to a generic
        "unknown error" path for handler exceptions. The helper stamps
    ``code: "server.handler_error"`` ( namespaced form; was
    ``"handler_error"`` pre-) and a sanitized message (the caller is
        responsible for logging the full exception server-side at ERROR
        with ``exc_info=True``).

        Parameters
        ----------
        resp : dict
            The response dict pre-populated by ``_dispatch`` (carries the
            request ``id``). Mutated in place.
        message : str
            The client-facing message. Should be sanitized (no Python
            internals, no PII). The caller decides what's safe to expose.
        code : str, optional
    The error code. Defaults to ``"server.handler_error"`` ( namespaced form; was
    ``"handler_error"`` pre-), the standard
            for an unexpected exception caught by a handler's catch-all.
            Override for known-error paths that still want the helper's
            envelope shape (e.g. ``"not_initialized"``).

        Returns
        -------
        dict
            The same ``resp`` dict, mutated to be an error envelope.
    """
    resp["type"] = "error"
    resp["data"] = {"code": code, "message": message}
    return resp
