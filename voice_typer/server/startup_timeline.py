"""Startup timeline markers."""

from __future__ import annotations

import logging
import os
import time

from voice_typer.server.duration import format_duration

BOOT_EPOCH_ENV = "VOICE_TYPER_BOOT_EPOCH_MS"
SPAWN_EPOCH_ENV = "VOICE_TYPER_SPAWN_EPOCH_MS"


def _epoch_delta_s(env_name: str, now_s: float) -> float | None:
    """Return ``now_s - epoch`` in seconds, or ``None`` if unset/garbage."""
    raw = os.environ.get(env_name)
    if not raw:
        return None
    try:
        return max(0.0, now_s - float(raw) / 1000.0)
    except ValueError:
        return None


def log_launch_timeline(logger: logging.Logger) -> None:
    """Emit the merged launch-timeline line (no-op without markers)."""
    now_s = time.time()
    parts: list[str] = []
    boot = _epoch_delta_s(BOOT_EPOCH_ENV, now_s)
    spawn = _epoch_delta_s(SPAWN_EPOCH_ENV, now_s)
    # On a respawn the host is much older than this backend instance;
    # "host boot 78m" would read as restart time. Keep only the backend
    # init segment in that case (cold boot shows both).
    is_respawn = boot is not None and spawn is not None and boot > 60.0 and spawn < boot - 30.0
    if boot is not None and not is_respawn:
        parts.append(f"host boot{format_duration(boot)} (host start to backend first log)")
    if spawn is not None:
        parts.append(f"backend init{format_duration(spawn)} (backend spawn to first log)")
    if parts:
        logger.info("[STARTUP] Launch timeline: %s", ", ".join(parts))


def backend_spawn_monotonic() -> float | None:
    """Monotonic-clock value of the backend-spawn epoch marker."""
    delta = _epoch_delta_s(SPAWN_EPOCH_ENV, time.time())
    if delta is None:
        return None
    return time.monotonic() - delta


__all__ = [
    "BOOT_EPOCH_ENV",
    "SPAWN_EPOCH_ENV",
    "backend_spawn_monotonic",
    "log_launch_timeline",
]
