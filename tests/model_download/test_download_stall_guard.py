"""Stall/max-duration guards must abort the transfer thread, never orphan it."""

import inspect
import logging

import pytest
from voice_typer.server.service import _download_helpers as helpers

_MODEL = "large-v3-turbo"
_REPO_ID = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
_MODEL_BYTES = 2 * 1024 * 1024


class _Clock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _FakeTime:
    """Module-local time stand-in so no test waits on the real clock."""

    def __init__(self, clock: _Clock) -> None:
        self.monotonic = clock


class _FakeThread:
    """Thread stand-in: alive until the abort join, joins recorded in order."""

    def __init__(self, trace: list[str], *, alive_after_abort_join: bool = False) -> None:
        self._trace = trace
        self._alive_after_abort_join = alive_after_abort_join
        self._abort_joined = False
        self.joins: list[float | None] = []

    def is_alive(self) -> bool:
        return self._alive_after_abort_join if self._abort_joined else True

    def join(self, timeout=None) -> None:
        self.joins.append(timeout)
        self._trace.append("join")
        if timeout == helpers.DOWNLOAD_ABORT_JOIN_S:
            self._abort_joined = True


class _RecordingBus:
    def __init__(self, clock: _Clock | None = None, advance_s: float = 0.0) -> None:
        self.events: list[dict] = []
        self._clock = clock
        self._advance_s = advance_s

    def publish(self, message) -> None:
        self.events.append(message)
        # Progress pushed after a byte change means time moved on: this is how
        # the guards are reached without sleeping.
        if self._clock is not None:
            self._clock.advance(self._advance_s)


@pytest.fixture(autouse=True)
def _idle_transfer_gate():
    from voice_typer.server import asr_setup

    asr_setup.clear_download_pause_state()
    yield
    asr_setup.clear_download_pause_state()


@pytest.fixture()
def trace() -> list[str]:
    """Shared ordering log for gate signals and thread joins."""
    return []


@pytest.fixture()
def abort_calls(monkeypatch, trace):
    from voice_typer.server import asr_setup

    calls: list[str] = []

    def fake_abort() -> bool:
        calls.append("abort")
        trace.append("abort")
        return True

    monkeypatch.setattr(asr_setup, "request_download_abort", fake_abort)
    return calls


def _seed_cache(cache_dir):
    model_dir = cache_dir / f"models--{_REPO_ID.replace('/', '--')}"
    model_dir.mkdir(parents=True)
    with (model_dir / "model.bin").open("wb") as handle:
        handle.truncate(_MODEL_BYTES)


def _run_poll(thread, cache_dir, bus, *, max_stall_s=helpers.DOWNLOAD_STALL_TIMEOUT_S, max_duration_s=1800.0):
    return helpers.poll_download_progress(
        thread=thread,
        target_bytes=_MODEL_BYTES,
        target_mb=2,
        model_name=_MODEL,
        repo_id=_REPO_ID,
        cache_dir=cache_dir,
        download_id="download-1",
        event_bus=bus,
        is_cancelled_fn=lambda _download_id: False,
        max_duration_s=max_duration_s,
        max_stall_s=max_stall_s,
    )


class TestStallGuardAbortsTransfer:
    def test_stall_signals_gate_joins_then_raises(self, tmp_path, monkeypatch, abort_calls, trace):
        _seed_cache(tmp_path)
        clock = _Clock()
        monkeypatch.setattr(helpers, "time", _FakeTime(clock))
        thread = _FakeThread(trace)
        # One poll iteration records the 2 MiB, then the clock jumps past the
        # stall limit on the next iteration.
        bus = _RecordingBus(clock, advance_s=helpers.DOWNLOAD_STALL_TIMEOUT_S + 1.0)

        with pytest.raises(TimeoutError) as excinfo:
            _run_poll(thread, tmp_path, bus)

        assert abort_calls == ["abort"], "a stalled poll must signal the transfer gate"
        assert thread.joins[-1] == helpers.DOWNLOAD_ABORT_JOIN_S, "the poller must join the transfer thread"
        assert trace[-2:] == ["abort", "join"], "signal the gate BEFORE joining"
        message = str(excinfo.value)
        assert _MODEL in message
        assert str(_MODEL_BYTES) in message, f"byte count missing from: {message}"
        assert "stalled" in message

    def test_max_duration_signals_gate_joins_then_raises(self, tmp_path, monkeypatch, abort_calls, trace):
        _seed_cache(tmp_path)
        clock = _Clock()
        monkeypatch.setattr(helpers, "time", _FakeTime(clock))
        thread = _FakeThread(trace)
        bus = _RecordingBus(clock, advance_s=1801.0)

        with pytest.raises(TimeoutError) as excinfo:
            _run_poll(thread, tmp_path, bus, max_duration_s=1800.0)

        assert abort_calls == ["abort"]
        assert thread.joins[-1] == helpers.DOWNLOAD_ABORT_JOIN_S
        assert trace[-2:] == ["abort", "join"]
        message = str(excinfo.value)
        assert _MODEL in message
        assert str(_MODEL_BYTES) in message
        assert "exceeded max duration" in message

    def test_still_alive_thread_after_join_warns_and_still_raises(
        self, tmp_path, monkeypatch, abort_calls, trace, caplog
    ):
        clock = _Clock()
        monkeypatch.setattr(helpers, "time", _FakeTime(clock))
        thread = _FakeThread(trace, alive_after_abort_join=True)
        bus = _RecordingBus(clock)

        with caplog.at_level(logging.WARNING, logger=helpers.__name__), pytest.raises(TimeoutError):
            _run_poll(thread, tmp_path, bus, max_stall_s=-1.0)

        assert abort_calls == ["abort"]
        assert "still running after" in caplog.text
        assert _MODEL in caplog.text


class TestGuardDefaults:
    def test_stall_timeout_default_covers_hf_retry_backoff(self):
        assert helpers.DOWNLOAD_STALL_TIMEOUT_S >= 120, "60 s aborted transfers still inside HF retry backoff"
        default = inspect.signature(helpers.poll_download_progress).parameters["max_stall_s"].default
        assert default == helpers.DOWNLOAD_STALL_TIMEOUT_S
        assert helpers.DOWNLOAD_ABORT_JOIN_S > 0


class TestCancelPathUnchanged:
    def test_cancel_returns_cancelled_without_aborting_gate(self, tmp_path, monkeypatch, abort_calls):
        clock = _Clock()
        monkeypatch.setattr(helpers, "time", _FakeTime(clock))
        trace: list[str] = []
        thread = _FakeThread(trace)
        bus = _RecordingBus(clock)

        outcome = helpers.poll_download_progress(
            thread=thread,
            target_bytes=_MODEL_BYTES,
            target_mb=2,
            model_name=_MODEL,
            repo_id=_REPO_ID,
            cache_dir=tmp_path,
            download_id="download-1",
            event_bus=bus,
            is_cancelled_fn=lambda _download_id: True,
        )

        assert outcome == ("cancelled", 0)
        assert abort_calls == [], "user cancel is signalled by the cancel path, not the poller"
        assert helpers.DOWNLOAD_ABORT_JOIN_S not in thread.joins
