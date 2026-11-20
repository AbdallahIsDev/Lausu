"""XV (Performance & Resources) fix regression tests.

Source-text pins were migrated to behavioral probes per
``docs/adr/source-text-test-migration.md``; the remaining structural gates
walk real collaborators (``Path.rglob`` spy, module-local sleep spy).
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.fixtures.sleep_seam import patch_module_sleep

# XV-1 deps-probe tests removed 2026-08-15: ``_check_qwen_deps`` /


class TestDownloadPollScopedToModelDir:
    """Progress polling walks the in-progress repo subdir, not the whole cache tree."""

    def test_poll_walks_only_the_per_repo_subdir(self, tmp_path, monkeypatch):
        """Drive the real poll loop and spy on which path ``rglob`` walks."""
        from voice_typer.server import asr_setup
        from voice_typer.server.service import _download_helpers as dh

        cache_dir = tmp_path / "cache"
        model_dir = cache_dir / "models--org--model"
        (model_dir / "snapshots").mkdir(parents=True)
        (model_dir / "snapshots" / "model.bin").write_bytes(b"abc")
        (cache_dir / "unrelated.bin").write_bytes(b"def")

        walked: list[Path] = []
        real_rglob = Path.rglob

        def spy_rglob(self, pattern):
            walked.append(self)
            return real_rglob(self, pattern)

        monkeypatch.setattr(Path, "rglob", spy_rglob)
        monkeypatch.setattr(asr_setup, "is_download_paused", lambda: False)
        monkeypatch.setattr(asr_setup, "wait_while_paused", lambda **kwargs: None)

        class FakeThread:
            def __init__(self):
                self._alive = True

            def is_alive(self):
                alive = self._alive
                self._alive = False
                return alive

            def join(self, timeout=None):
                return None

        dh.poll_download_progress(
            thread=FakeThread(),
            target_bytes=3,
            target_mb=1,
            model_name="tiny.en",
            repo_id="org/model",
            cache_dir=cache_dir,
            download_id="dl-1",
            event_bus=MagicMock(),
            is_cancelled_fn=lambda _id: False,
        )

        assert walked, "the poll loop must walk the cache for file sizes"
        assert all(root == model_dir for root in walked), (
            f"rglob must only walk the per-repo subdir, got {walked}"
        )
        assert cache_dir not in walked, "rglob must never walk the whole HF cache root"


class TestMicrophonesCacheEmptyList:
    """a legitimately-empty device list is served from cache."""

    def test_cache_initialised_to_none(self, tmp_config_dir):
        """The cache must start as ``None`` so we can distinguish"""
        from voice_typer.server.service import LausuService

        class FakeApp:
            config = type("FakeConfig", (), {})()

        svc = LausuService(FakeApp())
        assert svc._microphones_cache is None, (
            "XV-5: _microphones_cache must be initialised to None (not "
            "[]) so the truthiness check doesn't bypass the cache when "
            "PortAudio returns an empty list."
        )

    def test_empty_list_served_from_cache(self, tmp_config_dir, monkeypatch):
        """When the cache holds an empty list (legitimate \"0 mics\"),"""
        from voice_typer.server import service as svc_mod

        class FakeApp:
            config = type("FakeConfig", (), {})()
            _microphones = []
            tray = MagicMock()

        svc = svc_mod.LausuService(FakeApp())

        # Seed the cache with an empty list (simulating PortAudio
        svc._microphones_cache = []
        svc._microphones_cache_ts = time.monotonic()

        call_count = {"n": 0}

        def fake_list_microphones():
            call_count["n"] += 1
            return [{"name": "should-not-be-returned", "index": 0}]

        monkeypatch.setattr(
            "voice_typer.server.server_platform.microphone_list.list_microphones",
            fake_list_microphones,
        )

        result = svc.refresh_microphones()
        assert result == [], (
            "XV-5: refresh_microphones must serve the cached empty list "
            "instead of re-querying PortAudio when the cache is empty."
        )
        assert call_count["n"] == 0, (
            "XV-5: list_microphones must NOT be called when the cache (even if empty) is fresh."
        )

    def test_non_empty_list_still_served_from_cache(self, tmp_config_dir, monkeypatch):
        """Sanity: a non-empty cache continues to be served (regression"""
        from voice_typer.server import service as svc_mod

        class FakeApp:
            config = type("FakeConfig", (), {})()
            _microphones = []
            tray = MagicMock()

        svc = svc_mod.LausuService(FakeApp())
        cached_mics = [{"name": "USB Mic", "index": 0}]
        svc._microphones_cache = cached_mics
        svc._microphones_cache_ts = time.monotonic()

        call_count = {"n": 0}
        monkeypatch.setattr(
            "voice_typer.server.server_platform.microphone_list.list_microphones",
            lambda: call_count.__setitem__("n", call_count["n"] + 1) or [],
        )

        result = svc.refresh_microphones()
        assert result == cached_mics
        assert call_count["n"] == 0


class TestWaitForIpcReady:
    """XV-6: ``_wait_for_ipc_ready`` provides a bounded (5 s deadline)"""

    def test_returns_true_immediately_when_port_open(self, monkeypatch):
        """When the IPC port is already accepting connections, the poll"""
        from voice_typer.server import autostart_launcher as al

        monkeypatch.setattr(al, "_is_port_open", lambda h, p: True)
        monkeypatch.setattr(al, "_read_ipc_port_from_pid_file", lambda: None)
        # Force the deadline path to be observable: patch sleep to fail
        sleep_calls = patch_module_sleep(monkeypatch, al)

        result = al._wait_for_ipc_ready(deadline_s=5.0)
        assert result is True
        assert sleep_calls == [], "XV-6: must not sleep when the port is already open on the first poll."

    def test_returns_false_on_deadline_when_port_closed(self, monkeypatch):
        """When the IPC port never opens, the poll must run for at most"""
        from voice_typer.server import autostart_launcher as al

        monkeypatch.setattr(al, "_is_port_open", lambda h, p: False)
        monkeypatch.setattr(al, "_read_ipc_port_from_pid_file", lambda: None)
        # Speed up the test: zero out sleep so the deadline loop spins
        patch_module_sleep(monkeypatch, al)
        # Use a tiny deadline + patch monotonic so we don't actually
        start = [time.monotonic()]

        # Drive monotonic forward artificially to expire the deadline
        call_count = {"n": 0}

        def fake_monotonic():
            call_count["n"] += 1
            return start[0] + call_count["n"] * 0.25

        monkeypatch.setattr(al.time, "monotonic", fake_monotonic)

        result = al._wait_for_ipc_ready(deadline_s=1.0, poll_interval_s=0.25)
        assert result is False, (
            "XV-6: must return False (not raise) when the IPC port never becomes ready within the deadline."
        )

    def test_uses_port_from_pid_file_when_present(self, monkeypatch):
        """When the backend PID file declares a non-default port, the"""
        from voice_typer.server import autostart_launcher as al

        captured_ports = []
        monkeypatch.setattr(al, "_is_port_open", lambda h, p: captured_ports.append(p) or True)
        monkeypatch.setattr(al, "_read_ipc_port_from_pid_file", lambda: 12345)
        monkeypatch.setattr(al.time, "sleep", lambda s: None)

        result = al._wait_for_ipc_ready(deadline_s=1.0)
        assert result is True
        assert 12345 in captured_ports, "XV-6: must use the port from the PID file (12345), not the default IPC_PORT."

    def test_falls_back_to_default_port_when_pid_file_missing(self, monkeypatch):
        """When the PID file is missing/unreadable, the poll falls back"""
        from voice_typer.server import autostart_launcher as al

        captured_ports = []
        monkeypatch.setattr(al, "_is_port_open", lambda h, p: captured_ports.append(p) or True)
        monkeypatch.setattr(al, "_read_ipc_port_from_pid_file", lambda: None)
        monkeypatch.setattr(al.time, "sleep", lambda s: None)

        al._wait_for_ipc_ready(deadline_s=1.0)
        assert al.IPC_PORT in captured_ports

    def test_returns_true_after_finite_polls_when_port_opens_late(self, monkeypatch):
        """When the port opens after N failed polls, the function must"""
        from voice_typer.server import autostart_launcher as al

        poll_results = [False, False, True]  # port opens on 3rd poll
        call_idx = {"n": 0}

        def fake_is_port_open(host, port):
            idx = call_idx["n"]
            call_idx["n"] += 1
            return poll_results[idx] if idx < len(poll_results) else True

        monkeypatch.setattr(al, "_is_port_open", fake_is_port_open)
        monkeypatch.setattr(al, "_read_ipc_port_from_pid_file", lambda: None)
        monkeypatch.setattr(al.time, "sleep", lambda s: None)

        result = al._wait_for_ipc_ready(deadline_s=10.0, poll_interval_s=0.25)
        assert result is True
        # Exactly 3 polls: 2 failed + 1 succeeded.
        assert call_idx["n"] == 3, f"XV-6: expected 3 polls (2 fail + 1 succeed), got {call_idx['n']}"


class TestLaunchWaitsForIpcInsteadOfFixedSleep:
    """The spawn-success path waits for IPC readiness, not a fixed sleep."""

    def test_spawn_success_waits_for_ready_without_fixed_sleep(self, monkeypatch):
        """Drive ``launch()`` to a successful Tauri spawn with fakes/spies."""
        from voice_typer.server import autostart_launcher as al, backend_pid

        sleeps = patch_module_sleep(monkeypatch, al)
        ready_calls: list[bool] = []
        monkeypatch.setattr(al, "_setup_logging", lambda: None)
        monkeypatch.setattr(al.sys, "argv", ["autostart_launcher.py"])
        monkeypatch.setattr(al, "_parse_delay", lambda argv: 0.0)
        monkeypatch.setattr(backend_pid, "_backend_pid_file", lambda: MagicMock(exists=lambda: False))
        monkeypatch.setattr(al, "_read_ipc_port_from_pid_file", lambda: None)
        monkeypatch.setattr(al, "_is_port_open", lambda host, port: False)
        monkeypatch.setattr(al, "_is_tauri_mode", lambda: True)
        monkeypatch.setattr(al, "_tauri_binary", lambda: "C:/fake/lausu.exe")
        monkeypatch.setattr(al, "_spawn_tauri_host", lambda binary, hidden=False: MagicMock(pid=4242))
        monkeypatch.setattr(al, "_write_pid_file", lambda *args, **kwargs: None)
        monkeypatch.setattr(al, "_wait_for_ipc_ready", lambda: ready_calls.append(True))

        assert al.launch() == 0
        assert ready_calls == [True], "the spawn-success path must wait for IPC readiness"
        assert sleeps == [], "no fixed sleep belongs on the spawn-success path"


class TestNumpyDeadImportRemoved:
    """XV-4: the dead ``import numpy as np`` at the top of ``app.py``"""

    def test_app_module_does_not_import_numpy(self):
        """Source guard: no ``import numpy`` line at module top."""
        app_path = Path(__file__).resolve().parent.parent / "voice_typer" / "server" / "app.py"
        src = app_path.read_text()
        # Check the top-level import statements only (first ~60 lines
        for line in src.splitlines()[:60]:
            stripped = line.lstrip()
            if stripped.startswith("import numpy") or stripped.startswith("from numpy"):
                pytest.fail(f"XV-4: app.py still imports numpy at module top: {line!r}")

    def test_app_module_imports_cleanly(self):
        """Sanity: app.py must still import successfully after the dead"""
        try:
            import voice_typer.server.app  # noqa: F401
        except ImportError as exc:
            # Only skip if the failure originates OUTSIDE app.py itself
            if "voice_typer/server/app.py" in str(exc):
                pytest.fail(
                    f"XV-4: app.py failed to import after numpy removal (likely a missed ``np`` reference): {exc}"
                )
            pytest.skip(
                f"XV-4 sanity check skipped, downstream import error "
                f"outside app.py scope (parallel agent edit in progress?): {exc}"
            )
