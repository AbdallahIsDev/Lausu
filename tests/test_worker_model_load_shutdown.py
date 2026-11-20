"""Model-load shutdown drain: every load is tracked and bounded.

A load runs on the default executor via ``to_thread``. Cancelling its task
cannot stop that thread, and ``asyncio.run()`` joins the executor at
finalization, so loads must register for the drain and re-check a shared
abort event. No real model/WS dependency here: all loads are synthetic.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest
import voice_typer.worker._ws_commands as commands_mod
import voice_typer.worker._ws_connection as connection_mod
import voice_typer.worker._ws_server as server_mod
from voice_typer.worker._ws_commands import (
    MODEL_LOAD_DRAIN_TIMEOUT_S,
    _CommandHandles,
    _spawn_model_load,
    model_load_abort,
    model_loads,
)
from voice_typer.worker._ws_shutdown import _ShutdownTimer

BUDGET_S = 2.0
assert BUDGET_S < MODEL_LOAD_DRAIN_TIMEOUT_S


@pytest.fixture(autouse=True)
def _reset_model_load_state():
    model_load_abort.clear()
    model_loads.clear()
    yield
    model_load_abort.clear()
    model_loads.clear()


class _Sink:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, frame: str) -> None:
        self.sent.append(frame)


def _handles(sink: _Sink) -> _CommandHandles:
    async def _complete(_fn, _rid):
        raise AssertionError("load path must not use the transcribe tail")

    def _launch(_fn, _rid):
        raise AssertionError("load path must not use the transcribe tail")

    return _CommandHandles(
        websocket=sink, samples={}, aborted=set(), streams={}, complete=_complete, launch=_launch
    )


def _cooperative_run(release: asyncio.Event | None = None) -> dict:
    """Slow load that polls the shared abort event like a real load path.

    ``release`` (when given) gates completion for the registration test;
    the abort event gates it for every shutdown test.
    """
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if model_load_abort.is_set():
            break
        if release is not None and release.is_set():
            break
        time.sleep(0.005)
    return {"loaded": True, "backend": "synthetic", "device_info": "cpu", "error": None}


class TestTracking:
    async def test_load_task_registered_then_removed(self) -> None:
        release = asyncio.Event()
        sink = _Sink()
        _spawn_model_load(
            _handles(sink),
            backend="synthetic",
            result_type="load_synthetic_result",
            request_id=1,
            run=lambda: _cooperative_run(release),
        )
        deadline = time.monotonic() + 2.0
        while not model_loads and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        assert len(model_loads) == 1, "the load coroutine must be in the drain set"
        release.set()
        while model_loads and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        assert not model_loads, "done loads must unregister"
        assert len(sink.sent) == 1

    async def test_all_load_commands_use_the_tracked_spawn(self, monkeypatch) -> None:
        calls: list[str] = []
        real_spawn = commands_mod._spawn_model_load

        def _spy(handles, **kwargs):
            calls.append(kwargs["backend"])
            return real_spawn(handles, **kwargs)

        monkeypatch.setattr(commands_mod, "_spawn_model_load", _spy)

        class _Stub:
            def load_whisper_model(self, *_a, **_k):
                return {"loaded": True}

            def load_parakeet_model(self, *_a, **_k):
                return {"loaded": True}

            def load_qwen_model(self, *_a, **_k):
                return {"loaded": True}

        import voice_typer.worker._transcribe as transcribe_mod

        monkeypatch.setattr(transcribe_mod, "get_transcriber", lambda: _Stub())
        sink = _Sink()
        handles = _handles(sink)
        await commands_mod.handle_load_whisper_model_async(
            {"id": 1, "data": {"model_size": "tiny"}}, handles
        )
        await commands_mod.handle_load_parakeet_model_async({"id": 2, "data": {}}, handles)
        await commands_mod.handle_load_qwen_model_async(
            {"id": 3, "data": {"model_path": "/tmp/qwen"}}, handles
        )
        assert calls == ["whisper", "parakeet", "qwen"]


class TestBoundedExit:
    def test_slow_load_aborts_within_budget_and_logs(self, caplog) -> None:
        async def scenario():
            sink = _Sink()
            _spawn_model_load(
                _handles(sink),
                backend="synthetic",
                result_type="load_synthetic_result",
                request_id=7,
                run=_cooperative_run,
            )
            deadline = time.monotonic() + 2.0
            while not model_loads and time.monotonic() < deadline:
                await asyncio.sleep(0.005)
            assert model_loads, "load never started"
            model_load_abort.set()
            t0 = time.monotonic()
            tasks = list(model_loads)
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=BUDGET_S
            )
            elapsed = time.monotonic() - t0
            assert elapsed < BUDGET_S, f"drain took {elapsed:.2f}s"
            frame = json.loads(sink.sent[0])
            assert frame["data"]["error"] == "cancelled during shutdown"

        import logging

        with caplog.at_level(logging.INFO, logger="voice_typer.worker"):
            asyncio.run(scenario())
        assert any("cancelled during shutdown" in r.getMessage() for r in caplog.records)


class _ScriptWS:
    """Minimal async-iterable socket for the frame-loop test."""

    def __init__(self, frames: list[dict]) -> None:
        self._frames = list(frames)
        self.sent: list[str] = []

    async def send(self, frame: str) -> None:
        self.sent.append(frame)

    async def close(self, code=None) -> None:
        return None

    def __aiter__(self):
        async def _gen():
            for frame in self._frames:
                yield json.dumps(frame)

        return _gen()


class TestShutdownDrain:
    async def test_shutdown_command_drains_model_loads(self, monkeypatch, caplog) -> None:
        async def _auth(_ws) -> bool:
            return True

        monkeypatch.setattr(connection_mod, "_authenticate", _auth)

        def _slow_load(*_a, **_k) -> dict:
            return _cooperative_run()

        class _Stub:
            load_whisper_model = staticmethod(_slow_load)

        import voice_typer.worker._transcribe as transcribe_mod

        monkeypatch.setattr(transcribe_mod, "get_transcriber", lambda: _Stub())

        ws = _ScriptWS(
            [
                {"cmd": "load_whisper_model", "id": 1, "data": {"model_size": "tiny"}},
                {"cmd": "shutdown"},
            ]
        )
        import logging

        t0 = time.monotonic()
        with caplog.at_level(logging.INFO, logger="voice_typer.worker"):
            await connection_mod._handle_connection(
                ws,
                prewarm_ran=True,
                stop_event=asyncio.Event(),
                shutdown_timer=_ShutdownTimer(),
            )
        elapsed = time.monotonic() - t0
        assert elapsed < BUDGET_S, f"shutdown command took {elapsed:.2f}s"
        assert model_load_abort.is_set()
        assert any("cancelled during shutdown" in r.getMessage() for r in caplog.records)

    async def test_parent_gone_signals_the_same_event(self, monkeypatch) -> None:
        class _FakeSock:
            def getsockname(self):
                return ("127.0.0.1", 51234)

        class _FakeServe:
            sockets = [_FakeSock()]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_exc):
                return False

        class _FakeThread:
            def is_alive(self) -> bool:
                return True

        monkeypatch.setattr(
            "websockets.asyncio.server.serve", lambda *_a, **_kw: _FakeServe()
        )
        monkeypatch.setattr(server_mod, "_install_sigterm_handler", lambda *_a: None)
        monkeypatch.setattr(server_mod, "start_parent_watch", lambda **_kw: None)
        monkeypatch.setattr(server_mod, "_emit_worker_started", lambda *_a: None)
        monkeypatch.setattr(
            server_mod, "start_prewarm_in_background", lambda: _FakeThread()
        )
        stop_event = asyncio.Event()
        stop_event.set()
        assert (
            await server_mod.run_worker_server(
                prewarm_ran=True,
                stop_event=stop_event,
                shutdown_timer=_ShutdownTimer(),
            )
            is True
        )
        assert model_load_abort.is_set()
