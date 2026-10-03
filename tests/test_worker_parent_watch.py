"""Worker orphan self-exit: parent liveness watch."""

from __future__ import annotations

import os
import threading
import time

from voice_typer.worker import _parent_watch as _pw


class TestParentPidFromEnv:
    def test_valid_pid(self) -> None:
        assert _pw.parent_pid_from_env({"VOICE_TYPER_PARENT_PID": "1234"}) == 1234

    def test_missing_disables(self) -> None:
        assert _pw.parent_pid_from_env({}) is None

    def test_garbage_disables(self) -> None:
        assert _pw.parent_pid_from_env({"VOICE_TYPER_PARENT_PID": "abc"}) is None

    def test_non_positive_disables(self) -> None:
        assert _pw.parent_pid_from_env({"VOICE_TYPER_PARENT_PID": "0"}) is None
        assert _pw.parent_pid_from_env({"VOICE_TYPER_PARENT_PID": "-5"}) is None


class TestIsParentAlive:
    # NEVER probe with the real ``os.kill`` on Windows: ``CTRL_C_EVENT``
    # is 0, so ``os.kill(pid, 0)`` delivers Ctrl+C to this console and
    # the KeyboardInterrupt surfaces in a later test's setup. The POSIX
    # branch only ever runs on POSIX in production; here it gets a fake.
    def test_posix_live(self) -> None:
        assert _pw.is_parent_alive(1234, _os_name="posix", _kill=lambda pid, sig: None) is True

    def test_posix_dead(self) -> None:
        def _raise(pid: int, sig: int) -> None:
            raise ProcessLookupError(pid, "gone")

        assert _pw.is_parent_alive(999_999_999, _os_name="posix", _kill=_raise) is False

    def test_posix_permission_denied_is_alive(self) -> None:
        def _raise(pid: int, sig: int) -> None:
            raise PermissionError(pid, "owned by another user")

        assert _pw.is_parent_alive(1, _os_name="posix", _kill=_raise) is True

    def test_windows_delegates_to_pid_probe(self, monkeypatch) -> None:
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setattr(
            "voice_typer.server.single_instance._is_pid_alive",
            lambda pid: pid == 4242,
        )
        assert _pw.is_parent_alive(4242) is True
        assert _pw.is_parent_alive(4243) is False


class TestStartParentWatch:
    def _wait_until(self, cond, timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cond():
                return True
            time.sleep(0.01)
        return False

    def test_no_env_disables(self) -> None:
        assert (
            _pw.start_parent_watch(on_gone=lambda: None, _pid_fn=lambda: None) is None
        )

    def test_dead_parent_fires_once(self) -> None:
        calls: list[bool] = []
        stop = threading.Event()
        thread = _pw.start_parent_watch(
            on_gone=lambda: calls.append(True),
            poll_interval=0.01,
            stop=stop,
            _alive_fn=lambda pid: False,
            _pid_fn=lambda: 4242,
        )
        assert thread is not None
        assert self._wait_until(lambda: len(calls) == 1), "on_gone never fired"
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "watch must exit after firing"
        assert len(calls) == 1, "on_gone must fire exactly once"

    def test_live_then_dead_parent(self) -> None:
        states = [True, True, False]
        calls: list[bool] = []
        thread = _pw.start_parent_watch(
            on_gone=lambda: calls.append(True),
            poll_interval=0.01,
            _alive_fn=lambda pid: states.pop(0) if states else False,
            _pid_fn=lambda: 4242,
        )
        assert thread is not None
        assert self._wait_until(lambda: len(calls) == 1), "on_gone never fired"
        thread.join(timeout=2.0)
        assert not thread.is_alive()

    def test_stop_terminates_live_watch(self) -> None:
        stop = threading.Event()
        thread = _pw.start_parent_watch(
            on_gone=lambda: None,
            poll_interval=30.0,
            stop=stop,
            _alive_fn=lambda pid: True,
            _pid_fn=lambda: 4242,
        )
        assert thread is not None and thread.is_alive()
        stop.set()
        thread.join(timeout=2.0)
        assert not thread.is_alive()

    def test_on_gone_exception_does_not_escape(self) -> None:
        def _boom() -> None:
            raise RuntimeError("boom")

        thread = _pw.start_parent_watch(
            on_gone=_boom,
            poll_interval=0.01,
            _alive_fn=lambda pid: False,
            _pid_fn=lambda: 4242,
        )
        assert thread is not None
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "watch must exit even when on_gone raises"
