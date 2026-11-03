"""Divergence guard for the level-meter / microphone-test chain (A1).

The dictation pipeline fails open when a chain provably deletes voiced speech
(:mod:`voice_typer.server.recording.filter_divergence`). The meter and the mic
test run the same chain but never compared raw against filtered, so a starving
chain showed a dead bar with nothing explaining it — the historic symptom,
merely quieter. This module reuses that guard (same constants, no forked
thresholds) with the monitor's own session latch.

On the trip the chain is bypassed through the existing escape hatch (no
processor ⇒ the worker reads and records the raw device signal), one WARNING
carries both levels, and one toast names what happened.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.recording.filter_divergence import FilterDivergenceGuard, publish_filter_collapse

from ._state import _state

log = logging.getLogger("voice_typer.server.level_monitor")

#: Payload reason so the renderer can word the monitor case on its own.
REASON_MONITOR_COLLAPSE = "monitor_collapse"


def begin_session() -> None:
    """Arm a fresh guard for one monitoring or mic-test session."""
    _state._level_guard = FilterDivergenceGuard()
    _state._level_guard_tripped = False


def _preset_and_method() -> tuple[str, str]:
    config = _state._level_processor_config or {}
    return (
        str(config.get("audio_preset", "unknown")),
        str(config.get("noise_suppression_method", "unknown")),
    )


def observe_level_divergence(raw: Any, filtered_rms: float, sample_rate: int) -> bool:
    """Feed one raw/filtered pair; ``True`` exactly once, on the trip."""
    guard = _state._level_guard
    if guard is None or _state._level_guard_tripped:
        return False
    size = int(getattr(raw, "size", 0) or 0)
    rate = int(sample_rate or 0)
    if size <= 0 or rate <= 0:
        return False
    try:
        tripped = guard.observe(raw, float(filtered_rms), size / float(rate), rate)
    except Exception:
        log.debug("[LEVEL-MON] divergence observe failed", exc_info=True)
        return False
    if not tripped:
        return False
    _state._level_guard_tripped = True
    # Fail open through the existing escape hatch: with no processor the worker
    # reads and records the raw signal for the rest of the session.
    _state._level_processor = None
    preset, method = _preset_and_method()
    fields = {
        "raw_db": round(guard.raw_db, 1),
        "filtered_db": round(guard.filtered_db, 1),
        "delta_db": round(guard.delta_db, 1),
    }
    log.warning(
        "[LEVEL-MON] Filter divergence: chain is removing speech "
        "(raw=%.1f dBFS, filtered=%.1f dBFS, delta=%.1f dB, preset=%s, method=%s); "
        "meter and mic test now read the raw signal",
        guard.raw_db,
        guard.filtered_db,
        guard.delta_db,
        preset,
        method,
    )
    publish_filter_collapse(REASON_MONITOR_COLLAPSE, fields, preset, method)
    return True


__all__ = ["REASON_MONITOR_COLLAPSE", "begin_session", "observe_level_divergence"]
