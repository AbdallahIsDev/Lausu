"""Unit tests for :class:`MicVolumeGuard` (S5 mic guard).

The guard is the piece that keeps the OS capture knob at 100%. These tests
pin the three behaviours the plan calls out by name:

* a restore writes the REAL device value (not a bookkeeping flag),
* the anti-flap budget bounds the guard's OWN restores and then goes
  notify-only,
* the user-pressed write (``[Back to 100%]``) is never budgeted.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest
from voice_typer.server.mic_volume_guard import (
    DEFAULT_MIC_GUARD_POLL_MS,
    MIC_GUARD_ANTIFLAP_MAX_RESTORES,
    MIC_GUARD_ANTIFLAP_WINDOW_S,
    MIC_GUARD_TARGET_LEVEL,
    MicVolumeGuard,
)


class FakeMicBackend:
    """Minimal ``MicVolumeBackend`` stand-in with a settable knob."""

    def __init__(self, level: float = 1.0, *, supports_set: bool = True) -> None:
        self._level = level
        self._supports_set = supports_set
        self.writes: list[float] = []
        self.read_raises: Exception | None = None

    @property
    def name(self) -> str:
        return "fake (capture)"

    @property
    def supports_set(self) -> bool:
        return self._supports_set

    def initialize(self) -> bool:
        return True

    def get_level(self) -> float | None:
        if self.read_raises is not None:
            raise self.read_raises
        return self._level

    def set_level(self, level: float) -> bool:
        if not self._supports_set:
            return False
        self.writes.append(level)
        self._level = level
        return True


def _guard(backend: FakeMicBackend, **kwargs) -> MicVolumeGuard:
    guard = MicVolumeGuard(backend=backend, **kwargs)
    assert guard.initialize() is True
    return guard


class TestRestoreWritesTheRealDeviceValue:
    def test_lowered_knob_is_written_back_to_the_target(self) -> None:
        backend = FakeMicBackend(level=0.92)
        guard = _guard(backend)

        guard.poll_once()

        assert backend.writes == [MIC_GUARD_TARGET_LEVEL], (
            "the guard must write the REAL device value (1.0), not just flip a flag."
        )
        assert backend.get_level() == 1.0

    def test_a_knob_already_at_target_is_not_written(self) -> None:
        backend = FakeMicBackend(level=1.0)
        guard = _guard(backend)

        guard.poll_once()

        assert backend.writes == []

    def test_tolerance_absorbs_float_noise_but_not_a_real_step(self) -> None:
        # 0.996 is within the 0.005 tolerance of 1.0 → no write.
        backend = FakeMicBackend(level=0.996)
        guard = _guard(backend)
        guard.poll_once()
        assert backend.writes == []

        # 0.99 is a real (1%) device step → written.
        backend2 = FakeMicBackend(level=0.99)
        guard2 = _guard(backend2)
        guard2.poll_once()
        assert backend2.writes == [MIC_GUARD_TARGET_LEVEL]


class TestReportsOnlyOnChange:
    def test_a_parked_knob_reports_once(self) -> None:
        """A driver that keeps the knob at 92% must not re-report every 2s."""
        backend = FakeMicBackend(level=0.92)
        reports: list[tuple[float, bool]] = []
        guard = _guard(backend, on_lowered=lambda level, restored: reports.append((level, restored)))

        guard.poll_once()
        guard.poll_once()
        guard.poll_once()

        assert len(reports) == 1, f"expected one deduped report, got {reports}"

    def test_a_new_level_reports_again(self) -> None:
        backend = FakeMicBackend(level=0.92)
        reports: list[tuple[float, bool]] = []
        guard = _guard(backend, on_lowered=lambda level, restored: reports.append((level, restored)))

        guard.poll_once()
        backend._level = 0.88
        guard.poll_once()

        assert len(reports) == 2

    def test_a_cleared_message_must_not_mask_the_next_drop(self) -> None:
        """Notify-only drop → the user clicks Back to 100% (clearing the
        sticky note) → the driver clamps the SAME value again: they must be
        told a second time, or the knob sits at 92% with nothing on screen."""
        backend = FakeMicBackend(level=0.92)
        reports: list[tuple[float, bool]] = []
        guard = _guard(backend, on_lowered=lambda level, restored: reports.append((level, restored)))

        # Three automatic restores exhaust the budget, then go notify-only.
        for _ in range(MIC_GUARD_ANTIFLAP_MAX_RESTORES):
            guard.poll_once()
            backend._level = 0.92
        guard.poll_once()
        assert reports[-1] == (0.92, False), f"expected notify-only, got {reports}"

        # The user presses [Back to 100%] and the knob really moves back.
        assert guard.set_level(1.0) is True
        guard.poll_once()

        # The driver clamps to the same 92% while the budget is still spent.
        backend._level = 0.92
        guard.poll_once()

        assert len(reports) == 3, (
            "the second drop at 92% is a new episode: clearing the toast must "
            f"not dedupe it away, got {reports}"
        )


class TestAntiFlapBudget:
    def test_budget_bounds_automatic_restores_then_goes_notify_only(self) -> None:
        backend = FakeMicBackend(level=0.5)
        reports: list[tuple[float, bool]] = []
        guard = _guard(backend, on_lowered=lambda level, restored: reports.append((level, restored)))

        # A driver that re-clamps after every restore. Each cycle uses a
        # slightly different level so the dedupe does not mask the budget.
        for i in range(MIC_GUARD_ANTIFLAP_MAX_RESTORES + 3):
            backend._level = 0.5 + i * 0.01
            guard.poll_once()

        assert len(backend.writes) == MIC_GUARD_ANTIFLAP_MAX_RESTORES, (
            "the automatic restore must stop after the anti-flap budget, "
            "otherwise a stubborn driver becomes a tug-of-war."
        )
        assert reports[-1][1] is False, "past the budget the report must say restored=False (notify-only)"
        assert len(reports) == MIC_GUARD_ANTIFLAP_MAX_RESTORES + 3

    def test_budget_refills_after_the_window(self, monkeypatch) -> None:
        backend = FakeMicBackend(level=0.5)
        guard = _guard(backend)
        for i in range(MIC_GUARD_ANTIFLAP_MAX_RESTORES):
            backend._level = 0.5 + i * 0.01
            guard.poll_once()
        assert len(backend.writes) == MIC_GUARD_ANTIFLAP_MAX_RESTORES

        # Age the restore timestamps past the window.
        now = time.monotonic()
        guard._restores = type(guard._restores)(
            t - MIC_GUARD_ANTIFLAP_WINDOW_S - 1.0 for t in guard._restores
        )
        backend._level = 0.7
        guard.poll_once()

        assert len(backend.writes) == MIC_GUARD_ANTIFLAP_MAX_RESTORES + 1, (
            "the budget must refill once the window has passed."
        )
        assert now > 0

    def test_the_users_own_write_is_never_budgeted(self) -> None:
        backend = FakeMicBackend(level=0.5)
        guard = _guard(backend)
        # Burn the whole budget.
        for i in range(MIC_GUARD_ANTIFLAP_MAX_RESTORES):
            backend._level = 0.5 + i * 0.01
            guard.poll_once()
        assert guard._budget_available() is False

        assert guard.restore_to_full() is True
        assert backend.get_level() == MIC_GUARD_TARGET_LEVEL, (
            "the explicit [Back to 100%] press must always write, even with the budget exhausted."
        )


class TestDeviceWithoutSettableGain:
    def test_no_write_and_the_report_says_not_restored(self) -> None:
        """macOS built-in mics: message-only, never a fake button."""
        backend = FakeMicBackend(level=0.6, supports_set=False)
        reports: list[tuple[float, bool]] = []
        guard = _guard(backend, on_lowered=lambda level, restored: reports.append((level, restored)))

        guard.poll_once()

        assert backend.writes == []
        assert reports == [(0.6, False)]
        assert guard.supports_set is False

    def test_restore_to_full_is_a_no_op_and_reports_failure(self) -> None:
        backend = FakeMicBackend(level=0.6, supports_set=False)
        guard = _guard(backend)
        assert guard.restore_to_full() is False
        assert backend.writes == []


class TestEnabledToggle:
    def test_disabled_guard_does_nothing(self) -> None:
        backend = FakeMicBackend(level=0.5)
        guard = _guard(backend, enabled=lambda: False)

        guard.poll_once()

        assert backend.writes == []
        assert backend.get_level() == 0.5

    def test_toggle_is_read_live_not_snapshotted(self) -> None:
        """``set_config('mic_guard_enabled')`` must take effect without a restart."""
        backend = FakeMicBackend(level=0.5)
        flag = {"on": False}
        guard = _guard(backend, enabled=lambda: flag["on"])

        guard.poll_once()
        assert backend.writes == []

        flag["on"] = True
        guard.poll_once()
        assert backend.writes == [MIC_GUARD_TARGET_LEVEL]


class TestReadFailures:
    def test_read_failure_is_swallowed_and_warns_after_n(self, caplog) -> None:
        backend = FakeMicBackend(level=1.0)
        backend.read_raises = RuntimeError("device gone")
        guard = _guard(backend)

        with caplog.at_level("WARNING", logger="voice_typer.server.mic_volume_guard"):
            for _ in range(3):
                guard.poll_once()

        assert any("capture level read failed" in r.message for r in caplog.records), (
            "the guard owns the warn-after-N policy so the platform backends can stay DEBUG-only."
        )

    def test_error_counter_resets_on_a_successful_read(self) -> None:
        backend = FakeMicBackend(level=1.0)
        backend.read_raises = RuntimeError("transient")
        guard = _guard(backend)
        guard.poll_once()
        assert guard._consecutive_errors == 1

        backend.read_raises = None
        guard.poll_once()
        assert guard._consecutive_errors == 0


class TestLifecycle:
    def test_backend_failure_disables_the_guard(self) -> None:
        backend = MagicMock()
        backend.initialize.return_value = False
        backend.name = "fake"
        backend.supports_set = True
        guard = MicVolumeGuard(backend=backend)

        assert guard.initialize() is False
        assert guard.is_available is False
        # poll_once on an unready guard must be a no-op, not a crash.
        guard.poll_once()

    def test_initialize_is_idempotent(self) -> None:
        backend = MagicMock()
        backend.initialize.return_value = True
        backend.name = "fake"
        backend.supports_set = True
        guard = MicVolumeGuard(backend=backend)

        assert guard.initialize() is True
        assert guard.initialize() is True
        assert backend.initialize.call_count == 1

    def test_poll_interval_honours_the_backend_floor(self) -> None:
        backend = MagicMock()
        backend.initialize.return_value = True
        backend.name = "fake"
        backend.supports_set = True
        backend.min_poll_interval_ms = DEFAULT_MIC_GUARD_POLL_MS * 3
        guard = MicVolumeGuard(backend=backend)

        guard.initialize()

        assert guard._poll_ms == DEFAULT_MIC_GUARD_POLL_MS * 3, (
            "Linux spawns a subprocess per read, so its floor must win over the default."
        )

    def test_start_is_idempotent_and_stop_joins(self) -> None:
        backend = FakeMicBackend(level=1.0)
        guard = _guard(backend)
        guard.start()
        first = guard._thread
        assert first is not None and first.is_alive()
        guard.start()
        assert guard._thread is first, "a second start() must not spawn a second watcher"

        guard.stop(timeout=2.0)
        assert not first.is_alive()
        assert guard._thread is None

    def test_watcher_thread_is_a_daemon(self) -> None:
        """RACE-008: a wedged capture-API call must not hold process exit."""
        backend = FakeMicBackend(level=1.0)
        guard = _guard(backend)
        guard.start()
        try:
            assert guard._thread is not None
            assert guard._thread.daemon is True
            assert guard._thread.name == "mic-volume-guard"
        finally:
            guard.stop()

    def test_stop_interrupts_the_poll_wait_promptly(self) -> None:
        """RACE-013: the loop waits on an Event, not a one-shot Timer."""
        backend = FakeMicBackend(level=1.0)
        guard = _guard(backend)
        guard.start()
        started = time.monotonic()
        guard.stop(timeout=5.0)
        elapsed = time.monotonic() - started
        assert elapsed < 1.0, (
            f"stop() took {elapsed:.2f}s — it should interrupt the 2s poll via the stop Event."
        )

    def test_concurrent_reads_and_writes_are_serialized(self) -> None:
        """The watcher thread and IPC dispatch share ONE backend handle."""
        backend = FakeMicBackend(level=0.5)
        guard = _guard(backend)
        errors: list[BaseException] = []

        def churn() -> None:
            try:
                for _ in range(50):
                    guard.poll_once()
                    guard.set_level(1.0)
            except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
                errors.append(exc)

        threads = [threading.Thread(target=churn, daemon=True) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert errors == []
        assert backend.get_level() == 1.0


class TestSetLevelNeverBudgeted:
    def test_set_level_before_initialize_is_a_safe_false(self) -> None:
        backend = FakeMicBackend(level=1.0)
        guard = MicVolumeGuard(backend=backend)
        assert guard.set_level(1.0) is False
        assert guard.get_level() is None

    def test_set_level_clamps(self) -> None:
        backend = FakeMicBackend(level=1.0)
        guard = _guard(backend)
        guard.set_level(2.5)
        assert backend.writes[-1] == 1.0
        guard.set_level(-1.0)
        assert backend.writes[-1] == 0.0


@pytest.mark.parametrize("target", [MIC_GUARD_TARGET_LEVEL])
def test_target_is_full_scale(target: float) -> None:
    """The whole point of the guard: the knob is pinned at 100%."""
    assert target == 1.0
