"""Origin guard for dictation starts (C-START-USER-1).

Every start carries the user action that requested it. Background work (app
start, activation, recovery, reconnect, page-ready) has no origin and is
refused at the application entry, before any engine sees a toggle.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
from collections.abc import Iterator

log = logging.getLogger(__name__)

USER_ORIGINS = frozenset({"hotkey", "button", "tray", "dev-driver"})
_origin: contextvars.ContextVar[str] = contextvars.ContextVar("dictation_origin", default="")


@contextlib.contextmanager
def user_action(origin: str) -> Iterator[None]:
    if origin not in USER_ORIGINS:
        raise ValueError(f"unknown dictation origin: {origin}")
    token = _origin.set(origin)
    try:
        yield
    finally:
        _origin.reset(token)


def current() -> str:
    return _origin.get()


def authorize(caller: str) -> str:
    """Return the origin, or refuse the call with one WARN naming the caller."""
    origin = current()
    if origin not in USER_ORIGINS:
        log.warning("[DICTATION] start refused: no user-initiated origin (caller=%s)", caller)
        return ""
    return origin
