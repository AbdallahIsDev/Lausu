"""Mic-test recording lifecycle: arm, start, cancel, auto-stop.

Split from ``voice_typer/server/level_monitor/test_recording.py``
(create-first); the facade re-exports every name so the historical import
path keeps resolving.
"""

from __future__ import annotations

import collections
import logging
import threading
import time

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.duration import format_duration

from ._state import _state
from .test_recording_files import _purge_test_recordings

# Call-time facade access: tests patch ``_secure_clear_test_chunks`` on
# the facade, so the cancel path must re-resolve it there (never by value).
_facade = lazy_module("voice_typer.server.level_monitor.test_recording")

log = logging.getLogger("voice_typer.server.level_monitor")

def _secure_clear_test_chunks(*deques: collections.deque) -> None:
    """securely zero the np.ndarray chunks in the test"""
    try:
        from voice_typer.server.recording import _secure_clear_array_background
    except Exception:
        log.debug(
            "[LEVEL-MON] _secure_clear_array_background unavailable; "
            "skipping secure clear of test chunks (GC will reclaim)",
            exc_info=True,
        )
        return
    for d in deques:
        if not d:
            continue
        try:
            # Wrap a SNAPSHOT of the deque's current contents in a
            snapshot = collections.deque(list(d))
            _secure_clear_array_background(snapshot)
        except Exception:
            log.debug(
                "[LEVEL-MON] secure clear of test chunks failed for one deque (best-effort; GC will reclaim)",
                exc_info=True,
            )


def _reset_test_chunks(locked: bool) -> None:
    """(Re) create the bounded test-chunk deques under the right capacity."""
    sr = _state._monitor_sample_rate
    # Capacity bound: chunks arrive at ``sr / blocksize`` per second where
    cap = int(_state._test_duration * sr / 512) + 1
    if cap < 1:
        cap = 1
    new_chunks = collections.deque(maxlen=cap)
    new_raw = collections.deque(maxlen=cap)
    new_filtered = collections.deque(maxlen=cap)

    if locked:
        _state._test_chunks = new_chunks
        _state._test_raw_chunks = new_raw
        _state._test_filtered_chunks = new_filtered
    else:
        with _state._monitor_lock:
            _state._test_chunks = new_chunks
            _state._test_raw_chunks = new_raw
            _state._test_filtered_chunks = new_filtered


def is_test_active() -> bool:
    """Return True if a microphone test is currently recording.

    Returns:
    """
    with _state._monitor_lock:
        return _state._test_mode


def _begin_test_locked(duration: float, filters: dict | None) -> dict:
    """Arm test mode under ``_monitor_lock`` (caller holds the lock).

    Shared by both ``start_test_recording`` paths: the monitor already on
    the right device, and the restart path after ``start_monitoring``.
    """
    _state._test_mode = True
    _state._test_start_time = time.perf_counter()
    _state._test_duration = max(1.0, min(30.0, duration))
    # (re)create bounded deques sized to this start's duration
    _reset_test_chunks(locked=True)
    _state._test_filters = dict(filters) if filters else {}
    _state._test_peak_history.clear()
    _state._test_rms_history.clear()
    _state._test_clip_count = 0
    _state._test_silence_blocks = 0
    sr = _state._monitor_sample_rate

    _state._test_auto_stop_timer = threading.Timer(
        _state._test_duration,
        _do_auto_stop_test,
    )
    _state._test_auto_stop_timer.daemon = True
    _state._test_auto_stop_timer.start()

    log.info(
        "[LEVEL-MON] Test recording started: mic=%s | duration%s",
        _state._monitor_mic_id or "default",
        format_duration(_state._test_duration),
    )
    return {
        "success": True,
        "message": "Recording test...",
        "duration": _state._test_duration,
        "sample_rate": sr,
    }


