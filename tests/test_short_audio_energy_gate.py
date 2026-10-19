"""Short-audio energy gate: exact proceed/discard contract for sub-0.5s clips.

The stop+transcribe pipeline used to reject any clip under 0.5s on duration
alone, dropping crisp short words ("yes", "no", "stop") the same way as an
accidental tap. The gate now keeps sub-threshold clips only when they carry
speech-like energy (RMS at/above the speech floor and not mostly silence);
such clips reach the normal pipeline (TRANSCRIBING + DictationPipeline.run).
Clips at/above 0.5s keep the unchanged historical duration-only behavior.

All audio is synthetic numpy; the recorder, tray, bubble, busyness, and the
DictationPipeline are mocked. No real mic, model, or network.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from voice_typer.server.recording_lifecycle import (
    MAX_SHORT_SILENCE_PCT,
    MIN_DURATION_S,
    MIN_SHORT_RMS,
    RecordingLifecycle,
    _short_clip_has_speech_energy,
    _short_clip_rms,
    _short_clip_silence_pct,
)
from voice_typer.server.tray_types import AppState

SR = 16000


def _audio_stats(audio: np.ndarray) -> tuple[float, float, float]:
    """Real stop-time stats for synthetic audio (mirrors Recorder.stop())."""
    if audio.size == 0:
        return 0.0, 0.0, 0.0
    flat = audio.reshape(-1)
    rms = float(np.sqrt(np.dot(flat, flat) / flat.size))
    peak = float(np.max(np.abs(flat)))
    silence_pct = float(np.mean(np.abs(flat) < 0.001) * 100.0)
    return rms, peak, silence_pct


def _shape_audio(kind: str, duration_s: float, rng: np.random.Generator) -> np.ndarray:
    """Synthetic clip shapes: silence, quiet tap, speech, half-speech, click."""
    n = int(duration_s * SR)
    audio = np.zeros(n, dtype=np.float32)
    if kind == "silence":
        pass
    elif kind == "quiet_tap":
        tap = int(0.025 * SR)
        audio[:tap] = rng.uniform(-0.004, 0.004, tap)
    elif kind == "speech":
        audio[:] = rng.uniform(-0.2, 0.2, n)
    elif kind == "speech_half":
        half = n // 2
        audio[:half] = rng.uniform(-0.2, 0.2, half)
    elif kind == "loud_click":
        click = max(1, int(0.003 * SR))
        audio[:click] = rng.uniform(0.5, 1.0, click)
    else:
        raise ValueError(kind)
    return audio


class _GateResult:
    def __init__(self, app, controller, pipeline_mock):
        self.app = app
        self.controller = controller
        self.pipeline = pipeline_mock


_UNSET = object()


def _drive_gate(audio: np.ndarray, last_rms=_UNSET) -> _GateResult:
    """Run the real gate path with mocks and real stop-time stats."""
    rms, _peak, silence_pct = _audio_stats(audio)
    app = MagicMock(name="app")
    app.recorder = MagicMock(name="recorder")
    app.recorder._dropped_ring_chunks = 0
    app.recorder.last_rms = rms if last_rms is _UNSET else last_rms
    app.recorder._last_audio_stats = (rms, _peak, silence_pct)
    app.config = MagicMock()
    app.config.sample_rate = SR
    app.config.bubble_behavior = "show_on_record"
    app.tray = MagicMock()
    app._waveform_bubble = MagicMock()
    app._busyness = MagicMock()
    app._schedule_timer = MagicMock()
    app._restore_volume = MagicMock()
    app._finalize_audio_quality_report = MagicMock()
    app._cycle_id = "#gate"
    controller = MagicMock(name="controller")
    controller._app = app
    controller._watchdog_lock = threading.Lock()
    controller._cancel_streaming_session = MagicMock()
    controller._maybe_restart_level_monitor_for_always_visible_bubble = MagicMock()
    with patch("voice_typer.server.dictation_pipeline.DictationPipeline") as pipeline_cls:
        RecordingLifecycle()._run_stop_and_transcribe(controller, audio, "#gate")
    return _GateResult(app, controller, pipeline_cls.return_value.run)


def _assert_proceeded(result: _GateResult, audio: np.ndarray) -> None:
    rms, _peak, _sil = _audio_stats(audio)
    result.pipeline.assert_called_once()
    kwargs = result.pipeline.call_args.kwargs
    assert kwargs["cycle_id"] == "#gate"
    assert kwargs["recorded_rms"] == pytest.approx(rms)
    assert kwargs["duration"] == pytest.approx(len(audio) / SR)
    result.app.tray.set_state.assert_called_once()
    assert result.app.tray.set_state.call_args.args[0] == AppState.TRANSCRIBING
    result.controller._cancel_streaming_session.assert_not_called()
    result.app._waveform_bubble.hide.assert_not_called()
    result.app._waveform_bubble.set_state.assert_not_called()


def _assert_discarded(result: _GateResult) -> None:
    result.pipeline.assert_not_called()
    result.controller._cancel_streaming_session.assert_called_once()
    result.app.tray.set_state.assert_called_once()
    assert result.app.tray.set_state.call_args.args[0] == AppState.IDLE
    result.app._waveform_bubble.hide.assert_called_once()
    result.app._waveform_bubble.set_state.assert_not_called()
    result.app._busyness.set_idle.assert_called_once()


DURATIONS = [0.10, 0.30, 0.49, 0.50, 0.51]
SILENT_SHAPES = ["silence", "quiet_tap", "loud_click"]
SPEECH_SHAPES = ["speech", "speech_half"]


def _expected_proceed(kind: str, duration_s: float) -> bool:
    """Independent rule table with literal thresholds (mirrors the pinned
    constants; a threshold flip must fail these tables): duration >= 0.5
    always proceeds; below it only speech-like shapes."""
    if duration_s >= 0.5:
        return True
    return kind in SPEECH_SHAPES


def _raw_expected_proceed(rms: float, silence_pct: float, duration_s: float) -> bool:
    """Literal-threshold rule table for the fuzz sweep (0.5s / 0.01 / 95.0)."""
    return duration_s >= 0.5 or (rms >= 0.01 and silence_pct < 95.0)


@pytest.mark.parametrize("round_no", [0, 1, 2])
def test_boundary_matrix_is_stable(round_no: int):
    """0.10/0.30/0.49/0.50/0.51s x silence/tap/click/speech/half-speech,
    repeated 3 rounds for flakiness."""
    rng = np.random.default_rng(1234 + round_no)
    for duration_s in DURATIONS:
        for kind in SILENT_SHAPES + SPEECH_SHAPES:
            audio = _shape_audio(kind, duration_s, rng)
            result = _drive_gate(audio)
            expected = _expected_proceed(kind, duration_s)
            if expected:
                _assert_proceeded(result, audio)
            else:
                _assert_discarded(result)


def test_loud_word_survives_and_loud_click_is_rejected():
    """The core pair: a loud 0.3s word proceeds; a loud 3ms click in 0.3s of
    silence is a tap and is discarded (silence ceiling separates them)."""
    rng = np.random.default_rng(7)
    word = _shape_audio("speech", 0.30, rng)
    click = _shape_audio("loud_click", 0.30, rng)

    word_rms, _p, word_silence = _audio_stats(word)
    click_rms, _p2, click_silence = _audio_stats(click)
    assert word_rms >= MIN_SHORT_RMS and word_silence < MAX_SHORT_SILENCE_PCT
    assert click_rms >= MIN_SHORT_RMS and click_silence >= MAX_SHORT_SILENCE_PCT

    _assert_proceeded(_drive_gate(word), word)
    _assert_discarded(_drive_gate(click))


def test_quiet_tap_and_long_silence_are_rejected():
    rng = np.random.default_rng(11)
    for kind in ("quiet_tap", "silence"):
        for duration_s in (0.10, 0.49):
            _assert_discarded(_drive_gate(_shape_audio(kind, duration_s, rng)))


def test_above_threshold_keeps_duration_only_behavior():
    """>= 0.5s is NOT energy-gated: even silence proceeds (unchanged history)."""
    rng = np.random.default_rng(21)
    for kind in SILENT_SHAPES + SPEECH_SHAPES:
        audio = _shape_audio(kind, 1.0, rng)
        _assert_proceeded(_drive_gate(audio), audio)


def test_missing_silence_stats_fall_back_to_energy_only():
    """A recorder without tuple stats: RMS alone decides (>= floor proceeds)."""
    audio = _shape_audio("speech", 0.30, np.random.default_rng(31))
    rms, _peak, _sil = _audio_stats(audio)
    app = MagicMock(name="app")
    app.recorder = MagicMock(name="recorder")
    app.recorder._dropped_ring_chunks = 0
    app.recorder.last_rms = rms
    app.config = MagicMock()
    app.config.sample_rate = SR
    app.config.bubble_behavior = "show_on_record"
    app.tray = MagicMock()
    app._waveform_bubble = MagicMock()
    app._busyness = MagicMock()
    app._schedule_timer = MagicMock()
    app._restore_volume = MagicMock()
    app._finalize_audio_quality_report = MagicMock()
    controller = MagicMock(name="controller")
    controller._app = app
    controller._watchdog_lock = threading.Lock()
    controller._cancel_streaming_session = MagicMock()
    controller._maybe_restart_level_monitor_for_always_visible_bubble = MagicMock()
    with patch("voice_typer.server.dictation_pipeline.DictationPipeline") as pipeline_cls:
        RecordingLifecycle()._run_stop_and_transcribe(controller, audio, "#gate")
    pipeline_cls.return_value.run.assert_called_once()


def test_fuzz_two_hundred_clips_match_rule_table_and_stay_fast():
    """200+ randomized clips (0.05-0.8s, mixed loudness/presence): no crash,
    gate decision matches the independent rule table computed from the
    constants, discards never run the pipeline, and the gate cost is trivial."""
    rng = np.random.default_rng(20261018)
    mismatches: list[tuple] = []
    started = time.perf_counter()
    for _ in range(220):
        duration_s = float(rng.uniform(0.05, 0.8))
        n = int(duration_s * SR)
        audio = np.zeros(n, dtype=np.float32)
        mode = rng.integers(0, 4)
        if mode == 0:  # silence
            pass
        elif mode == 1:  # quiet presence
            frac = float(rng.uniform(0.0, 0.3))
            span = int(n * frac)
            if span:
                audio[:span] = rng.uniform(-0.01, 0.01, span)
        elif mode == 2:  # sustained speech-like
            span = int(n * float(rng.uniform(0.4, 1.0)))
            if span:
                audio[:span] = rng.uniform(-0.3, 0.3, span)
        else:  # transient click in mostly silence
            span = max(1, int(n * float(rng.uniform(0.001, 0.02))))
            audio[:span] = rng.uniform(0.4, 1.0, span)
        rms, _peak, silence_pct = _audio_stats(audio)
        expected = _raw_expected_proceed(rms, silence_pct, len(audio) / SR)
        result = _drive_gate(audio)
        if expected:
            if not result.pipeline.called:
                mismatches.append((duration_s, rms, silence_pct, "expected-proceed"))
        else:
            if result.pipeline.called:
                mismatches.append((duration_s, rms, silence_pct, "expected-discard"))
    elapsed = time.perf_counter() - started
    assert not mismatches, f"gate decisions diverged from rule table: {mismatches[:5]}"
    assert elapsed < 10.0, f"gate cost is not trivial: {elapsed:.2f}s for 220 clips"


class TestGateRuleHelpers:
    """Deliberate inclusive/exclusive boundaries, pinned."""

    def test_gate_threshold_values_are_pinned(self):
        """Product decision: 0.5s duration, 0.01 RMS floor, 95% silence
        ceiling. Changing any of these requires the docs + this pin updated."""
        assert MIN_DURATION_S == 0.5
        assert MIN_SHORT_RMS == 0.01
        assert MAX_SHORT_SILENCE_PCT == 95.0

    def test_rms_boundary_is_inclusive(self):
        assert _short_clip_has_speech_energy(MIN_SHORT_RMS, 0.0) is True
        assert _short_clip_has_speech_energy(MIN_SHORT_RMS - 1e-9, 0.0) is False

    def test_silence_boundary_is_exclusive(self):
        assert _short_clip_has_speech_energy(0.05, MAX_SHORT_SILENCE_PCT) is False
        assert _short_clip_has_speech_energy(0.05, MAX_SHORT_SILENCE_PCT - 0.1) is True
        assert _short_clip_has_speech_energy(0.05, 99.9) is False

    def test_missing_silence_falls_back_to_energy(self):
        assert _short_clip_has_speech_energy(0.05, None) is True
        assert _short_clip_has_speech_energy(0.009, None) is False

    def test_silence_pct_extraction_shapes(self):
        recorder = MagicMock()
        recorder._last_audio_stats = (0.05, 0.9, 12.5)
        assert _short_clip_silence_pct(recorder) == 12.5
        recorder._last_audio_stats = None
        assert _short_clip_silence_pct(recorder) is None
        recorder._last_audio_stats = (0.05, 0.9)
        assert _short_clip_silence_pct(recorder) is None
        recorder._last_audio_stats = ("a", "b", "c")
        assert _short_clip_silence_pct(recorder) is None
        assert _short_clip_silence_pct(MagicMock()) is None


class TestUnusableRmsIsDiscarded:
    """Unusable ``last_rms`` (mock/str/None/NaN) must discard, never crash.

    Pre-fix failures: MagicMock/str/None raised TypeError at the energy
    comparison (killing the stop worker); NaN failed open, because
    ``nan < MIN_SHORT_RMS`` is False."""

    @pytest.mark.parametrize(
        "garbage",
        [MagicMock(name="rms_mock"), "loud", None, float("nan")],
        ids=["magic_mock", "string", "none", "nan"],
    )
    def test_garbage_last_rms_discards_without_crashing(self, garbage):
        audio = _shape_audio("speech", 0.30, np.random.default_rng(11))
        result = _drive_gate(audio, last_rms=garbage)
        _assert_discarded(result)

    def test_numpy_float_rms_is_accepted(self):
        audio = _shape_audio("speech", 0.30, np.random.default_rng(12))
        rms, _peak, _silence = _audio_stats(audio)
        result = _drive_gate(audio, last_rms=np.float32(rms))
        _assert_proceeded(result, audio)

    def test_rms_helper_contract(self):
        recorder = MagicMock()
        assert _short_clip_rms(recorder) is None
        for garbage in ("loud", None, float("nan"), float("inf"), True):
            recorder.last_rms = garbage
            assert _short_clip_rms(recorder) is None
        recorder.last_rms = np.float32(0.25)
        assert _short_clip_rms(recorder) == pytest.approx(0.25)
        recorder.last_rms = 0.0
        assert _short_clip_rms(recorder) == 0.0
