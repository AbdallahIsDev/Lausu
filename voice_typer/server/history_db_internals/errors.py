"""Error type raised by the history-DB facade."""


class HistoryDBError(RuntimeError):
    """Raised by HistoryDB methods on unrecoverable failures.

    Each method also returns its documented sentinel (``[]``, ``False``,
    ``-1``, ``{}``); callers that must distinguish "empty result" from
    "operation failed" pass ``raise_on_error=True`` to get this instead.
    """
