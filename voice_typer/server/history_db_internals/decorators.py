"""The ``raise_on_error`` failure contract for history-DB public methods.

``HistoryDBError`` is the exception those methods raise; the ``_wrap_*``
decorators below are what decide between raising it and returning the
method's documented sentinel.
"""

from __future__ import annotations

import functools
import logging


class HistoryDBError(RuntimeError):
    """Raised by HistoryDB methods on unrecoverable failures.

    Each method also returns its documented sentinel (``[]``, ``False``,
    ``-1``, ``{}``); callers that must distinguish "empty result" from
    "operation failed" pass ``raise_on_error=True`` to get this instead.
    """


# Same logger as the facade: these wrappers report failures of HistoryDB
# methods, and users grep lausu.log for the ``voice_typer.server.history_db``
# provenance.
log = logging.getLogger("voice_typer.server.history_db")


def _wrap_write(failure_value, fail_verb, writer_label):
    """Map write-method failures to either ``HistoryDBError`` or a sentinel.

    ``failure_value`` may be a callable factory so mutable sentinels
    (``[]`` / ``{}``) are freshly built per failure return, matching the
    per-call literal the inline code used.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            raise_on_error = kwargs.pop("raise_on_error", False)
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                if isinstance(e, HistoryDBError):
                    if raise_on_error:
                        raise
                    log.exception("[HISTORY] Writer unavailable for %s", writer_label)
                    return failure_value() if callable(failure_value) else failure_value
                log.exception("[HISTORY] Failed to %s: %s", fail_verb, e)
                if raise_on_error:
                    raise HistoryDBError(str(e)) from e
                return failure_value() if callable(failure_value) else failure_value

        return wrapper

    return decorator


def _wrap_read(failure_value, fail_verb):
    """Map read-method failures to either ``HistoryDBError`` or a sentinel."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            raise_on_error = kwargs.pop("raise_on_error", False)
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                log.exception("[HISTORY] Failed to %s: %s", fail_verb, e)
                if raise_on_error:
                    raise HistoryDBError(str(e)) from e
                return failure_value() if callable(failure_value) else failure_value

        return wrapper

    return decorator
