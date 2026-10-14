"""Contract pins for the shared condition-wait helpers."""

from __future__ import annotations

import threading
import time

import pytest

from tests.fixtures.wait_helpers import (
    BUSY_CLEAR_TIMEOUT,
    wait_for_busy_clear,
)


class _FakeApp:
    """Minimal stand-in exposing the inverted ``_busy_event`` the waiter polls."""

    def __init__(self) -> None:
        self._busy_event = threading.Event()

    def go_idle_now(self) -> None:
        self._busy_event.set()

    def go_idle_after(self, delay: float) -> None:
        threading.Timer(delay, self._busy_event.set).start()


def test_returns_immediately_when_already_idle() -> None:
    app = _FakeApp()
    app.go_idle_now()

    started = time.monotonic()
    wait_for_busy_clear(app)

    assert time.monotonic() - started < 1.0


def test_waits_out_a_late_pipeline_completion() -> None:
    """The load-starvation case: the flag clears after a scheduling delay."""
    app = _FakeApp()
    app.go_idle_after(0.3)

    wait_for_busy_clear(app, timeout=5.0)

    assert app._busy_event.is_set()


def test_raises_when_the_pipeline_never_reports_idle() -> None:
    app = _FakeApp()

    with pytest.raises(TimeoutError, match=r"still not set after 0\.05s"):
        wait_for_busy_clear(app, timeout=0.05)


def test_default_ceiling_stays_above_the_measured_starvation_delay() -> None:
    """Regression pin: three concurrent ``-n auto`` suites on a 12-core box
    stretched one wait to 3.46 s with no defect, so the shared ceiling must
    stay well clear of the old 2.0 s budget that flaked under that load."""
    assert BUSY_CLEAR_TIMEOUT >= 10.0
