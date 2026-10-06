"""Mic-level push-event coalescing + the push worker thread.

``_push_mic_level`` coalesces RMS/peak payloads into a queue and the dedicated
worker thread drains it (latest-only) into ``mic_level`` push events. State
lives in :mod:`._state`.

Extracted from ``monitoring.py``.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time

from ._state import _state

log = logging.getLogger("voice_typer.server.level_monitor")


def _push_mic_level(rms: float, peak: float, active: bool) -> None:
    """Coalesce + enqueue a mic_level push-event payload."""
    now = time.monotonic()
    if now - _state._mic_level_last_push_ts < _state._MIC_LEVEL_COALESCE_SEC:
        return
    _state._mic_level_last_push_ts = now
    payload = {"level": float(rms), "peak": float(peak), "active": bool(active)}
    with _state._mic_level_queue_lock:
        # deque(maxlen=16) auto-evicts oldest on overflow, so we don't
        _state._mic_level_queue.append(payload)
    _state._mic_level_worker_wake_event.set()


def _mic_level_worker_loop() -> None:
    """Drains the coalesce queue (keeping the latest payload only, PERF-3"""
    from .worker import (
        MIC_LEVEL_WORKER_NAME,
        _unregister_from_thread_registry,
    )

    _consecutive_idle_ticks = 0
    while True:
        _state._mic_level_worker_wake_event.wait(
            timeout=_state._LEVEL_WORKER_BACKSTOP_TIMEOUT_SEC,
        )
        _state._mic_level_worker_wake_event.clear()
        if _state._mic_level_worker_stop:
            return
        # PERF-3 latest-only: drain all pending payloads, keep the last.
        latest = None
        with _state._mic_level_queue_lock:
            while _state._mic_level_queue:
                latest = _state._mic_level_queue.popleft()
        if latest is not None:
            _consecutive_idle_ticks = 0
            try:
                from voice_typer.server import event_bus

                event_bus.publish(
                    {
                        "type": "mic_level",
                        "data": {
                            "level": latest["level"],
                            "peak": latest["peak"],
                            "active": latest["active"],
                        },
                    },
                )
            except Exception:
                log.debug("[LEVEL-MON] Failed to publish mic_level event", exc_info=True)
            continue
        # Queue was empty. If the monitor stream is no longer active
        if not _state._monitor_active:
            _consecutive_idle_ticks += 1
            if _consecutive_idle_ticks >= 2:
                # Clear the slot BEFORE returning (race-safe restart).
                _state._mic_level_worker_thread = None
                _unregister_from_thread_registry(MIC_LEVEL_WORKER_NAME)
                return
        else:
            _consecutive_idle_ticks = 0


def _ensure_mic_level_worker_running() -> None:
    """Start the mic_level push-event worker thread if not already running."""
    from .worker import (
        MIC_LEVEL_WORKER_NAME,
        _register_with_thread_registry,
    )

    if _state._mic_level_worker_thread is not None and _state._mic_level_worker_thread.is_alive():
        return
    _state._mic_level_worker_stop = False
    _state._mic_level_worker_thread = threading.Thread(
        target=_mic_level_worker_loop,
        name=MIC_LEVEL_WORKER_NAME,
        daemon=True,
    )
    _state._mic_level_worker_thread.start()
    # Best-effort registration with the central ThreadRegistry so
    _register_with_thread_registry(
        MIC_LEVEL_WORKER_NAME,
        _state._mic_level_worker_thread,
        # The mic_level worker has no dedicated Event stop flag; the
        _state._mic_level_worker_wake_event,
    )


def _stop_mic_level_worker() -> None:
    """Signal the mic_level worker thread to stop and join it (best-effort)."""
    _state._mic_level_worker_stop = True
    _state._mic_level_worker_wake_event.set()
    t = _state._mic_level_worker_thread
    if t is not None and t is not threading.current_thread():
        with contextlib.suppress(Exception):
            t.join(timeout=1.0)
    _state._mic_level_worker_thread = None
    from .worker import (
        MIC_LEVEL_WORKER_NAME,
        _unregister_from_thread_registry,
    )

    _unregister_from_thread_registry(MIC_LEVEL_WORKER_NAME)
