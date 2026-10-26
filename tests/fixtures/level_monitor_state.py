"""One canonical level-monitor reset for the suites that need a clean slate.

Ten test files grew their own copy of this, and the copies drifted: the ones
written before the stream-recovery work never cleared
``_stream_recovery_token`` / ``_stream_recovery_episodes``, so a recovery
thread left alive by an earlier file in the same xdist worker could reopen a
monitor mid-test. On CI that surfaced as a phantom ``mic_level`` push stealing
a ``_monitor_level`` assertion and as a finished-callback retry that returned
early instead of emitting ``device_lost``.

``_reset_state_for_tests()`` already swaps every state field back to its
post-init default, so the reset below only has to stop the threads/timers that
outlive a state swap, then delegate.
"""

from __future__ import annotations

import contextlib


def reset_level_monitor_state() -> None:
    """Stop level-monitor threads/timers and reset all module state."""
    import voice_typer.server.level_monitor as lm
    from voice_typer.server.level_monitor import worker as _worker

    # A state swap only drops the reference; a live Timer keeps ticking.
    leaked_timer = lm._test_auto_stop_timer
    if leaked_timer is not None:
        with contextlib.suppress(Exception):
            leaked_timer.cancel()
    for expiry_timer in list(getattr(lm, "_test_recording_expiry_timers", ())):
        with contextlib.suppress(Exception):
            expiry_timer.cancel()

    # Threads write through the singleton, so they stop before the swap.
    lm._stop_level_worker()
    lm._stop_mic_level_worker()
    lm._reset_state_for_tests()
    _worker._reset_worker_error_state_for_tests()
