"""The level meter / mic test must fail open when a chain eats the speech (A1).

The dictation pipeline has had this guard since the original microphone
failure; the meter ran the same chain with no comparison, so a starving chain
showed a dead bar and explained nothing. Same criterion, same constants here.
"""

from __future__ import annotations

import logging

import numpy as np
import pytest
from voice_typer.server.level_monitor import worker as worker_module
from voice_typer.server.level_monitor.divergence import (
    REASON_MONITOR_COLLAPSE,
    begin_session,
    observe_level_divergence,
)

RATE = 16_000
CHUNK = 512  # 32 ms at 16 kHz


def _voiced(amplitude: float = 0.25) -> np.ndarray:
    """A 150 Hz tone: voiced enough for the guard's pitch-strength cue."""
    t = np.arange(CHUNK) / RATE
    return (amplitude * np.sin(2 * np.pi * 150.0 * t)).astype(np.float32)


class _Starving:
    """Stands in for a chain that deletes everything."""

    def process_chunk(self, chunk):  # noqa: ANN001, ANN201 - test double
        return np.zeros_like(np.asarray(chunk), dtype=np.float32)


@pytest.fixture()
def monitor(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """An active monitor with a starving chain and the guard armed."""
    import voice_typer.server.level_monitor as lm
    from voice_typer.server import event_bus

    published: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", published.append)
    lm._monitor_active = True
    lm._monitor_sample_rate = RATE
    lm._test_mode = False
    lm._monitor_level = 0.0
    lm._monitor_peak = 0.0
    lm._level_guard = None
    lm._level_guard_tripped = False
    lm._level_processor_config = {"audio_preset": "auto", "noise_suppression_method": "dpdfnet"}
    yield published
    lm._monitor_active = False
    lm._level_processor = None
    lm._level_guard = None
    lm._level_guard_tripped = False


def _feed(chunks: int, signal: np.ndarray) -> None:
    for _ in range(chunks):
        worker_module._process_level_chunk(signal.copy(), None)


def test_a_starving_chain_trips_and_the_bar_returns_to_raw(monitor: list[dict]) -> None:
    import voice_typer.server.level_monitor as lm

    lm._level_processor = _Starving()
    begin_session()

    _feed(20, _voiced())

    assert lm._level_guard_tripped is True
    assert lm._level_processor is None, "the trip must fail open to the raw signal"
    assert lm._monitor_level > 0.05, "the bar must move again (raw RMS), not stay dead"
    assert [event["type"] for event in monitor] == ["filter_collapse"]
    assert monitor[0]["data"]["reason"] == REASON_MONITOR_COLLAPSE
    assert monitor[0]["data"]["preset"] == "auto"
    assert monitor[0]["data"]["delta_db"] > 25.0


def test_the_trip_is_reported_once_per_session(monitor: list[dict]) -> None:
    import voice_typer.server.level_monitor as lm

    lm._level_processor = _Starving()
    begin_session()

    _feed(40, _voiced())

    assert len(monitor) == 1, "one toast per session, not one per chunk"


def test_genuine_silence_never_trips(monitor: list[dict]) -> None:
    import voice_typer.server.level_monitor as lm

    lm._level_processor = _Starving()
    begin_session()

    _feed(30, np.zeros(CHUNK, dtype=np.float32))

    assert lm._level_guard_tripped is False
    assert lm._level_processor is not None
    assert monitor == []


def test_an_unarmed_guard_never_trips(monitor: list[dict]) -> None:
    """A guard is armed per session; nothing may trip before ``begin_session``."""
    import voice_typer.server.level_monitor as lm

    lm._level_processor = _Starving()

    _feed(30, _voiced())

    assert lm._level_guard_tripped is False
    assert lm._level_processor is not None
    assert monitor == []


def test_begin_session_rearms_a_tripped_guard(monitor: list[dict]) -> None:
    import voice_typer.server.level_monitor as lm

    lm._level_processor = _Starving()
    begin_session()
    _feed(20, _voiced())
    assert lm._level_guard_tripped is True

    begin_session()
    assert lm._level_guard_tripped is False


def test_the_warning_carries_both_levels_and_the_configuration(
    monitor: list[dict], caplog: pytest.LogCaptureFixture
) -> None:
    import voice_typer.server.level_monitor as lm

    lm._level_processor = _Starving()
    begin_session()

    with caplog.at_level(logging.WARNING):
        _feed(20, _voiced())

    line = next(record.getMessage() for record in caplog.records if "Filter divergence" in record.getMessage())
    assert "raw=" in line and "filtered=" in line
    assert "preset=auto" in line and "method=dpdfnet" in line


def test_observe_needs_a_raw_signal() -> None:
    begin_session()
    assert observe_level_divergence(np.zeros(0, dtype=np.float32), 0.0, RATE) is False
