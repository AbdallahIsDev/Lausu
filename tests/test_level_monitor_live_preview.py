"""Live-listen preview stream (backend-streamed Listen Live).

The preview must be the level monitor's OWN ``AudioProcessor`` chain (E7 /
C-MIC-10): the level worker already holds the post-chain buffer, so a preview
frame is a copy of that buffer. These tests pin:

* the honest ``live_preview`` reply (no monitor -> ``active: False``),
* the wire shape (base64 PCM16 LE mono + a monotonic ``seq``),
* the off switch (nothing published while the preview is off),
* lifecycle clearing (``clear_live_preview`` / ``stop_monitoring``) and the
  idle-timeout hold.
"""

from __future__ import annotations

import base64

import numpy as np
import pytest


def _reset_level_monitor_state() -> None:
    """Delegate: one canonical reset (see tests/fixtures/level_monitor_state.py)."""
    from tests.fixtures.level_monitor_state import reset_level_monitor_state

    reset_level_monitor_state()


@pytest.fixture(autouse=True)
def _clean_state():
    _reset_level_monitor_state()
    yield
    _reset_level_monitor_state()


@pytest.fixture
def published(monkeypatch):
    """Capture every ``event_bus.publish`` payload instead of shipping it."""
    from voice_typer.server import event_bus

    frames: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", frames.append)
    return frames


def _decode(payload: dict) -> np.ndarray:
    raw = base64.b64decode(payload["pcm"])
    return np.frombuffer(raw, dtype="<i2")


class TestEnable:
    """``set_live_preview_enabled`` must answer with the REAL state."""

    def test_enable_without_monitor_reports_unavailable(self):
        """No monitor stream -> no capture path -> honest ``active: False``."""
        from voice_typer.server.level_monitor import (
            is_live_preview_active,
            set_live_preview_enabled,
        )

        result = set_live_preview_enabled(True)

        assert result == {
            "active": False,
            "monitoring": False,
            "sample_rate": 16000,
            "filtered": False,
        }
        assert is_live_preview_active() is False

    def test_enable_with_monitor_and_processor_activates(self):
        """A live monitor + processor -> the stream is genuinely on."""
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import (
            is_live_preview_active,
            set_live_preview_enabled,
        )

        lm._monitor_active = True
        lm._monitor_sample_rate = 48000
        lm._level_processor = object()

        result = set_live_preview_enabled(True)

        assert result["active"] is True
        assert result["monitoring"] is True
        assert result["sample_rate"] == 48000
        assert result["filtered"] is True
        assert is_live_preview_active() is True

    def test_disable_always_reports_inactive(self):
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import set_live_preview_enabled

        lm._monitor_active = True
        lm._level_processor = object()
        set_live_preview_enabled(True)

        result = set_live_preview_enabled(False)

        assert result["active"] is False
        # The monitor keeps running: turning the preview off is not a stop.
        assert result["monitoring"] is True


