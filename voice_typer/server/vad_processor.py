"""VAD state machine, Silero integration, and auto-calibration.

extracted from ``voice_typer/server/recording.py`` (god-class
decomposition). The ``Recorder`` class previously owned device
resolution, VAD state machine, auto-calibration, resampling, buffer
management, xrun/clipping detection, hot-plug handling, and pre-roll
buffer, all in one 3200-line file. This module extracts the VAD-only
concerns into a cohesive unit with a narrow public API.

Scope of extraction (this module):
    * State machine (silence → speech → silence with hysteresis).
    * Silero model availability detection (lazy torch import).
    * Auto-calibration of RMS-dB thresholds from ambient noise floor.
    * Config-driven ``vad_enabled`` cache (5s TTL safety net).

Out of scope (remain in ``recording.py``: see
``docs/history/rw04-recording-decomposition.md``):
    * AudioDeviceManager (device resolution, hot-plug, Bluetooth).
    * AudioBuffer (buffer mgmt, snapshot cache, 3-tier resampling).

Public API:
    VadProcessor(config)
        .update_frame(chunk_rms_db, vad_prob=None) -> VadState
        .auto_calibrate(chunk_rms, elapsed_seconds, chunk_duration=0.0) -> None
        .reset() -> None
        .compute_vad_enabled(config) -> bool
        .on_config_changed() -> None
        .vad_enabled  (cached property with 5s TTL)
        .state, .consecutive_speech_frames, .consecutive_silence_frames,
        .speech_threshold_db, .silence_threshold_db, .speech_frames,
        .silence_frames, .hangover_frames, .use_silero_vad,
        .speech_threshold, .silence_threshold, .silero_available,
        .calibration_duration, .calibration_rms_values, .calibrated,
        .vad_enabled_cached, .vad_enabled_cache_ts

The attribute names match the prior ``Recorder._vad_*`` names with the
``_vad_`` prefix stripped. The ``Recorder`` delegation shims were
removed, ``VadProcessor`` owns the state and tests / consumers access
it via ``recorder._vad.<attr>`` (e.g. ``recorder._vad.state``).
"""

from __future__ import annotations

import enum
import logging
from typing import Any

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.vad_calibration import _VadCalibrationMixin
from voice_typer.server.vad_constants import (  # noqa: F401  # facade re-export (calibration-only names)
    DEFAULT_VAD_CALIBRATION_DURATION,
    DEFAULT_VAD_HANGOVER_FRAMES,
    DEFAULT_VAD_SILENCE_FRAMES,
    DEFAULT_VAD_SILENCE_PROB_THRESHOLD,
    DEFAULT_VAD_SILENCE_THRESHOLD_DB,
    DEFAULT_VAD_SILERO_CALIBRATION_MARGIN,
    DEFAULT_VAD_SILERO_SPEECH_DELTA,
    DEFAULT_VAD_SPEECH_FRAMES,
    DEFAULT_VAD_SPEECH_PROB_THRESHOLD,
    DEFAULT_VAD_SPEECH_THRESHOLD_DB,
    MIN_VAD_SILENCE_THRESHOLD_DB,
    MIN_VAD_SILERO_THRESHOLD_SPREAD,
    MIN_VAD_SPEECH_THRESHOLD_DB,
)
from voice_typer.server.vad_enabled_cache import _VadEnabledCacheMixin

np = lazy_module("numpy")

log = logging.getLogger(__name__)


class VadState(enum.Enum):
    """VAD state-machine states with hysteresis transitions.

    SILENCE → SPEECH requires ``speech_frames`` consecutive loud frames.
    SPEECH → SILENCE requires ``silence_frames`` consecutive quiet frames.
    UNKNOWN is the initial state before enough frames have been observed.
    """

    SILENCE = "silence"
    SPEECH = "speech"
    UNKNOWN = "unknown"


def _make_vad_property(attr: str, doc: str | None = None) -> property:
    """Factory: build a read/write property backed by ``self._<attr>``.

    Reduces boilerplate for the pure pass-through state accessors on
    :class:`VadProcessor` (state, speech/silence frame counters, plain
    thresholds, calibration samples, cache flags). Properties with real
    logic, the clamping floors on ``speech_threshold_db`` /
    ``silence_threshold_db`` (threshold floors), stay hand-written below.

    Mirrors the factory in
    :mod:`voice_typer.server.recording.vad_helpers` but delegates to
    ``self._<attr>`` (the local backing attribute) instead of
    ``self._vad.<attr>`` (the Recorder's delegation target).
    """

    backing = "_" + attr

    def getter(self: Any) -> Any:
        return getattr(self, backing)

    def setter(self: Any, value: Any) -> None:
        setattr(self, backing, value)

    return property(getter, setter, doc=doc)


