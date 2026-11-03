"""Startup prewarm: gated on tts_enabled, post-ready, never raises into startup."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from voice_typer.server.tts import prewarm

REPO_ROOT = Path(__file__).resolve().parent.parent


def _app(*, enabled: bool, engine: str = "magpie", calls: list[str] | None = None, fail: bool = False):
    calls = calls if calls is not None else []

    def tts_prewarm(name: str) -> bool:
        if fail:
            raise RuntimeError("runtime exploded")
        calls.append(name)
        return True

    return SimpleNamespace(
        config=SimpleNamespace(tts_enabled=enabled, tts_engine=engine),
        service=SimpleNamespace(tts_prewarm=tts_prewarm),
    )


def _wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_disabled_does_not_start_anything() -> None:
    calls: list[str] = []
    assert prewarm.start_prewarm(_app(enabled=False, calls=calls)) is None
    assert calls == []


def test_no_engine_selected_does_not_start_anything() -> None:
    calls: list[str] = []
    assert prewarm.start_prewarm(_app(enabled=True, engine="off", calls=calls)) is None
    assert calls == []


def test_enabled_and_selected_prewarms_the_engine_once() -> None:
    calls: list[str] = []
    thread = prewarm.start_prewarm(_app(enabled=True, engine="magpie", calls=calls))

    assert thread is not None
    assert _wait_until(lambda: calls == ["magpie"])
    thread.join(timeout=5)
    assert calls == ["magpie"]


def test_a_failing_runtime_never_escapes_the_thread() -> None:
    thread = prewarm.start_prewarm(_app(enabled=True, fail=True))
    assert thread is not None
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_prewarm_starts_after_the_ready_marker() -> None:
    """C-START-1: the ready line must be logged before prewarm runs."""
    source = (REPO_ROOT / "voice_typer" / "server" / "startup_sequence" / "_phases_late.py").read_text(encoding="utf-8")
    ready = source.index('complete_msg = "[STARTUP] Startup complete')
    start = source.index("start_prewarm(app)")
    assert ready < start, "TTS prewarm must not sit in front of the ready marker"


@pytest.mark.parametrize("engine", ["audio8", "magpie"])
def test_only_real_engines_reach_the_service(engine: str) -> None:
    calls: list[str] = []
    thread = prewarm.start_prewarm(_app(enabled=True, engine=engine, calls=calls))
    assert thread is not None
    assert _wait_until(lambda: calls == [engine])
    thread.join(timeout=5)


def test_missing_config_is_ignored() -> None:
    assert prewarm.start_prewarm(SimpleNamespace()) is None


def test_prewarm_thread_is_daemon_so_it_cannot_block_quit() -> None:
    thread = prewarm.start_prewarm(_app(enabled=True, calls=[]))
    assert thread is not None
    assert thread.daemon is True
    thread.join(timeout=5)
    assert threading.current_thread() is not thread
