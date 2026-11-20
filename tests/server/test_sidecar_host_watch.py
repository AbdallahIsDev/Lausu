"""Sidecar host-liveness watch: nothing may dictate while the app is closed.

Under ``TAURI_SIDECAR=1`` the IPC heartbeat watchdog is skipped, so an
abnormally-dead host used to leave the sidecar serving hotkeys, the plugin
bridge and dictation with no UI. The host forwards its PID and the sidecar
must tear itself down.
"""

from __future__ import annotations

import inspect
import logging
import threading
import time

from voice_typer.server import parent_watch as shared_watch, sidecar_ws
from voice_typer.server.sidecar_ws_internals import host_watch
from voice_typer.worker import _parent_watch as worker_watch


class _FakeApp:
    def __init__(self, *, raises: bool = False, block: threading.Event | None = None) -> None:
        self.quit_calls = 0
        self._raises = raises
        self._block = block

    def quit(self) -> None:
        self.quit_calls += 1
        if self._block is not None:
            self._block.wait(timeout=5.0)
        if self._raises:
            raise RuntimeError("teardown exploded")


class _FakeServer:
    def __init__(self, app: _FakeApp | None = None) -> None:
        self.app = app


def _wait_until(cond, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return False


def _run_watcher(**kwargs) -> threading.Thread | None:
    return host_watch.install_host_watch(_FakeServer(), **kwargs)


class TestEnvContract:
    def test_env_var_name_is_shared_with_the_worker(self) -> None:
        # E7: one env name, two children. A fork would let the host pass a
        # var only one of them reads.
        assert host_watch.PARENT_PID_ENV_VAR == "VOICE_TYPER_PARENT_PID"
        assert worker_watch.PARENT_PID_ENV_VAR is host_watch.PARENT_PID_ENV_VAR
        assert shared_watch.PARENT_PID_ENV_VAR is host_watch.PARENT_PID_ENV_VAR

    def test_no_parent_pid_disables_the_watch(self) -> None:
        assert _run_watcher(_pid_fn=lambda: None) is None


class TestWatcher:
    def test_dead_host_fires_on_gone_once(self) -> None:
        calls: list[bool] = []
        thread = _run_watcher(
            on_gone=lambda: calls.append(True),
            poll_interval=0.01,
            _pid_fn=lambda: 4242,
            _alive_fn=lambda pid: False,
        )
        assert thread is not None
        assert _wait_until(lambda: len(calls) == 1), "on_gone never fired"
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert len(calls) == 1, "on_gone must fire exactly once"

    def test_dead_host_logs_a_warning_naming_the_pid(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="voice_typer.parent_watch"):
            thread = _run_watcher(
                on_gone=lambda: None,
                poll_interval=0.01,
                _pid_fn=lambda: 4242,
                _alive_fn=lambda pid: False,
            )
            assert thread is not None
            thread.join(timeout=2.0)
        records = [r for r in caplog.records if "host process (pid=4242) is gone" in r.getMessage()]
        assert records, f"host loss must be logged at WARNING, got {caplog.text!r}"
        assert records[0].levelno == logging.WARNING

    def test_live_host_never_fires(self) -> None:
        calls: list[bool] = []
        stop = threading.Event()
        thread = _run_watcher(
            on_gone=lambda: calls.append(True),
            poll_interval=0.01,
            _pid_fn=lambda: 4242,
            _alive_fn=lambda pid: True,
        )
        assert thread is not None and thread.is_alive()
        time.sleep(0.05)
        stop.set()
        thread.join(timeout=2.0)
        assert not calls


class TestOnGone:
    def test_early_bind_server_exits_immediately(self) -> None:
        exits: list[int] = []
        handler = host_watch.make_on_gone(_FakeServer(None), _exit_fn=exits.append)
        handler()
        assert exits == [0], "a pre-construction host loss must exit at once"

    def test_app_quit_runs_before_any_exit(self) -> None:
        app = _FakeApp()
        exits: list[int] = []
        cancel = threading.Event()
        handler = host_watch.make_on_gone(
            _FakeServer(app),
            force_exit_grace_s=30.0,
            _exit_fn=exits.append,
            _guard_cancel=cancel,
        )
        handler()
        cancel.set()
        assert app.quit_calls == 1, "the ordinary teardown must run"
        assert exits == [], "the force-exit guard must not fire on a clean quit"

    def test_quit_failure_still_arms_the_force_exit(self) -> None:
        app = _FakeApp(raises=True)
        exits: list[int] = []
        cancel = threading.Event()
        handler = host_watch.make_on_gone(
            _FakeServer(app),
            force_exit_grace_s=0.01,
            _exit_fn=exits.append,
            _guard_cancel=cancel,
        )
        handler()
        assert app.quit_calls == 1
        assert _wait_until(lambda: exits == [0]), "a raised teardown must not survive"

    def test_wedged_quit_is_bounded_by_the_force_exit(self) -> None:
        never = threading.Event()
        app = _FakeApp(block=never)
        exits: list[int] = []
        handler = host_watch.make_on_gone(
            _FakeServer(app),
            force_exit_grace_s=0.01,
            _exit_fn=exits.append,
        )
        threading.Thread(target=handler, daemon=True).start()
        assert _wait_until(lambda: exits == [0]), "a hung teardown must not keep the orphan alive"
        never.set()


class TestInstallPoint:
    def test_run_installs_the_host_watch(self) -> None:
        source = inspect.getsource(sidecar_ws.run)
        assert "install_host_watch" in source, (
            "sidecar_ws.run is the only transport entry point: without the "
            "install call the watch never runs and an orphan keeps dictating"
        )


class TestProcZombieDetection:
    """A defunct-but-unreaped host must be reported gone, not alive.

    No real /proc access: the reader seam is mocked, so these tests behave
    identically on Windows, Linux and macOS.
    """

    _STAT_LINE = "4242 (lausu (host)) Z 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"

    def test_state_parsed_after_last_paren(self) -> None:
        # comm may contain spaces and ')': a fixed field index misreads it.
        assert shared_watch._proc_stat_state(4242, _read=lambda _pid: self._STAT_LINE) == "Z"

    def test_zombie_is_gone(self) -> None:
        assert (
            shared_watch.is_parent_alive(
                4242,
                _os_name="posix",
                _kill=lambda _pid, _sig: None,
                _proc_state=lambda _pid: "Z",
            )
            is False
        )

    def test_running_state_is_alive(self) -> None:
        assert (
            shared_watch.is_parent_alive(
                4242,
                _os_name="posix",
                _kill=lambda _pid, _sig: None,
                _proc_state=lambda _pid: "S",
            )
            is True
        )

    def test_unreadable_proc_fails_alive(self) -> None:
        def _denied(_pid: int) -> str:
            raise PermissionError(_pid, "permission denied")

        assert shared_watch._proc_stat_state(4242, _read=_denied) is None
        assert (
            shared_watch.is_parent_alive(
                4242,
                _os_name="posix",
                _kill=lambda _pid, _sig: None,
                _proc_state=lambda pid: shared_watch._proc_stat_state(pid, _read=_denied),
            )
            is True
        )

    def test_kill_permission_error_fails_alive(self) -> None:
        def _denied(_pid: int, _sig: int) -> None:
            raise PermissionError(1, "owned by another user")

        assert (
            shared_watch.is_parent_alive(
                1,
                _os_name="posix",
                _kill=_denied,
                _proc_state=lambda _pid: "Z",
            )
            is True
        )
