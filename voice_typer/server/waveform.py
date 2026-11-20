"""Waveform data helpers for the bubble UI."""

import contextlib
import logging
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)

# States that legitimately make the pill visible in ``show_on_record`` mode.
# ``always_visible`` ignores this set entirely.
_ACTIVE_STATES: frozenset[str] = frozenset(
    {
        "recording",
        "transcribing",
        "loading",
        "cancelling",
        "permission_revoked",
        "paste_failed",
        "error",
        "blocked",
        "still_transcribing",
        "cloud_cancel_requested",
    }
)


class WaveformBubble:
    """State + listener registry for the waveform bubble overlay."""

    def __init__(self) -> None:
        self._visible: bool = False
        self._rms_level: float = 0.0
        self._peak_level: float = 0.0
        self._is_speaking: bool = False
        self._state: str = "idle"
        self._lock = threading.Lock()
        # Injected by waveform_bubble_wiring: reads the canonical config.
        self._behavior_provider: Callable[[], str] | None = None

        # Listener slots, set by app.py after IPC server is up.
        self.on_show: Callable[[], None] | None = None
        self.on_hide: Callable[[], None] | None = None
        self.on_level: Callable[[float, float], None] | None = None
        # ``on_set_state`` is called when the
        self.on_set_state: Callable[[str], None] | None = None

        # `on_config` is called with the app Config when the bubble
        self.on_config: Callable[[object], None] | None = None

    @property
    def visible(self) -> bool:
        return self._visible

    def set_behavior_provider(self, provider: Callable[[], str]) -> None:
        self._behavior_provider = provider

    def _behavior(self) -> str:
        if self._behavior_provider is None:
            return "show_on_record"
        try:
            return self._behavior_provider() or "show_on_record"
        except Exception:
            return "show_on_record"

    def apply_visibility(self, state: str, *, reason: str) -> None:
        """The ONE visibility policy. Every caller routes through here.

        ``_visible`` is a desired-state mirror, never proof of on-screen
        visibility. Every decision re-asserts at the host (``force=True``)
        so a host-side hide cannot strand the pill behind a stale mirror.
        """
        behavior = self._behavior()
        if behavior == "always_visible":
            desired = True
        elif behavior == "hidden":
            desired = False
        else:
            desired = state in _ACTIVE_STATES
        # Python owns desired state; only the host can observe the real
        # HWND. Never print a presumed "actual" (C-LOG-6).
        actual = "hidden" if reason.startswith("host-") else "unknown"
        log.info(
            "[BUBBLE] visibility intent=%s behavior=%s state=%s reason=%s actual=%s",
            "visible" if desired else "hidden",
            behavior,
            state,
            reason,
            actual,
        )
        if desired:
            self.show(force=True)
            self.set_state(state)
        else:
            self.hide(force=True)

    def note_host_hidden(self, *, reason: str = "host-hide") -> None:
        """The host hid the real window out of band; reconcile the mirror."""
        with self._lock:
            self._visible = False
            state = self._state
        self.apply_visibility(state, reason=reason)

    def show(self, *, force: bool = False) -> None:
        with self._lock:
            if self._visible and not force:
                return
            was_visible = self._visible
            self._visible = True
            cb = self.on_show
        if force and was_visible:
            log.debug("[WAVEFORM] Bubble shown (reassert)")
        else:
            log.info("[WAVEFORM] Bubble shown")
        if cb is not None:
            try:
                cb()
            except Exception:
                log.debug("[WAVEFORM] on_show callback raised", exc_info=True)

    def hide(self, *, force: bool = False) -> None:
        with self._lock:
            if not self._visible and not force:
                return
            was_hidden = not self._visible
            self._visible = False
            self._rms_level = 0.0
            self._peak_level = 0.0
            self._is_speaking = False
            cb = self.on_hide
        if force and was_hidden:
            log.debug("[WAVEFORM] Bubble hidden (reassert)")
        else:
            log.info("[WAVEFORM] Bubble hidden")
        if cb is not None:
            try:
                cb()
            except Exception:
                log.debug("[WAVEFORM] on_hide callback raised", exc_info=True)

    def set_state(self, state: str) -> None:
        """Change the bubble's visual state."""
        with self._lock:
            self._state = state
            cb = self.on_set_state
        log.info("[WAVEFORM] Bubble state -> %s", state)
        if cb is not None:
            try:
                cb(state)
            except Exception:
                log.debug("[WAVEFORM] on_set_state callback raised", exc_info=True)

    @property
    def state(self) -> str:
        """Last state pushed via :meth:`set_state` (initial ``idle``).

        Lets delayed resets (e.g. the permission_revoked auto-revert)
        check whether the variant is still current before overwriting
        a state that moved on in the meantime.
        """
        with self._lock:
            return self._state

    def reset_level(self) -> None:
        """Reset the level to zero and push a final event to the renderer."""
        with self._lock:
            self._rms_level = 0.0
            self._peak_level = 0.0
            self._is_speaking = False
            cb = self.on_level
        if cb is not None:
            try:
                cb(0.0, 0.0)
            except Exception:
                log.debug("[WAVEFORM] reset_level callback raised", exc_info=True)

    def update_level(self, rms: float, peak: float = 0.0) -> None:
        """Push a new RMS/peak sample to subscribers."""
        with self._lock:
            # Cheap low-pass smoothing so the bubble doesn't jitter
            self._rms_level = (self._rms_level * 0.50) + (rms * 0.50)
            self._peak_level = max(self._peak_level * 0.85, peak)
            self._is_speaking = self._rms_level > 0.005
            cb = self.on_level
            rms_out = self._rms_level
            peak_out = self._peak_level
        if cb is not None:
            with contextlib.suppress(Exception):
                # Drop frame, audio path must not stall
                cb(rms_out, peak_out)

    @property
    def is_speaking(self) -> bool:
        with self._lock:
            return self._is_speaking

    @property
    def rms_level(self) -> float:
        with self._lock:
            return self._rms_level

    @property
    def peak_level(self) -> float:
        with self._lock:
            return self._peak_level
