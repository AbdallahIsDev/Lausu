"""Speech-only microphone-test grading driven by VAD evidence."""

from __future__ import annotations

import numpy as np
import pytest
from voice_typer.server.level_monitor import test_recording_quality as quality

SAMPLE_RATE = 16000
NO_VOICE = "No voice detected, try speaking during the test"


def _tone(seconds: float, amplitude: float = 0.02) -> np.ndarray:
    t = np.arange(int(SAMPLE_RATE * seconds), dtype=np.float64) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


@pytest.fixture(autouse=True)
def _reset_level_state():
    import voice_typer.server.level_monitor as lm

    lm._reset_state_for_tests()
    yield
    lm._reset_state_for_tests()


def _speech(**overrides) -> quality.SpeechAnalysis:
    values = {
        "speech_detected": True,
        "speech_ratio": 0.5,
        "speech_rms": 0.03,
        "speech_peak": 0.0424,
        "noise_floor_rms": 0.001,
        "vad_used": True,
    }
    values.update(overrides)
    return quality.SpeechAnalysis(**values)


def _grade(analysis: quality.SpeechAnalysis, *, raw_audio=None, clip_count=0) -> dict:
    audio = raw_audio if raw_audio is not None else _tone(1.0, 0.0424)
    original = quality.analyze_speech
    quality.analyze_speech = lambda audio, sample_rate: analysis
    try:
        return quality.grade_test_quality(
            raw_audio=audio,
            sample_rate=SAMPLE_RATE,
            rms_history=[0.03] * 31,
            clip_count=clip_count,
            silence_blocks=0,
        )
    finally:
        quality.analyze_speech = original


class TestAnalyzeSpeech:
    def test_measures_only_vad_positive_windows(self):
        probs = [0.9] * 4 + [0.1] * 28
        seen: list[int] = []
        speech = _tone(1.0)[:2048]
        audio_in = np.concatenate([speech, np.zeros(SAMPLE_RATE - speech.size, dtype=np.float32)])

        def probability_fn(audio: np.ndarray, sample_rate: int):
            seen.append(sample_rate)
            assert audio.size == SAMPLE_RATE
            return probs

        result = quality.analyze_speech(audio_in, SAMPLE_RATE, probability_fn=probability_fn)

        assert seen == [SAMPLE_RATE]
        assert result.vad_used is True
        assert result.speech_detected is True
        assert result.speech_ratio == pytest.approx(4 / 32)
        assert result.speech_rms == pytest.approx(0.02 / np.sqrt(2), rel=0.02)
        assert result.speech_peak == pytest.approx(0.02, rel=0.02)
        assert result.noise_floor_rms == pytest.approx(0.0, abs=1e-6)

    def test_all_negative_windows_report_no_speech(self):
        result = quality.analyze_speech(
            _tone(1.0, 0.2),
            SAMPLE_RATE,
            probability_fn=lambda audio, sample_rate: [0.05] * 32,
        )

        assert result.vad_used is True
        assert result.speech_detected is False
        assert result.speech_ratio == 0.0

    def test_resamples_native_audio_before_vad(self):
        captured: dict[str, object] = {}

        def probability_fn(audio: np.ndarray, sample_rate: int):
            captured["size"] = audio.size
            captured["rate"] = sample_rate
            return [0.9] * 32

        native = np.repeat(_tone(1.0), 3)
        quality.analyze_speech(native, 48000, probability_fn=probability_fn)

        assert captured["rate"] == SAMPLE_RATE
        assert captured["size"] == pytest.approx(SAMPLE_RATE, abs=2)

    def test_unavailable_vad_marks_analysis_as_unused(self):
        result = quality.analyze_speech(
            _tone(1.0),
            SAMPLE_RATE,
            probability_fn=lambda audio, sample_rate: None,
        )

        assert result.vad_used is False
        assert result.speech_detected is False


class TestSpeechOnlyScore:
    def test_high_noise_does_not_lower_speech_quality(self):
        result = _grade(_speech(noise_floor_rms=0.2))

        assert result["vad_used"] is True
        assert result["has_voice"] is True
        assert result["volume_level"] == "good"
        assert result["noise_level"] == "high"
        assert result["speech_quality"] == 100
        assert result["estimated_transcription_quality"] == 70
        assert "High background noise" in result["detected_issues"]

    def test_no_speech_scores_zero_even_in_loud_noise(self):
        result = _grade(_speech(speech_detected=False, noise_floor_rms=0.5), clip_count=9)

        assert result["speech_quality"] == 0
        assert result["estimated_transcription_quality"] == 0
        assert result["has_voice"] is False
        assert result["has_clipping"] is False
        assert result["volume_level"] == "very_low"
        assert result["detected_issues"] == [NO_VOICE]

    def test_speech_clipping_lowers_speech_quality(self):
        result = _grade(_speech(speech_peak=0.995, speech_rms=0.05))

        assert result["has_clipping"] is True
        assert result["speech_quality"] == 80
        assert "Audio clipping detected" in result["detected_issues"]


class TestStopRecordingIntegration:
    def test_stop_returns_speech_fields(self):
        from voice_typer.server.level_monitor import test_recording as recording
        from voice_typer.server.level_monitor._state import _state

        analysis = _speech(speech_ratio=0.75, speech_rms=0.02)
        original = quality.analyze_speech
        quality.analyze_speech = lambda audio, sample_rate: analysis
        try:
            _state._test_mode = True
            _state._monitor_sample_rate = SAMPLE_RATE
            _state._test_raw_chunks.append(_tone(1.0, 0.03))
            _state._test_rms_history.extend([0.02] * 31)
            result = recording.stop_test_recording()
        finally:
            quality.analyze_speech = original

        payload = result["quality"]
        assert result["success"] is True
        assert payload["vad_used"] is True
        assert payload["speech_quality"] == 100
        assert payload["speech_ratio"] == 0.75
        assert payload["speech_rms"] == pytest.approx(0.02)
        assert payload["noise_floor_rms"] == pytest.approx(0.001)
