"""Shared condition-wait helpers for tests, replacing fixed ``time.sleep`` calls."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Protocol

from tests.fixtures.wait_for import wait_for


class _BusyEventApp(Protocol):
    """The slice of the app the busy-wait needs (``_busy_event`` is inverted:
    ``is_set()`` means NOT busy)."""

    _busy_event: threading.Event


# Ceiling for the off-thread dictation pipeline to report idle. A scheduling
# bound, not a product deadline: with three concurrent ``-n auto`` suites (24
# xdist workers on a 12-core box) single waits measured 2.26 s and 3.46 s and
# the flag always cleared -- no defect, just contention. A genuine hang still
# fails here, and the outer pytest timeout (60 s local / 120 s CI) stays the
# last line of defence.
BUSY_CLEAR_TIMEOUT = 30.0


def wait_for_busy_clear(app: _BusyEventApp, timeout: float = BUSY_CLEAR_TIMEOUT) -> None:
    """Wait until the app's dictation pipeline reports idle (see the ceiling note)."""
    if not wait_until(app._busy_event.is_set, timeout=timeout):
        raise TimeoutError(f"_busy_event still not set after {timeout}s")


def wait_until(
    predicate: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.005,
) -> bool:
    """Poll ``predicate`` until truthy or ``timeout`` elapses."""
    return wait_for(predicate, timeout=timeout, interval=interval)


def wait_for_event(event: threading.Event, timeout: float = 5.0) -> bool:
    """Wait for a ``threading.Event`` to be set."""
    return event.wait(timeout)


__all__ = [
    "BUSY_CLEAR_TIMEOUT",
    "wait_for",
    "wait_for_busy_clear",
    "wait_for_event",
    "wait_until",
]
