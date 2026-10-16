"""MicVolumeGuard — keeps the OS capture gain pinned at 100%.

Windows/driver auto-gain follows a loud close-range event and slides the
capture knob down (100 → 92 → 88 …); the user requires it at 100%. The
guard polls the capture endpoint and writes 100% back.

Two deliberate bounds:

* **Anti-flap.** At most ``ANTIFLAP_MAX_RESTORES`` writes per
  ``ANTIFLAP_WINDOW_S``. Past the budget it keeps observing and keeps
  reporting, but stops writing — a driver that re-clamps continuously
  must never become a tug-of-war.
* **The user's own write is never budgeted.** Only the automatic
  restore consumes the budget; ``set_level`` (the renderer's
  ``[Back to 100%]`` button) always writes.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable

from voice_typer.server.volume_backend_base import MicVolumeBackend

log = logging.getLogger(__name__)

# The knob the user requires: full scale.
MIC_GUARD_TARGET_LEVEL: float = 1.0

# One poll per 2s. Windows is an in-process COM read (~µs); Linux spawns
# a subprocess, so its backend raises ``min_poll_interval_ms`` to 2s.
DEFAULT_MIC_GUARD_POLL_MS: int = 2000

# A 1% device step (the Windows knob moves 100 → 99) is a real move.
_MIC_GUARD_TOLERANCE: float = 0.005

MIC_GUARD_ANTIFLAP_MAX_RESTORES: int = 3
MIC_GUARD_ANTIFLAP_WINDOW_S: float = 180.0

# consecutive read failures before a WARNING (the guard owns this policy
# so the three platform backends stay DEBUG-only and identical).
_MIC_GUARD_WARN_THRESHOLD: int = 3


class MicVolumeGuard:
    """Polls the capture gain and restores 100%, with an anti-flap budget."""

    def __init__(
        self,
        backend: MicVolumeBackend | None = None,
        on_lowered: Callable[[float, bool], None] | None = None,
        enabled: Callable[[], bool] | None = None,
    ) -> None:
        self._backend = backend
        self._on_lowered = on_lowered
        self._enabled = enabled
        self._poll_ms = DEFAULT_MIC_GUARD_POLL_MS
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._initialized = False
        self._ready = False
        # Serializes backend access: the watcher thread and the IPC
        # dispatch thread share ONE COM pointer / subprocess handle.
        self._lock = threading.RLock()
        self._restores: deque[float] = deque()
        self._last_reported: tuple[float, bool] | None = None
        self._consecutive_errors = 0

    # ── lifecycle ────────────────────────────────────────────────────

    def initialize(self) -> bool:
        """Resolve + initialize the backend. Idempotent."""
        if self._initialized:
            return self._ready
        self._initialized = True
        if self._backend is None:
            from voice_typer.server.server_platform.volume_factory import (
                get_mic_volume_backend,
            )

            self._backend = get_mic_volume_backend()
        if self._backend is None:
            log.info("[MIC-GUARD] No capture-volume backend available, guard disabled")
            return False
        try:
            self._ready = bool(self._backend.initialize())
        except Exception:
            log.warning("[MIC-GUARD] backend initialize failed", exc_info=True)
            self._ready = False
            return False
        if not self._ready:
            log.info("[MIC-GUARD] Capture endpoint unavailable, guard disabled")
            return False
        floor = int(getattr(self._backend, "min_poll_interval_ms", 0) or 0)
        self._poll_ms = max(DEFAULT_MIC_GUARD_POLL_MS, floor)
        log.info(
            "[MIC-GUARD] Backend ready: %s (settable=%s, poll=%dms)",
            self._backend.name,
            self._backend.supports_set,
            self._poll_ms,
        )
        return True

    def start(self) -> None:
        """Start the watcher thread. No-op when already running/disabled."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        # RACE-008: daemon so a wedged capture-API call can never hold
        # process exit hostage; the loop polls a stop Event (RACE-013).
        self._thread = threading.Thread(
            target=self._watch_loop,
            name="mic-volume-guard",
            daemon=True,
        )
        self._thread.start()
        log.debug("[MIC-GUARD] Watcher thread started")

    def stop(self, timeout: float = 2.0) -> None:
        """Signal the watcher and join it (best-effort)."""
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    # ── level surface ────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return self._ready

    @property
    def supports_set(self) -> bool:
        """``False`` on devices with no settable input gain (macOS)."""
        if self._backend is None:
            return False
        return bool(self._backend.supports_set)

    @property
    def backend_name(self) -> str:
        if self._backend is None:
            return "disabled"
        return self._backend.name

    def get_level(self) -> float | None:
        if not self._ready or self._backend is None:
            return None
        with self._lock:
            try:
                return self._backend.get_level()
            except Exception as exc:
                log.debug("[MIC-GUARD] get_level failed: %s", exc)
                return None

    def set_level(self, level: float) -> bool:
        """Write the device knob. Never consumes the anti-flap budget."""
        if not self._ready or self._backend is None:
            return False
        with self._lock:
            try:
                return bool(self._backend.set_level(max(0.0, min(1.0, level))))
            except Exception as exc:
                log.debug("[MIC-GUARD] set_level failed: %s", exc)
                return False

    def restore_to_full(self) -> bool:
        """Write the target level (the explicit user-pressed restore)."""
        return self.set_level(MIC_GUARD_TARGET_LEVEL)

    # ── watcher ──────────────────────────────────────────────────────

    def _watch_loop(self) -> None:
        # Event.wait as the sleep: shutdown interrupts a 2s poll at once
        # instead of after the full interval (RACE-013, no one-shot Timer).
        while not self._stop.wait(self._poll_ms / 1000.0):
            try:
                self.poll_once()
            except Exception:
                log.debug("[MIC-GUARD] poll failed", exc_info=True)

    def poll_once(self) -> None:
        """One observation cycle. Public so tests drive it directly."""
        if self._enabled is not None and not self._enabled():
            return
        if not self._ready:
            return
        level = self.get_level()
        if level is None:
            self._consecutive_errors += 1
            if self._consecutive_errors % _MIC_GUARD_WARN_THRESHOLD == 0:
                log.warning(
                    "[MIC-GUARD] capture level read failed %d times in a row",
                    self._consecutive_errors,
                )
            return
        if self._consecutive_errors:
            self._consecutive_errors = 0
        if level >= MIC_GUARD_TARGET_LEVEL - _MIC_GUARD_TOLERANCE:
            # Settled knob = new episode: forget a NOTIFY-ONLY report the user
            # may have cleared so a later clamp tells them again; restored
            # reports stay deduped so a clamping driver cannot spam.
            if self._last_reported is not None and not self._last_reported[1]:
                self._last_reported = None
            return

        restored = False
        if self._budget_available():
            restored = self.set_level(MIC_GUARD_TARGET_LEVEL)
            if restored:
                self._restores.append(time.monotonic())

        # Dedupe first: a knob parked at 92% would otherwise log and
        # re-report on every 2s poll.
        report = (round(level, 3), restored)
        if report == self._last_reported:
            return
        self._last_reported = report

        if restored:
            log.info("[MIC-GUARD] Microphone was at %.0f%%, restored to 100%%", level * 100)
        elif not self.supports_set:
            log.info("[MIC-GUARD] Microphone at %.0f%% — device has no settable gain", level * 100)
        else:
            log.warning(
                "[MIC-GUARD] Microphone at %.0f%% — anti-flap budget exhausted, notify-only",
                level * 100,
            )

        if self._on_lowered is not None:
            try:
                self._on_lowered(level, restored)
            except Exception:
                log.debug("[MIC-GUARD] on_lowered callback failed", exc_info=True)

    def _budget_available(self) -> bool:
        """``True`` while fewer than N automatic restores happened in the window."""
        if not self.supports_set:
            return False
        now = time.monotonic()
        cutoff = now - MIC_GUARD_ANTIFLAP_WINDOW_S
        while self._restores and self._restores[0] < cutoff:
            self._restores.popleft()
        return len(self._restores) < MIC_GUARD_ANTIFLAP_MAX_RESTORES


__all__ = [
    "DEFAULT_MIC_GUARD_POLL_MS",
    "MIC_GUARD_ANTIFLAP_MAX_RESTORES",
    "MIC_GUARD_ANTIFLAP_WINDOW_S",
    "MIC_GUARD_TARGET_LEVEL",
    "MicVolumeGuard",
]
