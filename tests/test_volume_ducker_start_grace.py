"""Start-cue grace on ``VolumeDucker.duck(grace_ms=...)``.

Dictation starts with its own audio cue. Smart duck reacts to speaker activity,
so without a grace the cue itself is what triggers the duck and the speakers
stay down for the whole recording. These tests pin the deferral, its
cancellation by a stop, and that the plain (grace-less) path stays immediate.
"""

from __future__ import annotations

import contextlib

import pytest
from voice_typer.server.volume_backend_base import VolumeBackend, VolumeState
from voice_typer.server.volume_ducker import VolumeDucker

from tests.fixtures.wait_helpers import wait_until


class _FakeBackend(VolumeBackend):
    """In-memory backend; ``speaker_active`` decides the smart-duck probe."""

    def __init__(self, current: float = 0.8, speaker_active: bool = True) -> None:
        self._current = current
        self._speaker_active = speaker_active
        self.fade_calls: list[tuple[float, int]] = []
        self.speaker_probes = 0

    @property
    def name(self) -> str:
        return "fake"

    @property
    def supports_per_session(self) -> bool:
        return True

    def initialize(self) -> bool:
        return True

    def get_state(self) -> VolumeState | None:
        return VolumeState(linear=self._current, muted=False)

    def set_linear(self, level: float, muted: bool | None = None) -> bool:
        self._current = max(0.0, min(1.0, level))
        return True

    def fade_to(self, target_linear: float, duration_ms: int = 150, steps: int = 10) -> bool:
        self._current = max(0.0, min(1.0, target_linear))
        self.fade_calls.append((target_linear, duration_ms))
        return True

    def is_speaker_active(self) -> bool:
        self.speaker_probes += 1
        return self._speaker_active

    def duck_other_sessions(self, level: float) -> bool:
        return True

    def restore_other_sessions(self) -> bool:
        return True


@pytest.fixture
def backend() -> _FakeBackend:
    return _FakeBackend()


@pytest.fixture
def ducker(backend: _FakeBackend) -> VolumeDucker:
    d = VolumeDucker(backend=backend)
    d.initialize()
    yield d
    with contextlib.suppress(Exception):
        d.restore(fade_ms=0, force=True)


class TestStartCueGrace:
    def test_duck_is_deferred_during_the_grace_window(self, ducker, backend, monkeypatch):
        # SMART DUCK would fire on the cue: speaker activity is reported from
        # the first probe onward, which is exactly the cue.
        monkeypatch.setattr(ducker, "_smart_duck_poll_ms", 10)
        ducker.duck(level=0.2, fade_ms=10, grace_ms=400)

        # Inside the window: no fade, no probe, nothing ducked yet.
        assert backend.fade_calls == []
        assert backend.speaker_probes == 0
        assert ducker.is_ducked is False

        assert wait_until(lambda: backend.fade_calls != [], timeout=5.0), "the deferred duck never applied"
        assert backend.fade_calls[-1][0] == pytest.approx(0.2)
        assert ducker.is_ducked is True

    def test_silence_after_the_grace_skips_the_duck(self, ducker, backend, monkeypatch):
        monkeypatch.setattr(ducker, "_smart_duck_poll_ms", 10)
        backend._speaker_active = False

        ducker.duck(level=0.2, fade_ms=10, grace_ms=100)

        # The monitor starts after the grace (one probe), finds silence, and
        # never fades the speakers.
        assert wait_until(lambda: backend.speaker_probes > 0, timeout=5.0)
        assert backend.fade_calls == []
        assert ducker.is_ducked is True  # logical duck (state saved, no fade)

    def test_restore_within_the_grace_cancels_the_pending_duck(self, ducker, backend):
        ducker.duck(level=0.2, fade_ms=10, grace_ms=300)
        assert ducker.restore(fade_ms=0) is True

        # Long enough that an uncancelled worker would have ducked by now.
        assert not wait_until(lambda: backend.fade_calls != [], timeout=0.6)
        assert ducker.is_ducked is False

    def test_zero_grace_ducks_immediately(self, ducker, backend):
        # The pre-grace contract every existing caller relies on.
        ducker.duck(level=0.2, fade_ms=10)

        assert backend.fade_calls == [(0.2, 10)]

    def test_a_second_request_supersedes_the_pending_grace(self, ducker, backend, monkeypatch):
        monkeypatch.setattr(ducker, "_smart_duck_poll_ms", 10)
        ducker.duck(level=0.2, fade_ms=10, grace_ms=200)
        ducker.duck(level=0.3, fade_ms=10, grace_ms=0)

        assert wait_until(lambda: backend.fade_calls != [], timeout=5.0)
        # The superseded worker must not apply a second, stale level.
        assert wait_until(lambda: ducker.is_ducked, timeout=5.0)
        assert all(level == pytest.approx(0.3) for level, _ in backend.fade_calls)
