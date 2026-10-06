"""Canonical VAD threshold/frame constants shared by the VAD processor
split modules.

Split from ``voice_typer/server/vad_processor.py`` (create-first); the
facade re-exports every constant so ``vad_processor.DEFAULT_VAD_*`` /
``vad_processor.MIN_VAD_*`` keep resolving (pinned by
``tests/test_vad_constants_cleanup.py``).
"""

from __future__ import annotations

# default VAD thresholds (overridden by auto-calibration)
DEFAULT_VAD_SPEECH_THRESHOLD_DB = -40.0  # dBFS, above this → speech candidate
DEFAULT_VAD_SILENCE_THRESHOLD_DB = -50.0  # dBFS, below this → silence candidate
# Threshold floors on the user-configurable values.
MIN_VAD_SPEECH_THRESHOLD_DB = -55.0  # dBFS, speech floor
MIN_VAD_SILENCE_THRESHOLD_DB = -65.0  # dBFS, silence floor (must be below speech floor)
DEFAULT_VAD_CALIBRATION_DURATION = 1.5  # seconds of ambient noise to sample
DEFAULT_VAD_SPEECH_FRAMES = 3  # consecutive loud frames to declare SPEECH
DEFAULT_VAD_SILENCE_FRAMES = 15  # consecutive quiet frames to declare SILENCE (hangover)
DEFAULT_VAD_HANGOVER_FRAMES = 15  # same as SILENCE_FRAMES, configurable alias

# Silero-probability auto-calibration constants. When
DEFAULT_VAD_SILERO_CALIBRATION_MARGIN: float = 0.05  # silence = noise_floor + 0.05
DEFAULT_VAD_SILERO_SPEECH_DELTA: float = 0.15  # speech = silence + 0.15 (~6 dB gap equivalent)
# Minimum separation between speech and silence Silero thresholds after
MIN_VAD_SILERO_THRESHOLD_SPREAD: float = 0.10

# Silero VAD probability thresholds. These must match the canonical
try:  # pragma: no cover - import shim, exercised at runtime
    from voice_typer.server.config import Config as _Config

    DEFAULT_VAD_SPEECH_PROB_THRESHOLD: float = _Config.vad_speech_threshold
    DEFAULT_VAD_SILENCE_PROB_THRESHOLD: float = _Config.vad_silence_threshold
except Exception:  # pragma: no cover - defensive fallback for partial imports
    DEFAULT_VAD_SPEECH_PROB_THRESHOLD = 0.5
    DEFAULT_VAD_SILENCE_PROB_THRESHOLD = 0.3
