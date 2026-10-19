"""Thread-local COM apartment management for the Windows native backends.

``comtypes`` initialises COM on the thread that *imports* it and only
balances that at ``atexit``. Every other thread starts with no apartment, so
any ``CoCreateInstance`` / ``Activate`` call there fails with
``CO_E_NOTINITIALIZED`` (``[WinError -2147221008] CoInitialize has not been
called``) -- or, worse, succeeds partially and leaves a wrapper whose object
is torn down under it.

Entering the apartment is therefore a per-thread concern, and it is entered
**once** and never left. ``CoUninitialize()`` is deliberately not called:
it invalidates every proxy in the apartment, and a COM wrapper can outlive
the call that created it (a ``LogRecord``'s ``exc_info``/``args`` traceback
pins the frame that holds it), so the later ``comtypes`` ``__del__`` would
call ``Release()`` through a freed vtable -- the "Windows fatal exception:
access violation" that killed the Windows CI workers.
"""

from __future__ import annotations

import threading

_READY = threading.local()


def ensure_com_initialized() -> None:
    """Enter a COM apartment on this thread, once, and never leave it.

    Raises ``ImportError`` when comtypes is not installed and whatever
    ``CoInitialize`` raises when the apartment cannot be entered (for example
    ``RPC_E_CHANGED_MODE`` on a thread already initialised as MTA), so callers
    keep their existing ``except ImportError`` / ``except Exception`` branches.
    """
    if getattr(_READY, "initialized", False):
        return
    import comtypes

    comtypes.CoInitialize()
    _READY.initialized = True
