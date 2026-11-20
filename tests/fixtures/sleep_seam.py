"""Record a module's sleeps without patching the process-global ``time`` module.

``monkeypatch.setattr(offline_pack.time, "sleep", recorder)`` mutates the shared
stdlib module, so EVERY thread in the worker is redirected — including a thread
an earlier test left running. Those foreign sleeps get appended to the recorder
(the recorder does not sleep, so such a loop spins), and a test asserting
``sleeps == []`` or ``sleeps == [1.0]`` then fails on values its code never
produced.

Patching the MODULE's own ``time`` reference keeps the mutation local to the
code under test: ``monkeypatch.setattr(module, "time", proxy)`` rebinds that
module's global only, and every other reader of ``time`` is untouched.
"""

from __future__ import annotations

import time


class _RecordingTime:
    """Stands in for a module's ``time`` reference; records ``sleep`` only."""

    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)

    def __getattr__(self, name: str):
        # monotonic / perf_counter / time / strftime … keep real behaviour.
        return getattr(time, name)


def patch_module_time(monkeypatch, module, sleep=None):
    """Rebind ``module.time`` to the proxy itself, for tests that also fake the clock.

    ``sleep`` replaces the recorder when the test needs its own sleep side
    effects; set further attributes (``counter.perf_counter = ...``) on the
    returned proxy.
    """
    proxy = _RecordingTime()
    if sleep is not None:
        proxy.sleep = sleep  # instance attribute shadows the recording method
    monkeypatch.setattr(module, "time", proxy)
    return proxy


def patch_module_sleep(monkeypatch, module) -> list[float]:
    """Rebind ``module.time`` to a recorder; return the recorded delays.

    ``module`` is the module the code under test reads ``time`` from — e.g.
    ``voice_typer.server.retry`` (covers ``run_with_retry`` and
    ``sleep_interruptible`` for every caller) or
    ``voice_typer.server.recording.stream_lifecycle``.
    """
    proxy = _RecordingTime()
    monkeypatch.setattr(module, "time", proxy)
    return proxy.sleeps