def start_test_recording(
    mic_id: str | None = None,
    duration: float = 10.0,
    filters: dict | None = None,
) -> dict:
    """Start a microphone test recording using the existing monitor stream."""
    with _state._monitor_lock:
        if _state._test_mode:
            return {
                "success": False,
                "message": "Test already running",
                "duration": duration,
            }

        # Keep-only-latest disk transport: a new test invalidates any
        _purge_test_recordings()

        # Ensure the monitor is running on the correct device
        if not _state._monitor_active or _state._monitor_mic_id != mic_id:
            # We must release the lock before calling start_monitoring
            pass  # handled below the lock
        else:
            # Monitor is already active on the right device.
            return _begin_test_locked(duration, filters)

    # Monitor not running or on wrong device, start/restart it
    from .monitoring import start_monitoring

    mon_result = start_monitoring(mic_id=mic_id)
    if not mon_result.get("success"):
        return {
            "success": False,
            "message": mon_result.get("message", "Failed to start monitor"),
            "duration": duration,
        }

    # Monitor is now running on the correct device.
    with _state._monitor_lock:
        if _state._test_mode:
            return {
                "success": False,
                "message": "Test already running",
                "duration": duration,
            }
        return _begin_test_locked(duration, filters)


def update_test_filters(filters_dict: dict) -> None:
    """Update the active test recording's filter settings in real-time."""
    with _state._monitor_lock:
        if not _state._test_mode:
            return
        # Merge new settings into existing test filters so individual
        _state._test_filters.update(filters_dict)
        log.debug(
            "[LEVEL-MON] Test filters updated in-flight: %s",
            {k: v for k, v in _state._test_filters.items() if k.startswith("noise_filter_")},
        )


def cancel_test_recording() -> dict:
    """Cancel an in-progress test recording without returning audio."""
    # Cancel the auto-stop timer under ``_monitor_lock`` (mirrors
    with _state._monitor_lock:
        timer = _state._test_auto_stop_timer
        if timer is not None:
            timer.cancel()
            _state._test_auto_stop_timer = None

    was_active = _cancel_test_locked()

    log.info("[LEVEL-MON] Test cancelled")
    if not was_active:
        return {"success": True, "message": "No test running"}
    return {"success": True, "message": "Test cancelled"}


def _do_auto_stop_test() -> None:
    """Auto-stop callback fired by the threading.Timer."""
    with _state._monitor_lock:
        if not _state._test_mode:
            return
        _state._test_mode = False
        _state._test_auto_stop_timer = None

    log.info("[LEVEL-MON] Auto-stop: test ended")

    # Notify the frontend
    try:
        from voice_typer.server import event_bus

        event_bus.publish(
            {
                "type": "microphone_test_complete",
                "data": {"duration": _state._test_duration},
            },
        )
    except Exception:
        # this is load-bearing, if the publish fails, the
        log.warning(
            "[LEVEL-MON] failed to publish microphone_test_complete event",
            exc_info=True,
        )

    # G-PERF-RELIABILITY: do NOT clear chunks on auto-stop.


def _cancel_test_locked() -> bool:
    """Cancel test state under the lock.

    Returns True if a test was actually active, False otherwise.
    """
    with _state._monitor_lock:
        # Stop auto-stop timer if running (under the lock to close
        timer = _state._test_auto_stop_timer
        if timer is not None:
            timer.cancel()
            _state._test_auto_stop_timer = None

        if (
            not _state._test_mode
            and not _state._test_chunks
            and not _state._test_raw_chunks
            and not _state._test_filtered_chunks
        ):
            return False
        was_active = _state._test_mode
        _state._test_mode = False
        # .clear() preserves the bounded deque (and its maxlen).
        _facade._secure_clear_test_chunks(_state._test_raw_chunks, _state._test_filtered_chunks, _state._test_chunks)
        _state._test_chunks.clear()
        _state._test_raw_chunks.clear()
        _state._test_filtered_chunks.clear()
        _state._test_start_time = 0.0
        _state._test_filters.clear()
        _state._test_peak_history.clear()
        _state._test_rms_history.clear()
        _state._test_clip_count = 0
        _state._test_silence_blocks = 0
        return was_active
