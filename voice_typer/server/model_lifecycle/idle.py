"""Shared idle-unload duration with one independent clock per kind.

The duration is the existing ``model_idle_unload_minutes`` setting (0 = Never
= no unload). Unlike the ASR manager's single deadline, each registered kind
has its own last-use timestamp and deadline; a runtime setting change re-arms
every loaded kind from its own timestamp. Busy kinds are never unloaded: their
deadline is pushed out one minute and retried later.

RACE-013 pattern: ONE persistent daemon thread parked on an Event, no
one-shot Timers, no per-kind threads.
"""

from __future__ import annotations

import logging
import math
import numbers
import threading
import time

from . import registry

log = logging.getLogger(__name__)

_SECONDS_PER_MINUTE = 60.0
_monotonic = time.monotonic

_lock = threading.RLock()
_minutes = 0.0
_last_use: dict[str, float] = {}
_deadlines: dict[str, float] = {}
_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None


def _ensure_thread() -> None:
    global _thread
    if _stop.is_set():
        return
    if _thread is not None and _thread.is_alive():
        return
    # daemon=True: idle cleanup must never delay process exit (RACE-016).
    _thread = threading.Thread(target=_loop, name="model-lifecycle-idle", daemon=True)
    _thread.start()


def touch(kind: str) -> None:
    """Record a use of ``kind`` and push its own deadline out."""
    now = _monotonic()
    with _lock:
        _last_use[kind] = now
        if _minutes > 0:
            _deadlines[kind] = now + _minutes * _SECONDS_PER_MINUTE
            _ensure_thread()
    _wake.set()


def apply_idle_setting(minutes: int) -> None:
    """Apply ``model_idle_unload_minutes`` immediately (0 disables)."""
    global _minutes
    # C-NUM-1: a bare float() on a mock/garbage would fail open as 1.0.
    if not isinstance(minutes, numbers.Real) or not math.isfinite(float(minutes)):
        value = 0.0
    else:
        value = max(0.0, float(minutes))
    with _lock:
        changed = value != _minutes
        _minutes = value
        if value <= 0:
            _deadlines.clear()
            _wake.set()
            return
        if changed:
            for kind, used in _last_use.items():
                _deadlines[kind] = used + value * _SECONDS_PER_MINUTE
            _ensure_thread()
        _wake.set()


def _loop() -> None:
    while not _stop.is_set():
        with _lock:
            minutes = _minutes
            deadlines = dict(_deadlines)
        if minutes <= 0 or not deadlines:
            _wake.wait(timeout=0.5)
            _wake.clear()
            continue
        now = _monotonic()
        delay = max(0.0, min(deadlines.values()) - now)
        if delay > 0:
            _wake.wait(timeout=delay)
            _wake.clear()
            if _stop.is_set():
                break
        now = _monotonic()
        with _lock:
            due = [kind for kind, deadline in _deadlines.items() if deadline <= now and _minutes > 0]
            for kind in due:
                _deadlines.pop(kind, None)
        for kind in due:
            policy = registry.get(kind)
            if policy is None:
                continue
            try:
                if policy.is_busy():
                    with _lock:
                        # Busy kind: never unload mid-use; retry in one minute.
                        if _minutes > 0:
                            _deadlines[kind] = _monotonic() + _SECONDS_PER_MINUTE
                    log.debug("[LIFECYCLE] %s idle unload deferred (busy)", kind)
                    continue
                policy.unload()
                with _lock:
                    _last_use.pop(kind, None)
            except Exception:
                log.debug("[LIFECYCLE] %s idle unload failed", kind, exc_info=True)


def shutdown() -> None:
    """Stop the monitor so no unload fires during app teardown."""
    _stop.set()
    with _lock:
        _deadlines.clear()
    _wake.set()
    thread = _thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=1.0)


def _reset_for_tests() -> None:
    global _minutes, _thread
    shutdown()
    _stop.clear()
    with _lock:
        _minutes = 0.0
        _last_use.clear()
        _deadlines.clear()
    _thread = None
    _wake.clear()


__all__ = ["apply_idle_setting", "shutdown", "touch"]
