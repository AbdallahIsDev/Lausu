"""Filter-divergence guard: a lying chain must never eat a dictation.

docs/microphone-filter-failures.md §2.3. Two layers are covered here:

* :class:`FilterDivergenceGuard` math (speech detection, cumulative collapse,
  latching, reset).
* :class:`FilterFallback` + :class:`AudioPipeline` integration (raw shadow,
  mid-recording swap, silence-timer suspension, stop-time fallback).
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock

import numpy as np
import pytest
from voice_typer.server._audio_constants import AUDIO_SILENCE_RMS
from voice_typer.server.recording import filter_divergence
from voice_typer.server.recording.audio_pipeline import AudioPipeline
from voice_typer.server.recording.filter_divergence import (
    COLLAPSE_DB,
    COLLAPSE_SECONDS,
    REASON_COLLAPSE,
    REASON_SILENT_TAKE,
    FilterDivergenceGuard,
    FilterFallback,
    rms_dbfs,
)

SR = 16000
CHUNK = 512  # 32 ms at 16 kHz
CHUNK_SECONDS = CHUNK / SR


def _chunk(peak: float) -> np.ndarray:
    t = np.arange(CHUNK, dtype=np.float32)
    return (peak * np.sin(2.0 * np.pi * 200.0 * t / SR)).astype(np.float32)


def _speech_chunk(i: int) -> np.ndarray:
    """Continuous 200 Hz voiced carrier with a 4 Hz syllable envelope."""
    t = np.arange(CHUNK, dtype=np.float32) + i * CHUNK
    envelope = 0.03 + 0.02 * np.sin(2.0 * np.pi * 4.0 * t / SR)
    return (envelope * np.sin(2.0 * np.pi * 200.0 * t / SR)).astype(np.float32)


def _noise_signal(seconds: float = 12.0) -> np.ndarray:
    """One continuous band-limited (pink-ish) noise signal at unit RMS."""
    n = int(SR * seconds)
    rng = np.random.default_rng(4242)
    white = rng.standard_normal(n).astype(np.float32)
    spectrum = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, d=1.0 / SR)
    spectrum[1:] /= np.sqrt(np.maximum(freqs[1:], 1.0))
    spectrum[0] = 0.0
    shaped = np.fft.irfft(spectrum, n=n).astype(np.float32)
    return shaped / max(float(np.sqrt(np.mean(shaped**2))), 1e-12)


_NOISE = _noise_signal()


def _noise_chunk(level: float, index: int) -> np.ndarray:
    """Consecutive 32 ms slices of the continuous noise signal."""
    start = (index * CHUNK) % (len(_NOISE) - CHUNK - 1)
    return np.asarray(_NOISE[start : start + CHUNK] * level, dtype=np.float32)


class _EatingProcessor:
    """Fake AudioProcessor whose chain deletes everything (the failure case)."""

    _sample_rate = SR

    def __init__(self, filtered_scale: float = 0.0) -> None:
        self._chain = types.SimpleNamespace(filter_names=["HighPass(80Hz)", "NoiseSuppressor(dpdfnet)"])
        self._filtered_scale = filtered_scale
        self._filter_bypass = False
        self.bypass_requests: list[bool] = []

    def set_filter_bypass(self, bypassed: bool) -> None:
        self._filter_bypass = bool(bypassed)
        self.bypass_requests.append(bool(bypassed))

    def process_chunk(self, chunk, input_sample_rate=None):
        if self._filter_bypass:
            # Mirrors AudioProcessor._process_chunk_impl: rate conversion and
            # the quality probe still run, only the filter stages are skipped.
            return chunk
        return (chunk * self._filtered_scale).astype(np.float32)


class _HonestProcessor(_EatingProcessor):
    """Fake chain that attenuates noise but keeps speech audible."""

    def __init__(self) -> None:
        super().__init__(filtered_scale=0.9)


class TestRmsDbfs:
    def test_zero_and_negative_clamp(self):
        assert rms_dbfs(0.0) == -200.0
        assert rms_dbfs(-1.0) == -200.0
        assert rms_dbfs(float("nan")) == -200.0

    def test_reference_levels(self):
        assert rms_dbfs(1.0) == pytest.approx(0.0)
        assert rms_dbfs(0.01) == pytest.approx(-40.0)


class TestFilterDivergenceGuard:
    def test_steady_loud_noise_never_trips(self):
        """A fan/HVAC floor is loud but unvoiced; a suppressor may remove it."""
        guard = FilterDivergenceGuard()
        for i in range(100):
            chunk = _noise_chunk(0.05, i)
            assert guard.observe(chunk, 0.0, CHUNK_SECONDS, SR) is False
        assert guard.tripped is False
        assert guard.saw_speech is False, "unvoiced noise is not speech"

    def test_the_chain_removing_loud_noise_60db_does_not_trip(self):
        """The exact case the guard must not punish: a suppressor doing its job."""
        guard = FilterDivergenceGuard()
        for i in range(200):
            chunk = _noise_chunk(0.04, 1000 + i)
            assert guard.observe(chunk, 0.0, CHUNK_SECONDS, SR) is False
        assert guard.tripped is False

    def test_pauses_between_sentences_do_not_accumulate(self):
        """Voiced speech, then a long silent pause with a silent filter output.

        The old envelope test let the window max carry the last syllable, so a
        noisy room tripped the guard during every pause (bench/stress_mic_filters.py).
        """
        guard = FilterDivergenceGuard()
        for i in range(30):
            chunk = _speech_chunk(i)
            raw_db = rms_dbfs(float(np.sqrt(np.dot(chunk, chunk) / CHUNK)))
            guard.observe(chunk, float(np.sqrt(np.dot(chunk, chunk) / CHUNK)), CHUNK_SECONDS, SR)
            assert guard.tripped is False, f"honest speech tripped at chunk {i} (raw {raw_db:.1f} dBFS)"
        # 2 s of en-unvoiced background: both raw and filtered near zero.
        for i in range(60):
            chunk = _noise_chunk(0.0004, 2000 + i)
            assert guard.observe(chunk, 0.0, CHUNK_SECONDS, SR) is False
        assert guard.tripped is False

    def test_modulated_speech_with_flat_chain_does_not_trip(self):
        guard = FilterDivergenceGuard()
        for i in range(60):
            raw = _speech_chunk(i)
            raw_rms = float(np.sqrt(np.dot(raw, raw) / CHUNK))
            assert guard.observe(raw, raw_rms, CHUNK_SECONDS, SR) is False
        assert guard.tripped is False

    def test_legitimate_suppression_of_noise_on_speech_does_not_trip(self):
        """Speech kept within 25 dB of raw while steady noise is removed."""
        guard = FilterDivergenceGuard()
        for i in range(60):
            raw = _speech_chunk(i)
            raw_rms = float(np.sqrt(np.dot(raw, raw) / CHUNK))
            # -20 dB: allowed suppression, well under the 25 dB collapse bar.
            assert guard.observe(raw, raw_rms * 0.1, CHUNK_SECONDS, SR) is False
        assert guard.tripped is False

    def test_a_minute_of_loud_noise_never_trips(self):
        """Long-run regression: lucky pitch spikes must not accumulate a trip.

        The stress harness found this: 35 s of pink noise at -36 dBFS (removed
        60+ dB by the suppressor) crossed the cumulative bar until the trip
        also required one unbroken deleted run.
        """
        guard = FilterDivergenceGuard()
        for i in range(1800):  # 57.6 s at 32 ms
            assert guard.observe(_noise_chunk(0.014, i), 0.0, CHUNK_SECONDS, SR) is False
        assert guard.tripped is False
        assert guard.saw_speech is False

    def test_collapse_trips_once_after_cumulative_window(self):
        guard = FilterDivergenceGuard()
        trips = []
        for i in range(40):
            raw = _speech_chunk(i)
            if guard.observe(raw, 0.0, CHUNK_SECONDS, SR):
                trips.append(i)
        assert len(trips) == 1, f"the guard must latch exactly once, got {trips}"
        assert (trips[0] + 1) * CHUNK_SECONDS > COLLAPSE_SECONDS
        assert guard.tripped is True
        assert guard.delta_db > COLLAPSE_DB

    def test_reset_clears_the_latch(self):
        guard = FilterDivergenceGuard()
        for i in range(20):
            guard.observe(_speech_chunk(i), 0.0, CHUNK_SECONDS, SR)
        assert guard.tripped is True
        guard.reset()
        assert guard.tripped is False
        assert guard.saw_speech is False
        assert guard.delta_db == 0.0

    def test_speech_requires_loud_enough_audio(self):
        guard = FilterDivergenceGuard()
        for i in range(40):
            tiny = _speech_chunk(i) * 0.0005  # well under -60 dBFS
            guard.observe(tiny, 0.0, CHUNK_SECONDS, SR)
        assert guard.tripped is False
        assert guard.saw_speech is False


def _pipeline_stub(processor, effective_sr: int = SR):
    recorder = MagicMock(name="RecorderStub")
    recorder._effective_sr = effective_sr
    recorder._audio_processor = processor
    recorder.config.sample_rate = effective_sr
    recorder.config.audio_preset = "auto"
    recorder.config.noise_suppression_method = "dpdfnet"
    pipeline = AudioPipeline(recorder)
    recorder._audio_pipeline = pipeline
    return recorder, pipeline


def _push(pipeline, chunk: np.ndarray) -> np.ndarray:
    filtered = pipeline.apply_filter_chain(chunk)
    pipeline.append_to_buffer_locked(filtered)
    return filtered


class TestFilterFallbackPipeline:
    def test_shadow_only_exists_when_the_chain_can_eat_speech(self):
        honest = _EatingProcessor()
        honest._chain = types.SimpleNamespace(filter_names=["HighPass(80Hz)", "Limiter(-1dB)"])
        _rec, pipeline = _pipeline_stub(honest)
        _push(pipeline, _chunk(0.05))
        assert pipeline._filter_fallback.active() is False

        eating = _EatingProcessor()
        _rec2, pipeline2 = _pipeline_stub(eating)
        _push(pipeline2, _chunk(0.05))
        assert pipeline2._filter_fallback.active() is True

    def test_collapse_swaps_the_take_to_raw_audio(self):
        recorder, pipeline = _pipeline_stub(_EatingProcessor())
        delivered = []
        for i in range(20):
            delivered.append(len(_push(pipeline, _speech_chunk(i))))

        assert pipeline._filter_fallback.tripped is True
        exported = pipeline._buffer.export_copy()
        rms = float(np.sqrt(np.dot(exported, exported) / exported.size))
        assert rms > AUDIO_SILENCE_RMS, "the swapped take must carry the real speech"
        assert len(exported) == sum(delivered), "no audio may be lost or duplicated on the swap"
        assert recorder._audio_processor.bypass_requests == [True]

    def test_after_the_trip_the_chain_is_bypassed(self):
        processor = _EatingProcessor()
        _rec, pipeline = _pipeline_stub(processor)
        for i in range(20):
            _push(pipeline, _speech_chunk(i))

        chunk = _speech_chunk(0)
        out = pipeline.apply_filter_chain(chunk)
        assert np.array_equal(out, chunk), "post-trip chunks must be delivered raw"

    def test_silence_timer_is_suspended_while_the_guard_is_active(self):
        _rec, pipeline = _pipeline_stub(_EatingProcessor())
        for i in range(20):
            _push(pipeline, _speech_chunk(i))
        assert pipeline._filter_fallback.suspend_silence() is True

        _rec2, pipeline2 = _pipeline_stub(_HonestProcessor())
        _push(pipeline2, _chunk(0.05))
        assert pipeline2._filter_fallback.suspend_silence() is False

    def test_stop_time_fallback_recovers_a_short_silent_take(self):
        """Speech on raw, silence after filtering, guard never latched."""
        _rec, pipeline = _pipeline_stub(_EatingProcessor())
        for i in range(4):
            _push(pipeline, _speech_chunk(i))
        fallback = pipeline._filter_fallback
        assert fallback.tripped is False
        assert fallback.saw_speech is True

        reason = fallback.finalize(pipeline._recorder)
        assert reason == REASON_SILENT_TAKE
        exported = pipeline._buffer.export_copy()
        assert float(np.sqrt(np.dot(exported, exported) / exported.size)) > AUDIO_SILENCE_RMS

    def test_stop_time_fallback_leaves_a_healthy_take_alone(self):
        _rec, pipeline = _pipeline_stub(_HonestProcessor())
        for i in range(20):
            _push(pipeline, _speech_chunk(i))
        assert pipeline._filter_fallback.finalize(pipeline._recorder) is None

    def test_no_fallback_without_speech(self):
        _rec, pipeline = _pipeline_stub(_EatingProcessor())
        for _ in range(30):
            _push(pipeline, _chunk(0.0002))
        assert pipeline._filter_fallback.saw_speech is False
        assert pipeline._filter_fallback.finalize(pipeline._recorder) is None

    def test_reset_starts_a_clean_take(self):
        recorder, pipeline = _pipeline_stub(_EatingProcessor())
        for i in range(20):
            _push(pipeline, _speech_chunk(i))
        fallback = pipeline._filter_fallback
        assert fallback.tripped is True
        fallback.reset(recorder)
        assert fallback.tripped is False
        assert fallback.swapped is False
        assert fallback.active() is False

    def test_summary_fields_carry_both_levels_and_state(self):
        _rec, pipeline = _pipeline_stub(_EatingProcessor())
        for i in range(20):
            _push(pipeline, _speech_chunk(i))
        fields = pipeline._filter_fallback.summary_fields()
        assert set(fields) == {"raw_db", "filtered_db", "delta_db", "guard"}
        assert fields["guard"] in {"tripped", "swapped", "ok"}
        assert fields["delta_db"] > COLLAPSE_DB


class TestReportFallback:
    def test_warns_and_publishes_once_per_process(self, monkeypatch):
        published: list[dict] = []
        monkeypatch.setattr(filter_divergence, "_reported_reasons", set())
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish",
            lambda event: published.append(event),
        )
        recorder = MagicMock()
        recorder.config.audio_preset = "auto"
        recorder.config.noise_suppression_method = "dpdfnet"
        fallback = FilterFallback()
        fallback._guard.raw_db = -20.0
        fallback._guard.filtered_db = -60.0
        fallback._guard.delta_db = 40.0
        fallback._guard.tripped = True

        filter_divergence.report_fallback(recorder, fallback, REASON_COLLAPSE)
        filter_divergence.report_fallback(recorder, fallback, REASON_COLLAPSE)

        assert len(published) == 1, "one toast per process, not one per recording"
        assert published[0]["type"] == "filter_collapse"
        data = published[0]["data"]
        assert data["reason"] == REASON_COLLAPSE
        assert data["raw_db"] == -20.0
        assert data["filtered_db"] == -60.0
        assert data["preset"] == "auto"
        assert data["method"] == "dpdfnet"
