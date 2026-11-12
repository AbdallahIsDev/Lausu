"""Startup prewarm: gated on tts_enabled, post-ready, never raises into startup."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from voice_typer.server.tts import prewarm

REPO_ROOT = Path(__file__).resolve().parent.parent


def _app(
    *,
    enabled: bool,
    engine: str = "magpie",
    calls: list[str] | None = None,
    fail: bool = False,
    attach_service: bool = True,
):
    """Fake ``LausuApp``.

    The TTS service is reached through ``app._ipc_server.service`` — that is the
    real shape (``LausuService`` is composed onto the IPC server, which registers
    itself back onto the app in ``IPCServer.start()``). The earlier fixture put
    ``service`` straight on the app, which is why ``app.service.tts_prewarm``
    stayed green while raising ``AttributeError`` on every real startup.
    """
    calls = calls if calls is not None else []

    def tts_prewarm(name: str) -> bool:
        if fail:
            raise RuntimeError("runtime exploded")
        calls.append(name)
        return True

    app = SimpleNamespace(config=SimpleNamespace(tts_enabled=enabled, tts_engine=engine))
    if attach_service:
        app._ipc_server = SimpleNamespace(service=SimpleNamespace(tts_prewarm=tts_prewarm))
    return app


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


def test_a_bare_app_attribute_error_is_a_clean_skip(caplog: pytest.LogCaptureFixture) -> None:
    """The app has no ``service`` of its own; a boot without one must not crash.

    Regression for ``AttributeError: 'LausuApp' object has no attribute
    'service'`` logged as ``[TTS] prewarm failed engine=magpie`` on every start.
    """
    caplog.set_level(logging.DEBUG, logger="voice_typer.server.tts.prewarm")
    thread = prewarm.start_prewarm(_app(enabled=True, attach_service=False))
    assert thread is not None
    thread.join(timeout=5)

    messages = [r.getMessage() for r in caplog.records]
    assert "[TTS] prewarm skipped: TTS service not attached yet" in messages
    assert not [m for m in messages if "prewarm failed" in m]


def test_the_service_is_reached_through_the_ipc_server() -> None:
    """The callable lives on ``app._ipc_server.service``, not on the app."""
    calls: list[str] = []
    app = _app(enabled=True, calls=calls)
    # ``app.service`` does not exist on a real LausuApp; assert the fix reads
    # the server path instead of inventing the attribute.
    assert not hasattr(app, "service")

    thread = prewarm.start_prewarm(app)
    assert thread is not None
    assert _wait_until(lambda: calls == ["magpie"])
    thread.join(timeout=5)


def test_prewarm_thread_is_daemon_so_it_cannot_block_quit() -> None:
    thread = prewarm.start_prewarm(_app(enabled=True, calls=[]))
    assert thread is not None
    assert thread.daemon is True
    thread.join(timeout=5)
    assert threading.current_thread() is not thread
