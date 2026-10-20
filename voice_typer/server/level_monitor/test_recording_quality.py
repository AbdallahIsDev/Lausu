"""Speech-only quality grading for completed microphone tests.

The score is derived from VAD-detected speech windows, so silence and
background noise outside the user's voice cannot earn a passing grade.
Energy-only grading remains as a fallback when Silero is unavailable.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

from voice_typer.server._audio_constants import (
    AUDIO_CLIPPING_THRESHOLD,
    AUDIO_LOW_VOLUME_RMS,
    AUDIO_SILENCE_RMS,
    SILERO_VAD_SAMPLE_RATES,
    WHISPER_SAMPLE_RATE,
)

MIC_TEST_GOOD_VOLUME_RMS = AUDIO_LOW_VOLUME_RMS
MIC_TEST_VERY_LOW_VOLUME_RMS = AUDIO_SILENCE_RMS

_MIC_TEST_NOISE_LOW_RMS = 0.005
_MIC_TEST_NOISE_HIGH_RMS = 0.05

_MIC_TEST_VOICE_PEAK = 0.05
_MIC_TEST_VOICE_MAX_SILENCE_RATIO = 0.95
_MIC_TEST_VOICE_MIN_NON_SILENT_BLOCKS = 3
_VAD_MIN_SPEECH_WINDOWS = 3

_NO_VOICE_ISSUE = "No voice detected, try speaking during the test"


@dataclass(frozen=True)
class SpeechAnalysis:
    """Speech evidence measured offline from one completed recording."""

    speech_detected: bool
    speech_ratio: float
    speech_rms: float
    speech_peak: float
    noise_floor_rms: float
    vad_used: bool


def _rms(audio: ArrayLike) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio, dtype=np.float32))))


def _peak(audio: ArrayLike) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.max(np.abs(audio)))


def _vad_probabilities(audio: ArrayLike, sample_rate: int) -> list[float] | None:
    from voice_typer.server.vad import compute_speech_probabilities

    return compute_speech_probabilities(audio, sample_rate)


def _resample_for_vad(audio: ArrayLike, sample_rate: int) -> tuple[ArrayLike, int] | None:
    if sample_rate == WHISPER_SAMPLE_RATE:
        return audio, WHISPER_SAMPLE_RATE
    if sample_rate in SILERO_VAD_SAMPLE_RATES:
        return audio, sample_rate
    if sample_rate <= 0:
        return None
    from voice_typer.server.recording.resampling import resample_audio

    return resample_audio(audio, sample_rate, WHISPER_SAMPLE_RATE), WHISPER_SAMPLE_RATE


def analyze_speech(
    audio: ArrayLike,
    sample_rate: int,
    *,
    probability_fn: Callable[[ArrayLike, int], list[float] | None] | None = None,
) -> SpeechAnalysis:
    """Measure speech windows without touching the live VAD stream."""
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    raw_rms = _rms(audio)
    raw_peak = _peak(audio)
    unavailable = SpeechAnalysis(False, 0.0, raw_rms, raw_peak, raw_rms, False)
    if audio.size == 0:
        return unavailable

    resampled = _resample_for_vad(audio, sample_rate)
    if resampled is None:
        return unavailable
    vad_audio, vad_rate = resampled
    probs = (probability_fn or _vad_probabilities)(vad_audio, vad_rate)
    if probs is None or not probs:
        return unavailable

    window_samples = 512 if vad_rate == 16000 else 256
    count = min(len(probs), max(1, -(-vad_audio.size // window_samples)))
    windows = [
        vad_audio[index * window_samples : (index + 1) * window_samples]
        for index in range(count)
    ]
    speech_mask = np.asarray([prob > 0.5 for prob in probs[:count]], dtype=bool)
    speech_windows = [window for window, is_speech in zip(windows, speech_mask, strict=True) if is_speech]
    speech_ratio = float(np.count_nonzero(speech_mask)) / max(1, count)

    if speech_windows:
        speech_audio = np.concatenate([window for window in speech_windows if window.size])
        speech_rms = _rms(speech_audio)
        speech_peak = _peak(speech_audio)
    else:
        speech_rms = 0.0
        speech_peak = 0.0

    background = [
        window for window, is_speech in zip(windows, speech_mask, strict=True) if not is_speech and window.size
    ]
    noise_floor = min((_rms(window) for window in background), default=0.0)
    detected = (
        bool(speech_windows)
        and len(speech_windows) >= _VAD_MIN_SPEECH_WINDOWS
        and speech_rms >= AUDIO_SILENCE_RMS
    )
    return SpeechAnalysis(
        speech_detected=detected,
        speech_ratio=round(speech_ratio, 4),
        speech_rms=speech_rms,
        speech_peak=speech_peak,
        noise_floor_rms=noise_floor,
        vad_used=True,
    )


def _volume_level(rms: float) -> str:
    if rms >= MIC_TEST_GOOD_VOLUME_RMS:
        return "good"
    if rms < MIC_TEST_VERY_LOW_VOLUME_RMS:
        return "very_low"
    return "low"


def _noise_level(noise_floor: float) -> str:
    if noise_floor < _MIC_TEST_NOISE_LOW_RMS:
        return "low"
    if noise_floor < _MIC_TEST_NOISE_HIGH_RMS:
        return "moderate"
    return "high"


def _append_environment_issues(issues: list[str], quality: dict[str, Any]) -> None:
    if quality["noise_level"] == "high":
        issues.append("High background noise")
    elif quality["noise_level"] == "moderate":
        issues.append("Moderate background noise")
    if quality["has_clipping"]:
        issues.append("Audio clipping detected")
    if quality["volume_level"] == "very_low":
        issues.append("Volume too low, speak closer to the microphone")
    elif quality["volume_level"] == "low":
        issues.append("Volume is low, consider raising input gain")


def _speech_score(speech: SpeechAnalysis) -> int:
    if not speech.speech_detected:
        return 0
    score = 100
    if speech.speech_peak >= AUDIO_CLIPPING_THRESHOLD:
        score -= 20
    if speech.speech_rms < MIC_TEST_VERY_LOW_VOLUME_RMS:
        score -= 40
    elif speech.speech_rms < MIC_TEST_GOOD_VOLUME_RMS:
        score -= 15
    if speech.speech_rms > 0.1:
        score -= 10
    return max(0, min(100, score))


def _grade_from_vad(
    speech: SpeechAnalysis,
    *,
    raw_rms: float,
    raw_peak: float,
    rms_history: Sequence[float],
    clip_count: int,
    silence_ratio: float,
) -> dict[str, Any]:
    total_blocks = len(rms_history)
    has_voice = speech.speech_detected
    volume_level = _volume_level(speech.speech_rms) if has_voice else "very_low"
    noise_level = _noise_level(speech.noise_floor_rms)
    score = _speech_score(speech)

    quality: dict[str, Any] = {
        "volume_level": volume_level,
        "volume_rms": round(raw_rms, 6),
        "peak_level": round(raw_peak, 4),
        "noise_level": noise_level,
        "has_voice": has_voice,
        "has_clipping": has_voice and speech.speech_peak >= AUDIO_CLIPPING_THRESHOLD,
        "clipping_blocks": clip_count,
        "total_blocks": total_blocks,
        "silence_ratio": silence_ratio,
        "avg_rms": round(float(np.mean(rms_history) if total_blocks else 0), 6),
        "peak_rms": round(float(np.max(rms_history) if total_blocks else 0), 6),
        "speech_quality": score,
        "speech_ratio": speech.speech_ratio,
        "speech_rms": round(speech.speech_rms, 6),
        "speech_peak": round(speech.speech_peak, 4),
        "noise_floor_rms": round(speech.noise_floor_rms, 6),
        "vad_used": True,
    }

    issues: list[str] = []
    if has_voice:
        _append_environment_issues(issues, quality)
    else:
        issues.append(_NO_VOICE_ISSUE)
    quality["detected_issues"] = issues

    estimated = score
    if quality["noise_level"] == "high":
        estimated -= 30
    elif quality["noise_level"] == "moderate":
        estimated -= 10
    quality["estimated_transcription_quality"] = max(0, min(100, estimated))
    return quality


def _grade_from_energy(
    *,
    raw_rms: float,
    raw_peak: float,
    rms_history: Sequence[float],
    clip_count: int,
    silence_blocks: int,
) -> dict[str, Any]:
    total_blocks = len(rms_history)
    silence_ratio = round(silence_blocks / max(1, total_blocks), 4)
    non_silent_blocks = total_blocks - silence_blocks
    if total_blocks > 0:
        has_voice = (
            raw_peak > _MIC_TEST_VOICE_PEAK
            and silence_ratio < _MIC_TEST_VOICE_MAX_SILENCE_RATIO
            and non_silent_blocks >= _MIC_TEST_VOICE_MIN_NON_SILENT_BLOCKS
        )
    else:
        has_voice = raw_peak > _MIC_TEST_VOICE_PEAK

    noise_floor = float(min(rms_history)) if rms_history else raw_rms
    noise_level = _noise_level(noise_floor)
    if has_voice and noise_level == "high":
        noise_level = "moderate"

    quality: dict[str, Any] = {
        "volume_level": _volume_level(raw_rms),
        "volume_rms": round(raw_rms, 6),
        "peak_level": round(raw_peak, 4),
        "noise_level": noise_level,
        "has_voice": has_voice,
        "has_clipping": clip_count > 0,
        "clipping_blocks": clip_count,
        "total_blocks": total_blocks,
        "silence_ratio": silence_ratio,
        "avg_rms": round(float(np.mean(rms_history) if total_blocks else 0), 6),
        "peak_rms": round(float(np.max(rms_history) if total_blocks else 0), 6),
        "speech_ratio": round(1.0 - silence_ratio, 4),
        "speech_rms": round(raw_rms, 6),
        "speech_peak": round(raw_peak, 4),
        "noise_floor_rms": round(noise_floor, 6),
        "vad_used": False,
    }

    issues: list[str] = []
    _append_environment_issues(issues, quality)
    if not has_voice:
        issues.append(_NO_VOICE_ISSUE)
    quality["detected_issues"] = issues

    estimated = 100
    if noise_level == "high":
        estimated -= 30
    elif noise_level == "moderate":
        estimated -= 10
    if quality["has_clipping"]:
        estimated -= 20
    if quality["volume_level"] == "very_low":
        estimated -= 40
    elif quality["volume_level"] == "low":
        estimated -= 15
    if not has_voice:
        estimated = 0
    if raw_rms > 0.1:
        estimated = max(0, estimated - 10)
    estimated = max(0, min(100, estimated))
    quality["speech_quality"] = estimated
    quality["estimated_transcription_quality"] = estimated
    return quality


def grade_test_quality(
    *,
    raw_audio: ArrayLike,
    sample_rate: int,
    rms_history: Sequence[float],
    clip_count: int,
    silence_blocks: int,
) -> dict[str, Any]:
    """Build the mic-test verdict from speech evidence plus capture stats."""
    audio = np.asarray(raw_audio, dtype=np.float32).reshape(-1)
    raw_rms = _rms(audio)
    raw_peak = _peak(audio)
    total_blocks = len(rms_history)
    silence_ratio = round(silence_blocks / max(1, total_blocks), 4)

    speech = analyze_speech(audio, sample_rate)
    if speech.vad_used:
        return _grade_from_vad(
            speech,
            raw_rms=raw_rms,
            raw_peak=raw_peak,
            rms_history=rms_history,
            clip_count=clip_count,
            silence_ratio=silence_ratio,
        )
    return _grade_from_energy(
        raw_rms=raw_rms,
        raw_peak=raw_peak,
        rms_history=rms_history,
        clip_count=clip_count,
        silence_blocks=silence_blocks,
    )
