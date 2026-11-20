"""The shared STT-plugin level meter forwards measured mic levels.

A browser-owned recording sends no PCM to the bubble, so the pill used to be
fed one constant level and rendered a frozen waveform. The meter opens a
meter-only capture and pushes real RMS/peak into the app's waveform
coordinator; an unavailable device degrades to rest with one warning.
"""

from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from tools.internal_plugins._common import level_meter

_LOGGER = "voice_typer.internal_plugin.level_meter"


class TestMeasuredLevels:
    def test_levels_track_the_samples_not_a_constant(self) -> None:
        quiet = level_meter.compute_levels(np.zeros(800, dtype="float32"))
        loud = level_meter.compute_levels(np.full(800, 0.5, dtype="float32"))

        assert quiet == pytest.approx((0.0, 0.0))
        assert loud == pytest.approx((0.5, 0.5))
        assert loud != quiet, "levels must come from the audio, not a hardcoded pair"

    def test_meter_forwards_measured_levels_to_the_bubble(self, monkeypatch: pytest.MonkeyPatch) -> None:
        updates: list[tuple[float, float]] = []
        app = SimpleNamespace(
            config=SimpleNamespace(microphone=None),
            _waveform_bubble=SimpleNamespace(update_level=lambda r, p: updates.append((r, p))),
        )
        monkeypatch.setattr(level_meter, "_meter_device", lambda a: None)

        class FakeInputStream:
            def __init__(self, **kwargs: object) -> None:
                self.kwargs = kwargs

            def start(self) -> None:
                pass

            def read(self, block: int):
                meter._stop.set()
                return np.full((block, 1), 0.25, dtype="float32"), False

            def stop(self) -> None:
                pass

            def close(self) -> None:
                pass

        monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(InputStream=FakeInputStream))
        meter = level_meter.LevelMeter(app)
        meter.start()
        assert meter._thread is not None
        meter._thread.join(timeout=5.0)

        assert not meter._thread.is_alive(), "the meter must stop when asked"
        assert len(updates) >= 1, "a captured block must reach the bubble"
        assert updates[0] == pytest.approx((0.25, 0.25))

    def test_unavailable_device_warns_once_and_stays_at_rest(self, monkeypatch: pytest.MonkeyPatch, caplog) -> None:
        app = SimpleNamespace(
            config=SimpleNamespace(microphone=None),
            _waveform_bubble=SimpleNamespace(update_level=lambda r, p: pytest.fail("no fake levels")),
        )
        monkeypatch.setattr(level_meter, "_meter_device", lambda a: None)

        class RefusingStream:
            def __init__(self, **kwargs: object) -> None:
                raise RuntimeError("device busy")

        monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(InputStream=RefusingStream))
        meter = level_meter.LevelMeter(app)
        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            meter._run()

        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 1, "one warning, never a per-frame flood"
        assert "stays at rest" in warnings[0].getMessage()