class TestFrames:
    """Wire shape of one preview frame."""

    def _activate(self) -> None:
        import voice_typer.server.level_monitor as lm

        lm._monitor_active = True
        lm._monitor_sample_rate = 16000
        lm._level_processor = object()
        from voice_typer.server.level_monitor import set_live_preview_enabled

        set_live_preview_enabled(True)

    def test_frame_is_base64_pcm16_le_mono(self, published):
        from voice_typer.server.level_monitor import publish_preview_frame

        self._activate()
        samples = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)

        publish_preview_frame(samples, 16000)

        assert len(published) == 1
        event = published[0]
        assert event["type"] == "live_preview_audio"
        data = event["data"]
        assert data["sample_rate"] == 16000
        assert data["seq"] == 1
        decoded = _decode(data)
        assert decoded.size == samples.size
        # PCM16 round-trip within one LSB of the float samples.
        assert np.allclose(decoded.astype(np.float32) / 32767.0, samples, atol=1e-4)

    def test_out_of_range_samples_are_clipped_not_wrapped(self, published):
        """A clipped sample must saturate, never wrap to the opposite sign."""
        from voice_typer.server.level_monitor import publish_preview_frame

        self._activate()
        publish_preview_frame(
            np.array([2.0, -2.0], dtype=np.float32),
            16000,
        )

        decoded = _decode(published[0]["data"])
        assert decoded[0] == 32767
        assert decoded[1] == -32767

    def test_seq_is_monotonic_across_frames(self, published):
        from voice_typer.server.level_monitor import publish_preview_frame

        self._activate()
        for _ in range(3):
            publish_preview_frame(np.zeros(64, dtype=np.float32), 16000)

        assert [frame["data"]["seq"] for frame in published] == [1, 2, 3]

    def test_gated_silence_is_still_published(self, published):
        """An aggressive gate yields exact zeros, and zeros are the point."""
        from voice_typer.server.level_monitor import publish_preview_frame

        self._activate()
        publish_preview_frame(np.zeros(128, dtype=np.float32), 16000)

        assert len(published) == 1
        decoded = _decode(published[0]["data"])
        assert decoded.size == 128
        assert not decoded.any()

    def test_nothing_is_published_while_preview_is_off(self, published):
        from voice_typer.server.level_monitor import publish_preview_frame

        publish_preview_frame(np.ones(64, dtype=np.float32) * 0.1, 16000)

        assert published == []

    def test_empty_chunk_is_never_published(self, published):
        from voice_typer.server.level_monitor import publish_preview_frame

        self._activate()
        publish_preview_frame(np.zeros(0, dtype=np.float32), 16000)

        assert published == []


class TestLifecycle:
    """Stopping the preview or the monitor must release the stream."""

    def _activate(self) -> None:
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import set_live_preview_enabled

        lm._monitor_active = True
        lm._monitor_sample_rate = 16000
        lm._level_processor = object()
        set_live_preview_enabled(True)

    def test_clear_stops_frames_and_resets_seq(self, published):
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import (
            clear_live_preview,
            is_live_preview_active,
            publish_preview_frame,
            set_live_preview_enabled,
        )

        self._activate()
        publish_preview_frame(np.zeros(32, dtype=np.float32), 16000)
        assert len(published) == 1

        clear_live_preview()

        assert is_live_preview_active() is False
        publish_preview_frame(np.zeros(32, dtype=np.float32), 16000)
        assert len(published) == 1
        # A fresh enable restarts the sequence at 1.
        set_live_preview_enabled(True)
        publish_preview_frame(np.zeros(32, dtype=np.float32), 16000)
        assert published[-1]["data"]["seq"] == 1
        assert lm._live_preview_seq == 1

    def test_stop_monitoring_clears_the_preview(self, monkeypatch):
        """A monitor stop has no capture path left, so the preview dies with it."""
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor import (
            is_live_preview_active,
            stop_monitoring,
        )

        self._activate()
        # The stop path touches PortAudio teardown; stub the worker joins so
        # this stays a state-machine test.
        monkeypatch.setattr(
            "voice_typer.server.level_monitor.worker._stop_level_worker",
            lambda *a, **k: None,
        )

        stop_monitoring()

        assert is_live_preview_active() is False
        assert lm._live_preview_seq == 0

    def test_idle_timeout_never_stops_the_mic_under_an_active_preview(self, monkeypatch):
        """An active preview holds the mic exactly like an active test does."""
        import voice_typer.server.level_monitor as lm
        from voice_typer.server.level_monitor._state import _state as lm_state
        from voice_typer.server.level_monitor.monitoring import (
            _idle_timeout_auto_stop,
        )

        self._activate()
        # Make the idle timeout look long expired.
        monkeypatch.setattr(lm_state, "_LEVEL_IDLE_TIMEOUT_SEC", 1.0)
        lm._last_get_level_poll_ts = 1.0

        assert _idle_timeout_auto_stop() is False
        assert lm._monitor_active is True


