"""the cosmetic level bar."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _mock_sounddevice(monkeypatch):
    """Mock sounddevice so tests run on any platform without real"""
    holder = {"callback": None}

    class _Stream:
        def __init__(self, *args, **kwargs):
            holder["callback"] = kwargs.get("callback")

        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    import sounddevice as sd

    monkeypatch.setattr(sd, "InputStream", _Stream)
    monkeypatch.setattr(
        sd,
        "query_devices",
        lambda *a, **k: {
            "name": "Mock Mic",
            "default_samplerate": 16000,
            "max_input_channels": 1,
            "hostapi": 0,
        },
    )
    yield holder


class TestLightweightLevelBarMode:
    """The bar reads filtered audio by default; the raw path is an opt-out."""

    def test_filter_chain_skipped_when_opted_out_of_cosmetic_bar(self, _mock_sounddevice):
        """``_test_mode`` is False and the flag is opted out, the filter chain MUST NOT be invoked"""
        import voice_typer.server.level_monitor as lm

        processor = MagicMock()
        processor.process_chunk.side_effect = lambda x: x
        lm._level_processor = processor
        lm._level_processor_config = None
        # Explicit opt-out (legacy cosmetic-only raw meter)
        lm._level_bar_filtered = False
        # Not in test mode
        lm._test_mode = False

        lm.start_monitoring(mic_id=None)
        try:
            chunk = np.ones((512, 1), dtype=np.float32) * 0.25
            _mock_sounddevice["callback"](chunk, 512, None, None)

            # Wait for the worker to process.
            deadline = time.perf_counter() + 1.0
            while time.perf_counter() < deadline:
                if lm._monitor_level > 0:
                    break
                time.sleep(0.01)

            processor.process_chunk.assert_not_called()
            # The RMS should still be computed (on raw audio) so the bar
            assert lm._monitor_level > 0, (
                "even with the filter chain skipped, the cosmetic bar "
                "must still show a non-zero level (RMS computed on raw audio)"
            )
        finally:
            lm.stop_monitoring()

    def test_filter_chain_runs_when_level_bar_filtered_opted_in(self, _mock_sounddevice):
        """When ``_level_bar_filtered`` is True (user opted in), the"""
        import voice_typer.server.level_monitor as lm

        processor = MagicMock()
        processor.process_chunk.side_effect = lambda x: x
        lm._level_processor = processor
        lm._level_processor_config = None
        # Opt in to filtered bar
        lm._level_bar_filtered = True
        lm._test_mode = False

        lm.start_monitoring(mic_id=None)
        try:
            chunk = np.ones((512, 1), dtype=np.float32) * 0.25
            _mock_sounddevice["callback"](chunk, 512, None, None)

            # Wait for the worker to process.
            deadline = time.perf_counter() + 1.0
            while time.perf_counter() < deadline:
                if lm._monitor_level > 0:
                    break
                time.sleep(0.01)

            processor.process_chunk.assert_called()
        finally:
            lm.stop_monitoring()

    def test_filter_chain_runs_in_test_mode_regardless_of_flag(self, _mock_sounddevice):
        """When ``_test_mode`` is True, the filter chain runs EVEN IF"""
        import voice_typer.server.level_monitor as lm

        processor = MagicMock()
        processor.process_chunk.side_effect = lambda x: x
        lm._level_processor = processor
        lm._level_processor_config = None
        lm._level_bar_filtered = False
        # In test mode, filter chain must run regardless
        lm._test_mode = True

        lm.start_monitoring(mic_id=None)
        try:
            chunk = np.ones((512, 1), dtype=np.float32) * 0.25
            _mock_sounddevice["callback"](chunk, 512, None, None)

            # Wait for the worker to process.
            deadline = time.perf_counter() + 1.0
            while time.perf_counter() < deadline:
                if lm._monitor_level > 0:
                    break
                time.sleep(0.01)

            processor.process_chunk.assert_called()
        finally:
            # Reset test_mode + stop
            lm._test_mode = False
            lm.stop_monitoring()


class TestUpdateLevelProcessorPropagatesFlag:
    """``update_level_processor`` must propagate the"""

    def test_update_level_processor_sets_flag_true_by_default(self):
        """When ``level_bar_filtered`` is NOT in the config dict, the"""
        import voice_typer.server.level_monitor as lm

        # Reset to the OLD default so the flip is actually exercised
        lm._level_bar_filtered = False
        # Call update_level_processor with a config dict that doesn't
        lm.update_level_processor({"noise_filter_enabled": False})
        assert lm._level_bar_filtered is True, "update_level_processor must default _level_bar_filtered to True"

    def test_update_level_processor_sets_flag_false_when_opted_out(self):
        """When ``level_bar_filtered=False`` is explicitly in the config dict, the"""
        import voice_typer.server.level_monitor as lm

        lm.update_level_processor({"noise_filter_enabled": False, "level_bar_filtered": False})
        assert lm._level_bar_filtered is False, (
            "update_level_processor must set _level_bar_filtered=False when the config dict opts out"
        )

    def test_update_level_processor_sets_flag_true_when_opted_in(self):
        """When ``level_bar_filtered=True`` is in the config dict, the"""
        import voice_typer.server.level_monitor as lm

        lm.update_level_processor({"noise_filter_enabled": False, "level_bar_filtered": True})
        assert lm._level_bar_filtered is True, (
            "update_level_processor must set _level_bar_filtered=True when the config dict opts in"
        )

    def test_idle_bar_reads_filtered_after_update_with_filter_enabled(self, _mock_sounddevice, monkeypatch):
        """A filter-enabled config (no ``level_bar_filtered`` key) seeds the"""
        import voice_typer.server.audio_processor as ap
        import voice_typer.server.level_monitor as lm

        processor = MagicMock()
        processor.process_chunk.side_effect = lambda x: x * 0.5
        monkeypatch.setattr(ap, "AudioProcessor", lambda *a, **k: processor)
        lm.update_level_processor({"noise_filter_enabled": True, "noise_filter_highpass": True})
        assert lm._level_bar_filtered is True
        assert lm._level_processor is processor

        lm._level_processor_config = None
        lm.start_monitoring(mic_id=None)
        try:
            chunk = np.ones((512, 1), dtype=np.float32) * 0.25
            _mock_sounddevice["callback"](chunk, 512, None, None)
            deadline = time.perf_counter() + 1.0
            while time.perf_counter() < deadline:
                if lm._monitor_level > 0:
                    break
                time.sleep(0.01)
            processor.process_chunk.assert_called()
            # filtered RMS is half the raw 0.25 → ~0.125; raw would be ~0.25
            assert 0 < lm._monitor_level < 0.2, (
                f"level={lm._monitor_level} should reflect the FILTERED audio (~0.1), not the raw 0.25"
            )
        finally:
            lm.stop_monitoring()

    def test_raw_meter_when_filter_disabled(self, _mock_sounddevice):
        """``noise_filter_enabled=False`` clears the processor; even with the"""
        import voice_typer.server.level_monitor as lm

        lm.update_level_processor({"noise_filter_enabled": False})
        assert lm._level_processor is None
        assert lm._level_bar_filtered is True

        lm.start_monitoring(mic_id=None)
        try:
            chunk = np.ones((512, 1), dtype=np.float32) * 0.25
            _mock_sounddevice["callback"](chunk, 512, None, None)
            deadline = time.perf_counter() + 1.0
            while time.perf_counter() < deadline:
                if lm._monitor_level > 0:
                    break
                time.sleep(0.01)
            # processor is None → raw RMS 0.25 → EMA level ≈ 0.1;
            # a filtered processor (×0.5) would land ≈ 0.05
            assert lm._monitor_level > 0.07, (
                f"level={lm._monitor_level} should be raw RMS (processor=None bypass), not filtered"
            )
        finally:
            lm.stop_monitoring()

    def test_transition_preset_flip_changes_meter_source_mid_monitoring(self, _mock_sounddevice, monkeypatch):
        """Preset on → off mid-monitoring must switch the meter source"""
        import voice_typer.server.audio_processor as ap
        import voice_typer.server.level_monitor as lm

        processor = MagicMock()
        processor.process_chunk.side_effect = lambda x: x * 0.1
        monkeypatch.setattr(ap, "AudioProcessor", lambda *a, **k: processor)
        lm.update_level_processor({"noise_filter_enabled": True, "audio_preset": "noisy_room"})
        assert lm._level_processor is processor
        assert lm._level_bar_filtered is True

        lm._level_processor_config = None
        lm.start_monitoring(mic_id=None)
        try:
            chunk = np.ones((512, 1), dtype=np.float32) * 0.25
            _mock_sounddevice["callback"](chunk, 512, None, None)
            deadline = time.perf_counter() + 1.0
            while time.perf_counter() < deadline:
                if lm._monitor_level > 0:
                    break
                time.sleep(0.01)
            processor.process_chunk.assert_called()
            filtered_level = lm._monitor_level
            # filtered ×0.1 → RMS 0.025 → EMA ≈ 0.01
            assert filtered_level < 0.05

            # Flip preset off mid-monitoring: processor cleared, meter goes raw
            lm.update_level_processor({"noise_filter_enabled": False, "audio_preset": "off"})
            assert lm._level_processor is None

            calls_before = processor.process_chunk.call_count
            lm._monitor_level = 0.0
            _mock_sounddevice["callback"](chunk, 512, None, None)
            deadline = time.perf_counter() + 1.0
            while time.perf_counter() < deadline and lm._monitor_level == 0.0:
                time.sleep(0.01)
            assert processor.process_chunk.call_count == calls_before, (
                "after preset-off, the filter chain must not run again (processor cleared)"
            )
            # raw RMS 0.25 → EMA ≈ 0.1; filtered ×0.1 would be ≈ 0.01
            assert lm._monitor_level > 0.07, (
                f"level={lm._monitor_level} should be raw RMS after preset-off, not filtered"
            )
        finally:
            lm.stop_monitoring()

    def test_gate_closed_filtered_zeros_do_not_trip_disconnect(self, _mock_sounddevice):
        """With the bar filtered by default, a closed noise gate (exact-zero"""
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import worker as _w

        lm._monitor_active = True
        lm._test_mode = False
        lm._level_bar_filtered = True
        lm._consecutive_zero_chunks = 0
        lm._device_lost_emitted = False

        class _ClosedGate:
            def process_chunk(self, chunk, input_sample_rate=None):
                return np.zeros_like(chunk, dtype=np.float32)

        lm._level_processor = _ClosedGate()
        rng = np.random.default_rng(7)
        live_raw = (rng.standard_normal(1411).astype(np.float32) * 0.002)
        assert np.any(live_raw != 0.0)
        for _ in range(15):
            _w._process_level_chunk(live_raw.copy(), None)
        assert lm._consecutive_zero_chunks == 0, (
            "gate-closed filtered zeros over live raw must reset the counter, not increment"
        )

    def test_true_raw_zeros_still_trip_disconnect_when_bar_filtered(self, _mock_sounddevice):
        """Raw all-zero input must still trip the detector even when the"""
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import worker as _w

        lm._monitor_active = True
        lm._test_mode = False
        lm._level_bar_filtered = True
        lm._consecutive_zero_chunks = 0
        lm._device_lost_emitted = False

        class _PassThrough:
            def process_chunk(self, chunk, input_sample_rate=None):
                return chunk

        lm._level_processor = _PassThrough()
        dead = np.zeros(1411, dtype=np.float32)
        for _ in range(lm._LEVEL_ZERO_CHUNK_DISCONNECT_THRESHOLD + 2):
            _w._process_level_chunk(dead.copy(), None)
        assert lm._consecutive_zero_chunks >= lm._LEVEL_ZERO_CHUNK_DISCONNECT_THRESHOLD, (
            "raw all-zero input must still increment the zero-chunk counter"
        )


class TestMidTestToggleStitch:
    """Mid-test filter toggles must stitch a faithful Enhanced timeline.

    Regression for the user report: toggling the filter mid-test used to
    poison Play Enhanced (off→on = total silence, on→off = stale buffer +
    ghost Play Recording). The worker now captures EVERY test-mode chunk
    (filtered spans post-chain, off spans raw splice) and stop stitches
    instead of wholesale re-filtering with end-state config.
    """

    def test_chain_off_spans_splice_raw_into_filtered_chunks(self):
        """Chain-off chunks during a test land in _test_filtered_chunks as raw."""
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import worker as _w

        lm._monitor_active = True
        lm._test_mode = True
        lm._level_processor = None  # chain off
        lm._test_did_filter = False  # fresh timeline (cf. _reset_test_chunks)
        lm._test_raw_chunks.clear()
        lm._test_filtered_chunks.clear()
        lm._test_rms_history.clear()
        lm._test_peak_history.clear()

        chunk = (np.ones(1411, dtype=np.float32) * 0.25).copy()
        _w._process_level_chunk(chunk, None)

        assert len(lm._test_raw_chunks) == 1
        assert len(lm._test_filtered_chunks) == 1, (
            "chain-off test chunks must still be captured (raw splice) so the "
            "Enhanced stitch stays length-locked to the Original recording"
        )
        assert np.allclose(
            np.asarray(lm._test_filtered_chunks[0]).ravel(),
            np.asarray(lm._test_raw_chunks[0]).ravel(),
        )
        assert lm._test_did_filter is False, "no live-chain chunk ran yet"

    def test_toggle_off_on_off_stitches_audio_silence_audio(self):
        """Three spans (off/on/off) produce a 3-part Enhanced timeline."""
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import worker as _w

        lm._monitor_active = True
        lm._test_mode = True
        lm._test_did_filter = False  # fresh timeline (cf. _reset_test_chunks)
        lm._test_raw_chunks.clear()
        lm._test_filtered_chunks.clear()
        lm._test_rms_history.clear()
        lm._test_peak_history.clear()

        voice = (np.ones(1411, dtype=np.float32) * 0.25).copy()

        class _AggressiveGate:
            def process_chunk(self, chunk, input_sample_rate=None):
                return np.zeros_like(chunk, dtype=np.float32)

        # Span 1: chain OFF → raw splice (audible).
        lm._level_processor = None
        _w._process_level_chunk(voice.copy(), None)
        # Span 2: chain ON (aggressive) → filtered silence.
        lm._level_processor = _AggressiveGate()
        _w._process_level_chunk(voice.copy(), None)
        # Span 3: chain OFF again → raw splice (audible).
        lm._level_processor = None
        _w._process_level_chunk(voice.copy(), None)

        assert len(lm._test_filtered_chunks) == 3
        assert len(lm._test_raw_chunks) == 3
        first = np.asarray(lm._test_filtered_chunks[0]).ravel()
        second = np.asarray(lm._test_filtered_chunks[1]).ravel()
        third = np.asarray(lm._test_filtered_chunks[2]).ravel()
        assert np.abs(first).mean() > 0.1, "off-span must stay audible"
        assert np.abs(second).max() == 0.0, "on-span (aggressive) must be silence"
        assert np.abs(third).mean() > 0.1, "second off-span must stay audible"
        assert lm._test_did_filter is True, "one live-chain chunk ran"

    def test_never_filtered_test_leaves_did_filter_false(self):
        """All-off test: post-hoc path stays valid, did_filter stays False."""
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import worker as _w

        lm._monitor_active = True
        lm._test_mode = True
        lm._level_processor = None
        lm._test_did_filter = False
        lm._test_raw_chunks.clear()
        lm._test_filtered_chunks.clear()
        lm._test_rms_history.clear()
        lm._test_peak_history.clear()

        chunk = (np.ones(1411, dtype=np.float32) * 0.25).copy()
        _w._process_level_chunk(chunk, None)
        _w._process_level_chunk(chunk, None)

        assert lm._test_did_filter is False
        assert len(lm._test_filtered_chunks) == 2
