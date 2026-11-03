"""Gate + preload behaviour of the DPDFNet noise-suppression backend."""

from __future__ import annotations

import logging
import time
import types
from typing import Any

import numpy as np
import pytest
from voice_typer.server.audio_filters import dpdfnet_backend

_WIN = 256
_HOP = 256
_RATE = 2048


class _SlowWarmupSession:
    """Fake ORT session whose first ``slow_calls`` runs are expensive."""

    def __init__(self, slow_calls: int, slow_s: float) -> None:
        self._slow_calls = slow_calls
        self._slow_s = slow_s
        self.calls = 0

    def run(self, output_names: list[str], feeds: dict[str, Any]) -> list[Any]:
        self.calls += 1
        if self.calls <= self._slow_calls:
            time.sleep(self._slow_s)
        spec = feeds["spec"]
        enhanced = np.zeros((1, 1, spec.shape[2], 2), dtype=np.float32)
        return [enhanced, feeds["state"]]


def _fake_runtime(session: Any) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        session=session,
        init_state=np.zeros(4, dtype=np.float32),
        in_spec_name="spec",
        in_state_name="state",
        out_spec_name="out_spec",
        out_state_name="out_state",
        win_len=_WIN,
        hop_size=_HOP,
        window=np.ones(_WIN, dtype=np.float32),
        model_sample_rate=_RATE,
        realtime_factor=0.0,
    )


def test_probe_excludes_warmup_windows_from_the_timing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cold session's first runs pay ORT spin-up and must not set the verdict."""
    monkeypatch.setattr(dpdfnet_backend, "_PROBE_SECONDS", 1.0)
    monkeypatch.setattr(dpdfnet_backend, "_PROBE_WARMUP_WINDOWS", 2)
    session = _SlowWarmupSession(slow_calls=2, slow_s=0.25)

    rtf = dpdfnet_backend._probe_realtime_factor(_fake_runtime(session))

    assert session.calls == 8
    assert rtf < 0.2, (
        f"charging the two slow warm-up windows to the model would report ~0.5 (got {rtf:.3f}); "
        "a real host measured 0.346 cold against ~0.10 warm"
    )


def test_rtf_verdict_logs_one_warning_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _refuse() -> None:
        raise dpdfnet_backend.RealtimeFactorError("dpdfnet real-time factor 0.346 exceeds the 0.30 ceiling")

    monkeypatch.setattr(dpdfnet_backend, "_get_runtime", _refuse)
    dpdfnet_backend._reset_for_tests()

    with caplog.at_level(logging.DEBUG, logger=dpdfnet_backend.log.name):
        assert dpdfnet_backend.preload() is False

    verdicts = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(verdicts) == 1
    assert verdicts[0].exc_info is None, "an expected RTF verdict is not an error traceback"
    assert "real-time factor 0.346" in verdicts[0].getMessage()
    assert not [r for r in caplog.records if "preload failed" in r.getMessage()]


def test_realtime_factor_ceiling_is_pinned() -> None:
    """0.3 is the shipped contract (docs/microphone-filter-failures.md).

    Raising it silently is how a slow host started claiming DPDFNet.
    """
    assert dpdfnet_backend.MAX_REALTIME_FACTOR == 0.3


def _scripted_probe(monkeypatch: pytest.MonkeyPatch, readings: list[float]) -> list[float]:
    """Replace the warm probe with a scripted sequence; return the call log."""
    pending = list(readings)
    seen: list[float] = []

    def _probe(_runtime: Any) -> float:
        value = pending.pop(0)
        seen.append(value)
        return value

    monkeypatch.setattr(dpdfnet_backend, "_probe_realtime_factor", _probe)
    return seen


def test_a_first_reading_under_the_ceiling_is_the_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """The common warm case pays ONE probe; extra readings would only add noise."""
    seen = _scripted_probe(monkeypatch, [0.09, 0.9, 0.9])

    rtf = dpdfnet_backend._warm_realtime_factor(_fake_runtime(None))

    assert rtf == pytest.approx(0.09)
    assert len(seen) == 1


def test_a_cold_first_reading_is_outvoted_by_the_median(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """One cold outlier must not disable the backend for the whole boot."""
    seen = _scripted_probe(monkeypatch, [0.42, 0.11, 0.12])

    with caplog.at_level(logging.INFO, logger=dpdfnet_backend.log.name):
        rtf = dpdfnet_backend._warm_realtime_factor(_fake_runtime(None))

    assert len(seen) == 3
    assert rtf == pytest.approx(0.12)
    lines = [r.getMessage() for r in caplog.records if "RTF probe readings" in r.getMessage()]
    assert lines and "0.42" in lines[0], "the discarded cold reading stays diagnosable"


def test_all_three_readings_over_the_ceiling_keep_every_number(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A genuinely slow host is refused, and the log names all three readings."""
    _scripted_probe(monkeypatch, [0.5, 0.62, 0.9])

    with (
        caplog.at_level(logging.INFO, logger=dpdfnet_backend.log.name),
        pytest.raises(dpdfnet_backend.RealtimeFactorError, match=r"0\.30 ceiling"),
    ):
        dpdfnet_backend._warm_realtime_factor(_fake_runtime(None))

    lines = [r.getMessage() for r in caplog.records if "RTF probe readings" in r.getMessage()]
    assert lines, "a refusal must still say what it measured"
    assert "0.62" in lines[0] and "0.9" in lines[0]


def test_unexpected_load_failure_keeps_its_traceback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _boom() -> None:
        raise RuntimeError("onnxruntime not importable")

    monkeypatch.setattr(dpdfnet_backend, "_get_runtime", _boom)

    with caplog.at_level(logging.DEBUG, logger=dpdfnet_backend.log.name):
        assert dpdfnet_backend.preload() is False

    failures = [r for r in caplog.records if "preload failed" in r.getMessage()]
    assert len(failures) == 1, "a genuine load failure must stay diagnosable"
    assert failures[0].exc_info is not None
