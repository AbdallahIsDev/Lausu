"""An unchanged config must not pin the meter to a stale denoiser (B2).

The page reaches ``update_level_processor`` two or three times with the same
config, and the second one used to be an unconditional early return — so a
chain built before the DPDFNet preload kept serving GTCRN for the session
while the UI said DPDFNet (docs/microphone-filter-failures.md §3.2). The dedupe
is still on the config, but a hit now converges the live chain in place.
"""

from __future__ import annotations

import types

import pytest
from voice_typer.server.level_monitor import monitoring_queries as queries

CONFIG = {"noise_filter_enabled": True, "noise_suppression_method": "dpdfnet"}


class _Processor:
    """A live chain whose backend may become available later."""

    def __init__(self, promoted: bool) -> None:
        self.promoted = promoted
        self.refresh_calls = 0

    def refresh_backends(self) -> bool:
        self.refresh_calls += 1
        return self.promoted


@pytest.fixture()
def installed():
    """Install a processor + config exactly as ``update_level_processor`` left them."""
    from voice_typer.server.level_monitor._state import _state as state

    def install(processor: object, config: dict | None = None) -> None:
        state._level_processor = processor
        state._level_processor_config = dict(config or CONFIG)
        state._level_processor_sample_rate = 16_000

    yield install
    state._level_processor = None
    state._level_processor_config = None


@pytest.fixture(autouse=True)
def _no_rebuild(monkeypatch: pytest.MonkeyPatch):
    """A dedupe hit must never construct a second processor (that is the point)."""

    def _explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("the unchanged path must not rebuild the chain")

    monkeypatch.setattr("voice_typer.server.audio_processor.AudioProcessor", _explode)


def test_identical_config_promotes_the_existing_chain(installed) -> None:
    from voice_typer.server.level_monitor._state import _state as state

    processor = _Processor(promoted=True)
    installed(processor)

    queries.update_level_processor(dict(CONFIG))

    assert processor.refresh_calls == 1
    assert state._level_processor is processor


def test_identical_config_keeps_the_chain_when_nothing_landed(installed) -> None:
    from voice_typer.server.level_monitor._state import _state as state

    processor = _Processor(promoted=False)
    installed(processor)

    queries.update_level_processor(dict(CONFIG))

    assert processor.refresh_calls == 1
    assert state._level_processor is processor, "a refused promotion keeps the working chain"


def test_a_broken_refresh_never_breaks_the_meter(installed) -> None:
    from voice_typer.server.level_monitor._state import _state as state

    class _Raising(_Processor):
        def refresh_backends(self) -> bool:
            raise RuntimeError("backend exploded")

    processor = _Raising(promoted=False)
    installed(processor)

    queries.update_level_processor(dict(CONFIG))

    assert state._level_processor is processor


def test_a_changed_config_still_rebuilds(installed, monkeypatch: pytest.MonkeyPatch) -> None:
    from voice_typer.server.level_monitor._state import _state as state

    built: list[types.SimpleNamespace] = []

    class _Fresh:
        def __init__(self, config: object, **_kwargs: object) -> None:
            built.append(config)  # type: ignore[arg-type]

    monkeypatch.setattr("voice_typer.server.audio_processor.AudioProcessor", _Fresh)

    stale = _Processor(promoted=False)
    installed(stale)

    queries.update_level_processor({**CONFIG, "noise_suppression_method": "gtcrn"})

    assert len(built) == 1
    assert state._level_processor is not stale
    assert stale.refresh_calls == 0, "a real change rebuilds instead of converging"


# ── The preload watcher ───────────────────────────────────────
# `update_level_processor` only converges when something calls it again, so a
# page opened before the preload finished kept serving GTCRN for its lifetime.

The_WATCHED_HAS_RUNTIME = "voice_typer.server.audio_filters.dpdfnet_backend.has_runtime"


class _Watched:
    """Processor that reports a promotion after ``promote_after`` refreshes."""

    def __init__(self, promote_after: int, *, degraded: bool = True) -> None:
        self.promote_after = promote_after
        self.is_degraded = degraded
        self.refresh_calls = 0

    def refresh_backends(self) -> bool:
        self.refresh_calls += 1
        return self.refresh_calls >= self.promote_after


@pytest.fixture()
def session(monkeypatch: pytest.MonkeyPatch):
    """An active monitoring session at a known epoch."""
    from voice_typer.server.level_monitor import monitoring
    from voice_typer.server.level_monitor._state import _state as state

    monkeypatch.setattr(monitoring, "_BACKEND_WATCH_INTERVAL_SEC", 0.01)
    with state._monitor_lock:
        state._monitor_active = True
        state._monitor_epoch += 1
        epoch = state._monitor_epoch
    yield monitoring, state, epoch
    with state._monitor_lock:
        state._monitor_active = False
        state._monitor_epoch += 1
    state._level_processor = None


def test_the_watcher_promotes_when_the_runtime_lands(session, monkeypatch: pytest.MonkeyPatch) -> None:
    monitoring, state, epoch = session
    processor = _Watched(promote_after=3)
    state._level_processor = processor
    monkeypatch.setattr(The_WATCHED_HAS_RUNTIME, lambda: False)

    monitoring._watch_pending_backend(epoch)

    assert processor.refresh_calls == 3, "it must stop the moment the chain converges"


def test_the_watcher_gives_up_on_its_own(session, monkeypatch: pytest.MonkeyPatch) -> None:
    monitoring, state, epoch = session
    monkeypatch.setattr(monitoring, "_BACKEND_WATCH_TIMEOUT_SEC", 0.3)
    processor = _Watched(promote_after=10_000)
    state._level_processor = processor
    monkeypatch.setattr(The_WATCHED_HAS_RUNTIME, lambda: False)

    monitoring._watch_pending_backend(epoch)  # must return, not hang

    assert processor.refresh_calls > 1


def test_the_watcher_stops_with_the_session(session, monkeypatch: pytest.MonkeyPatch) -> None:
    monitoring, state, epoch = session
    processor = _Watched(promote_after=1)
    state._level_processor = processor
    monkeypatch.setattr(The_WATCHED_HAS_RUNTIME, lambda: False)

    monitoring._watch_pending_backend(epoch + 1)

    assert processor.refresh_calls == 0, "a stale session's watcher must exit untouched"


def test_the_watcher_is_not_started_for_a_healthy_chain(session, monkeypatch: pytest.MonkeyPatch) -> None:
    monitoring, state, _epoch = session
    state._level_processor = _Watched(promote_after=1, degraded=False)
    started: list[object] = []

    class _Thread:
        def __init__(self, *args: object, **kwargs: object) -> None:
            started.append((args, kwargs))

        def start(self) -> None:
            raise AssertionError("a healthy chain must not spawn a watcher")

    monkeypatch.setattr(monitoring, "threading", types.SimpleNamespace(Thread=_Thread))

    monitoring._spawn_backend_watch(1)

    assert started == []


def test_the_watcher_stops_once_the_runtime_is_up_but_refused(session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A chain that refuses a READY runtime (RTF gate) will never change."""
    monitoring, state, epoch = session
    processor = _Watched(promote_after=10_000)
    state._level_processor = processor
    monkeypatch.setattr(The_WATCHED_HAS_RUNTIME, lambda: True)

    monitoring._watch_pending_backend(epoch)

    assert processor.refresh_calls == 1