class VadProcessor(_VadCalibrationMixin, _VadEnabledCacheMixin):
    """Encapsulates the VAD state machine, Silero integration, and
        auto-calibration.

        Stateless w.r.t. the audio buffer: callers pass in per-frame
        RMS (and optional Silero probability) and read back the new state.
        The processor owns its own counters and threshold state, refreshed
        by :meth:`reset` between recording sessions.

    pure extraction from ``Recorder``. Behavior is preserved
        bit-for-bit, the state-machine logic, hysteresis, grey-zone
        pass-through, and auto-calibration math are identical to the
        pre-refactor ``Recorder._vad_update`` /
        ``Recorder._vad_auto_calibrate`` implementations.
    """

    # PERF-02 (c-review): max age in seconds before the cached vad_enabled
    VAD_ENABLED_CACHE_TTL_S: float = 5.0

    def __init__(
        self,
        config: Any,
        vad_check_available_fn: Any | None = None,
    ) -> None:
        """Initialize the VAD processor.

        Args:
            config: the Config object. Read once for ``use_silero_vad``,
                ``vad_speech_threshold``, ``vad_silence_threshold``. The
                ``vad_enabled`` decision is computed lazily from
                ``config`` on first access (and re-cached), so subsequent
                config field changes are reflected after
                :meth:`on_config_changed` or the 5s TTL fallback.
            vad_check_available_fn: optional callable returning bool
                (Silero available?). When None, imports
                ``voice_typer.server.vad.is_available`` lazily
                (preserving the prior deferred-import behavior).
        """
        self._config: Any = config

        # State machine counters
        self._state: VadState = VadState.UNKNOWN
        self._consecutive_speech_frames: int = 0
        self._consecutive_silence_frames: int = 0

        # grey-zone hold bounding. Without this, a long run of
        self._consecutive_grey_frames: int = 0
        # grey-zone hold limit is now configurable so soft-spoken
        _grey_override = getattr(config, "vad_grey_zone_hold_limit", None)
        if isinstance(_grey_override, int):
            self._grey_zone_hold_limit: int = _grey_override
        else:
            self._grey_zone_hold_limit: int = 30  # ~1s at the ~31 Hz chunk cadence

        # RMS-dB thresholds (overridden by auto-calibration)
        self._speech_threshold_db: float = DEFAULT_VAD_SPEECH_THRESHOLD_DB
        self._silence_threshold_db: float = DEFAULT_VAD_SILENCE_THRESHOLD_DB

        # Hysteresis frame counts
        self._speech_frames: int = DEFAULT_VAD_SPEECH_FRAMES
        self._silence_frames: int = DEFAULT_VAD_SILENCE_FRAMES
        self._hangover_frames: int = DEFAULT_VAD_HANGOVER_FRAMES

        # Silero VAD integration: when use_silero_vad is
        self._use_silero_vad: bool = getattr(config, "use_silero_vad", True)
        # getattr fallbacks now reference the canonical Config
        self._speech_threshold: float = getattr(config, "vad_speech_threshold", DEFAULT_VAD_SPEECH_PROB_THRESHOLD)
        self._silence_threshold: float = getattr(config, "vad_silence_threshold", DEFAULT_VAD_SILENCE_PROB_THRESHOLD)
        self._silero_available: bool = False
        if self._use_silero_vad:
            try:
                if vad_check_available_fn is None:
                    from voice_typer.server.vad import (
                        is_available as _vad_check_available,
                    )

                    vad_check_available_fn = _vad_check_available
                self._silero_available = bool(vad_check_available_fn())
                if not self._silero_available:
                    log.warning(
                        "[VAD] use_silero_vad=True but Silero VAD "
                        "unavailable (onnxruntime missing or bundled silero_vad.onnx "
                        "not found), falling back to RMS"
                    )
            except Exception:
                log.debug("[VAD] Silero init failed, falling back to RMS", exc_info=True)
                self._silero_available = False

        # auto-calibration state
        self._calibration_duration: float = DEFAULT_VAD_CALIBRATION_DURATION
        self._calibration_rms_values: list[float] = []
        # Silero-probability samples collected during the
        self._calibration_prob_values: list[float] = []
        self._calibrated: bool = False
        # explicit, inspectable calibration status so a no-op skip
        self._calibration_status: str = "pending"

        # Opt-in flag for Silero-probability auto-calibration.
        _vad_ac_override = getattr(config, "vad_auto_calibrate", False)
        self._vad_auto_calibrate: bool = isinstance(_vad_ac_override, bool) and _vad_ac_override

        # VAD-GATE (Task 4): gate ALL VAD processing on whether any audio
        self._vad_enabled_cached: bool | None = None
        self._vad_enabled_cache_ts: float = 0.0

    def update_frame(
        self,
        chunk_rms_db: float,
        vad_prob: float | None = None,
    ) -> VadState:
        """Update the VAD state machine based on the current frame's signal.

        Uses hysteresis, transitioning from SILENCE to SPEECH
                requires N consecutive loud frames, while SPEECH to SILENCE
                requires M consecutive quiet frames (hangover period). This
                prevents rapid toggling at the boundary.

                When Silero VAD is enabled and a probability is provided, uses
                the VAD probability for speech/silence determination instead of
                RMS dB. Falls back to RMS-based detection if ``vad_prob`` is
                None.

                VAD-GATE (Task 4): returns ``VadState.UNKNOWN`` immediately when
                VAD is disabled (all audio enhancements off). The caller's
                silence-timer logic sees UNKNOWN and treats it as "not silence"
                (no silence warnings, no VAD-based auto-stop).
        """
        # VAD-GATE (Task 4): skip the full state machine when VAD is
        if not self.vad_enabled:
            return VadState.UNKNOWN
        if vad_prob is not None and self._use_silero_vad and self._silero_available:
            # Silero VAD path: use probability thresholds
            is_loud = vad_prob >= self._speech_threshold
            is_quiet = vad_prob < self._silence_threshold
        else:
            # RMS dB path, traditional threshold-based detection
            is_loud = chunk_rms_db >= self._speech_threshold_db
            is_quiet = chunk_rms_db < self._silence_threshold_db

        if is_loud:
            self._consecutive_speech_frames += 1
            self._consecutive_silence_frames = 0
            # a clear loud frame breaks the grey-zone run.
            self._consecutive_grey_frames = 0
        elif is_quiet:
            self._consecutive_silence_frames += 1
            self._consecutive_speech_frames = 0
            # a clear quiet frame breaks the grey-zone run.
            self._consecutive_grey_frames = 0
        else:
            # Grey zone (between speech and silence thresholds).
            self._consecutive_grey_frames += 1
            if self._consecutive_grey_frames >= self._grey_zone_hold_limit:
                if self._state == VadState.SPEECH:
                    # Sustained grey after speech => the soft tail has ended.
                    self._consecutive_speech_frames = 0
                    self._consecutive_silence_frames = self._hangover_frames
                elif self._state == VadState.SILENCE:
                    # SILENCE grey-zone PROMOTE.
                    self._consecutive_silence_frames = 0
                    self._consecutive_speech_frames = self._speech_frames - 1
                else:
                    # UNKNOWN state: decay both counters by 1 so stale
                    if self._consecutive_speech_frames > 0:
                        self._consecutive_speech_frames -= 1
                    if self._consecutive_silence_frames > 0:
                        self._consecutive_silence_frames -= 1
                self._consecutive_grey_frames = 0  # reset so decay is periodic
            elif (
                self._state == VadState.SILENCE
                and self._consecutive_speech_frames > 0
                and self._consecutive_speech_frames < self._speech_frames
            ):
                # Promote mode, the limit-hit branch above
                self._consecutive_speech_frames += 1

        # State transitions with hysteresis
        old_state = self._state
        if self._state == VadState.UNKNOWN:
            if is_loud and self._consecutive_speech_frames >= self._speech_frames:
                self._state = VadState.SPEECH
            elif is_quiet and self._consecutive_silence_frames >= self._silence_frames:
                self._state = VadState.SILENCE
        elif self._state == VadState.SILENCE and self._consecutive_speech_frames >= self._speech_frames:
            self._state = VadState.SPEECH
        elif self._state == VadState.SPEECH and self._consecutive_silence_frames >= self._hangover_frames:
            self._state = VadState.SILENCE

        if self._state != old_state:
            log.debug(
                "[VAD] %s -> %s (rms_db=%.1f, speech_frames=%d, silence_frames=%d)",
                old_state.value,
                self._state.value,
                chunk_rms_db,
                self._consecutive_speech_frames,
                self._consecutive_silence_frames,
            )

        return self._state

    def reset(self) -> None:
        """Reset VAD state machine + auto-calibration to defaults.

                Called by ``Recorder.start()`` at the beginning of each session
                so counters and thresholds from the prior session don't bleed
                into the new one.

        also resets the Silero LSTM hidden state (if the model
                is loaded) so prior-session speech patterns don't bias the
                first probabilities of the new session.
        """
        self._state = VadState.UNKNOWN
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        # reset grey-zone hold counter on session reset.
        self._consecutive_grey_frames = 0
        self._speech_threshold_db = DEFAULT_VAD_SPEECH_THRESHOLD_DB
        self._silence_threshold_db = DEFAULT_VAD_SILENCE_THRESHOLD_DB
        self._calibration_rms_values = []
        # Clear Silero-probability calibration samples too so
        self._calibration_prob_values = []
        self._speech_threshold = float(getattr(self._config, "vad_speech_threshold", DEFAULT_VAD_SPEECH_PROB_THRESHOLD))
        self._silence_threshold = float(
            getattr(self._config, "vad_silence_threshold", DEFAULT_VAD_SILENCE_PROB_THRESHOLD)
        )
        self._calibrated = False
        self._calibration_status = "pending"

        # reset Silero LSTM hidden state at session boundaries.
        try:
            from voice_typer.server.vad import reset_states as _vad_reset_states

            _vad_reset_states()
        except Exception:
            log.debug("[VAD] Silero reset_states unavailable", exc_info=True)

    # The 18 pure pass-through properties below are generated by the

    state = _make_vad_property("state")
    consecutive_speech_frames = _make_vad_property("consecutive_speech_frames")
    consecutive_silence_frames = _make_vad_property("consecutive_silence_frames")
    speech_frames = _make_vad_property("speech_frames")
    silence_frames = _make_vad_property("silence_frames")
    hangover_frames = _make_vad_property("hangover_frames")
    use_silero_vad = _make_vad_property("use_silero_vad")
    speech_threshold = _make_vad_property("speech_threshold")
    silence_threshold = _make_vad_property("silence_threshold")
    silero_available = _make_vad_property("silero_available")
    calibration_duration = _make_vad_property("calibration_duration")
    calibration_rms_values = _make_vad_property("calibration_rms_values")
    calibration_prob_values = _make_vad_property(
        "calibration_prob_values",
        doc=(
            "Silero-probability samples collected during the calibration "
            "window when ``vad_auto_calibrate`` is enabled. Read/write "
            "property for testability + inspection (mirrors "
            "``calibration_rms_values``)."
        ),
    )
    vad_auto_calibrate = _make_vad_property(
        "vad_auto_calibrate",
        doc=("Whether Silero-probability auto-calibration is enabled (``config.vad_auto_calibrate``, default False)."),
    )
    calibrated = _make_vad_property("calibrated")
    calibration_status = _make_vad_property(
        "calibration_status",
        doc=(
            "Explicit, inspectable reason for the current calibration state. "
            "Makes a no-op skip (Silero active / VAD disabled / no samples) "
            "explicit rather than a silent early-return. Values: "
            '"pending" (not yet run), "calibrated" (RMS-dB thresholds '
            'computed), "calibrated_silero" (Silero probability thresholds '
            'computed from observed noise floor), "skipped_silero" (Silero '
            'active, uses probability thresholds), "skipped_disabled" (VAD '
            'off), "skipped_no_samples" (calibration window elapsed with no '
            'RMS samples), "skipped_no_prob" (flag on but the caller did not '
            "pass ``vad_prob``)."
        ),
    )
    vad_enabled_cached = _make_vad_property("vad_enabled_cached")
    vad_enabled_cache_ts = _make_vad_property("vad_enabled_cache_ts")

    @property
    def speech_threshold_db(self) -> float:
        return self._speech_threshold_db

    @speech_threshold_db.setter
    def speech_threshold_db(self, value: float) -> None:
        # Clamp to the speech threshold floor so a noisy
        self._speech_threshold_db = max(float(value), MIN_VAD_SPEECH_THRESHOLD_DB)

    @property
    def silence_threshold_db(self) -> float:
        return self._silence_threshold_db

    @silence_threshold_db.setter
    def silence_threshold_db(self, value: float) -> None:
        # Clamp to the silence threshold floor.
        self._silence_threshold_db = max(float(value), MIN_VAD_SILENCE_THRESHOLD_DB)