class TestWorkerIntegration:
    """The preview rides the level worker's post-chain buffer (E7)."""

    class _HalvingProcessor:
        """Stands in for the real chain: any filter would change the frame."""

        def process_chunk(self, chunk):
            return chunk * 0.5

    def _drive(self, monkeypatch, *, filtered: bool):
        import voice_typer.server.level_monitor as lm
        from voice_typer.server import event_bus
        from voice_typer.server.level_monitor import set_live_preview_enabled
        from voice_typer.server.level_monitor.worker import _process_level_chunk

        frames: list[dict] = []
        monkeypatch.setattr(event_bus, "publish", frames.append)

        lm._monitor_active = True
        lm._monitor_sample_rate = 16000
        lm._level_processor = self._HalvingProcessor()
        lm._level_bar_filtered = filtered
        set_live_preview_enabled(True)

        _process_level_chunk(np.full((4, 1), 0.8, dtype=np.float32), None)
        return frames

    def test_frame_is_the_processor_output_not_the_raw_chunk(self, monkeypatch):
        """Chain pin: the preview is what the user's preset produced."""
        frames = self._drive(monkeypatch, filtered=True)

        assert len(frames) == 1
        decoded = _decode(frames[0]["data"]).astype(np.float32) / 32767.0
        assert np.allclose(decoded, 0.4, atol=1e-3)

    def test_frame_is_raw_when_filtering_is_off(self, monkeypatch):
        """Filtering OFF -> the preview is the raw capture, like the meter."""
        frames = self._drive(monkeypatch, filtered=False)

        assert len(frames) == 1
        decoded = _decode(frames[0]["data"]).astype(np.float32) / 32767.0
        assert np.allclose(decoded, 0.8, atol=1e-3)

    def test_no_frame_is_published_before_the_preview_is_enabled(self, monkeypatch):
        import voice_typer.server.level_monitor as lm
        from voice_typer.server import event_bus
        from voice_typer.server.level_monitor.worker import _process_level_chunk

        frames: list[dict] = []
        monkeypatch.setattr(event_bus, "publish", frames.append)

        lm._monitor_active = True
        lm._monitor_sample_rate = 16000
        lm._level_processor = self._HalvingProcessor()
        lm._level_bar_filtered = True

        _process_level_chunk(np.full((4, 1), 0.8, dtype=np.float32), None)

        assert frames == []

    def test_a_processor_rebuild_mid_preview_keeps_streaming(self, monkeypatch):
        """A preset change rebuilds the chain; the preview never restarts."""
        import voice_typer.server.level_monitor as lm
        from voice_typer.server import event_bus
        from voice_typer.server.level_monitor import (
            is_live_preview_active,
            set_live_preview_enabled,
        )
        from voice_typer.server.level_monitor.monitoring_queries import (
            update_level_processor,
        )
        from voice_typer.server.level_monitor.worker import _process_level_chunk

        frames: list[dict] = []
        monkeypatch.setattr(event_bus, "publish", frames.append)

        lm._monitor_active = True
        lm._monitor_sample_rate = 16000
        lm._level_processor = self._HalvingProcessor()
        lm._level_bar_filtered = True
        set_live_preview_enabled(True)

        _process_level_chunk(np.full((4, 1), 0.8, dtype=np.float32), None)

        # The config applier swaps the processor in place (set_config path).
        update_level_processor({"noise_filter_enabled": False})

        assert is_live_preview_active() is True
        _process_level_chunk(np.full((4, 1), 0.8, dtype=np.float32), None)

        assert [frame["data"]["seq"] for frame in frames] == [1, 2]
        # Filtering is now OFF, so the second frame is the raw chunk again.
        decoded = _decode(frames[1]["data"]).astype(np.float32) / 32767.0
        assert np.allclose(decoded, 0.8, atol=1e-3)
