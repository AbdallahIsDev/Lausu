"""Dictation-cycle liveness: is this cycle still the app's live one?

Shared by the pipeline's paste guard and (later) the store guard so a
force-recovered "zombie" worker cannot reach either side effect.
"""

from __future__ import annotations

from typing import Any


def is_cycle_live(app: Any, cycle_id: str | None) -> bool:
    """True iff ``cycle_id`` is the app's current cycle and was not cancelled.

    A stale id (a new dictation already started) or a cancelled id means
    every remaining side effect of that worker must be dropped. Callers
    without cycle bookkeeping (unit stubs, non-string ids) fail open:
    production always assigns ``app._cycle_id`` before dictation starts.
    """
    if not cycle_id:
        return True
    current = getattr(app, "_cycle_id", None)
    if isinstance(current, str) and current and current != cycle_id:
        return False
    recording = getattr(app, "recording", None)
    cancelled = getattr(recording, "_cancelled_cycle_ids", None)
    lock = getattr(recording, "_cancelled_cycle_ids_lock", None)
    if cancelled is None or lock is None:
        return True
    with lock:
        return cycle_id not in cancelled
