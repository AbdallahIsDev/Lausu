"""VAD auto-calibration mixin: RMS-dB threshold calibration from the
ambient noise floor + Silero probability-threshold derivation.

Split from ``voice_typer/server/vad_processor.py`` (create-first);
:class:`voice_typer.server.vad_processor.VadProcessor` composes it so
the historical import path keeps resolving.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.vad_constants import (
    DEFAULT_VAD_SILERO_CALIBRATION_MARGIN,
    DEFAULT_VAD_SILERO_SPEECH_DELTA,
    MIN_VAD_SILERO_THRESHOLD_SPREAD,
)

np = lazy_module("numpy")

# Same logger object as the pre-split facade: caplog tests set levels on
# ``voice_typer.server.vad_processor`` for the records emitted here.
log = logging.getLogger("voice_typer.server.vad_processor")


class _VadCalibrationMixin:
    """Threshold auto-calibration (no ownership of the frame loop)."""

    # Host state owned by VadProcessor.__init__ (composed class).
    _calibration_duration: float
    _calibration_rms_values: list[float]
    _calibration_prob_values: list[float]
    _calibrated: bool
    _calibration_status: str
    _use_silero_vad: bool
    _silero_available: bool
    _vad_auto_calibrate: bool
    _silence_threshold: float
    _speech_threshold: float
    _silence_threshold_db: float
    _speech_threshold_db: float

    if TYPE_CHECKING:
        # Cross-mixin / facade members resolved via the composed class.
        @property
        def vad_enabled(self) -> bool: ...

        @property
        def speech_threshold_db(self) -> float: ...

        @speech_threshold_db.setter
        def speech_threshold_db(self, value: float) -> None: ...

        @property
        def silence_threshold_db(self) -> float: ...

        @silence_threshold_db.setter
        def silence_threshold_db(self, value: float) -> None: ...

    def auto_calibrate(
        self,
        chunk_rms: float,
        elapsed_seconds: float,
        chunk_duration: float = 0.0,
        vad_prob: float | None = None,
    ) -> None:
        """Auto-calibrate VAD thresholds based on ambient noise floor.

        During the first ``calibration_duration`` seconds of
                recording, we collect RMS values to determine the ambient noise
                floor. Then we set speech/silence thresholds relative to it.

                Args:
                    chunk_rms: RMS amplitude of the current chunk (linear).
                    elapsed_seconds: time since recording start (used to gate the
                        calibration window). Caller computes this from
                        ``time.perf_counter() - recording_start_time`` so this
                        module stays clock-agnostic and testable.
                    chunk_duration: duration of the chunk in seconds (reserved
                        for future per-chunk weighting; currently unused, kept
                        for signature compatibility with the prior
                        ``Recorder._vad_auto_calibrate(chunk_rms, chunk_duration)``
                        API).
                    vad_prob: Silero VAD probability for the current
                        chunk (0-1). When ``config.vad_auto_calibrate`` is
                        True AND Silero is the active backend, this is
                        collected during the calibration window and used to
                        derive the probability thresholds from the observed
                        noise floor. When None (the default), the Silero
                        path falls through to the existing ``skipped_silero``
                        behavior, preserving backwards compat.
        """
        # VAD-GATE (Task 4): skip calibration entirely when VAD is
        if not self.vad_enabled:
            self._calibration_status = "skipped_disabled"
            return
        if self._calibrated:
            return

        # when Silero VAD is the active backend, dB-threshold
        if self._use_silero_vad and self._silero_available:
            if self._vad_auto_calibrate and vad_prob is not None:
                self._calibrate_silero_thresholds(vad_prob, elapsed_seconds)
                return
            if self._vad_auto_calibrate and vad_prob is None:
                # the flag is on but the caller didn't pass
                self._calibration_status = "skipped_no_prob"
                self._calibrated = True  # prevent re-entry / log spam
                log.warning(
                    "[VAD] vad_auto_calibrate=True but vad_prob not "
                    "provided, Silero thresholds left at config defaults "
                    "[status=skipped_no_prob]"
                )
                return
            # Default (flag off): preserve the previous skip behavior.
            self._calibration_status = "skipped_silero"
            self._calibrated = True  # prevent re-entry
            log.info(
                "[VAD] auto-calibration skipped. Silero VAD active "
                "(uses probability thresholds, not RMS-dB) "
                "[status=skipped_silero]"
            )
            return

        self._calibration_rms_values.append(chunk_rms)

        if elapsed_seconds < self._calibration_duration:
            return  # still collecting samples

        if not self._calibration_rms_values:
            self._calibration_status = "skipped_no_samples"
            self._calibrated = True
            return

        # Compute noise floor from collected samples
        noise_rms = float(np.median(self._calibration_rms_values))
        # Convert to dBFS (approximately)
        noise_db = 20.0 * math.log10(noise_rms) if noise_rms > 0 else -90.0

        # Set thresholds relative to noise floor, written through the
        self.silence_threshold_db = noise_db + 6.0  # 6 dB above noise -> silence
        self.speech_threshold_db = noise_db + 18.0  # 18 dB above noise -> speech
        self._calibrated = True
        self._calibration_status = "calibrated"

        # VAD auto-calibration runs every recording start (the dB thresholds
        log.info(
            "[VAD] auto-calibrated: noise_floor=%.1f dBFS, silence_threshold=%.1f dBFS, speech_threshold=%.1f dBFS",
            noise_db,
            self._silence_threshold_db,
            self._speech_threshold_db,
        )

    def _calibrate_silero_thresholds(
        self,
        vad_prob: float,
        elapsed_seconds: float,
    ) -> None:
        """Collect Silero probabilities and derive thresholds.

        Mirrors the RMS-dB calibration math but in linear probability
        space: collect ``vad_prob`` samples during the calibration
        window, then set::

            noise_floor       = median(collected probs)
            silence_threshold = noise_floor + MARGIN
            speech_threshold  = silence_threshold + SPEECH_DELTA

        The thresholds are clamped to ``[0, 1]`` and a minimum spread
        (``MIN_VAD_SILERO_THRESHOLD_SPREAD``) is enforced so a
        degenerate noise floor (silent mic) doesn't produce
        indistinguishable thresholds.

        This is a private helper invoked from ``auto_calibrate`` when
        ``vad_auto_calibrate`` is True and Silero is the active
        backend. It mutates ``_speech_threshold`` /
        ``_silence_threshold`` / ``_calibrated`` /
        ``_calibration_status`` and appends to
        ``_calibration_prob_values``.
        """
        self._calibration_prob_values.append(float(vad_prob))

        if elapsed_seconds < self._calibration_duration:
            return  # still collecting samples

        if not self._calibration_prob_values:
            self._calibration_status = "skipped_no_samples"
            self._calibrated = True
            return

        # noise_floor = median of collected Silero probabilities.
        noise_prob = float(np.median(self._calibration_prob_values))

        # silence = noise_floor + MARGIN
        silence = noise_prob + DEFAULT_VAD_SILERO_CALIBRATION_MARGIN
        # speech = silence + SPEECH_DELTA (the finding's "silence + 6dB"
        speech = silence + DEFAULT_VAD_SILERO_SPEECH_DELTA

        # Enforce a minimum spread + clamp to [0, 1].
        if speech - silence < MIN_VAD_SILERO_THRESHOLD_SPREAD:
            speech = silence + MIN_VAD_SILERO_THRESHOLD_SPREAD
        silence = max(0.0, min(1.0, silence))
        speech = max(0.0, min(1.0, speech))
        # Final guard: if clamping inverted the order (only possible
        if speech <= silence:
            speech = min(1.0, silence + MIN_VAD_SILERO_THRESHOLD_SPREAD)

        self._silence_threshold = silence
        self._speech_threshold = speech
        self._calibrated = True
        self._calibration_status = "calibrated_silero"

        log.info(
            "[VAD] auto-calibrated Silero: noise_floor=%.3f, "
            "silence_threshold=%.3f, speech_threshold=%.3f "
            "[status=calibrated_silero]",
            noise_prob,
            self._silence_threshold,
            self._speech_threshold,
        )
