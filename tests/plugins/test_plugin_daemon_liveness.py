"""A slow bridge must not be mistaken for a dead daemon.

Regression: reloading the extension broke content-script ports in already-open
tabs, so GET /status took seconds. Python's 1.5 s probe called the daemon dead
and spawned a second one on the same port (EADDRINUSE), freezing every hotkey
for ~80 s in ensure_daemon's retry loop.
"""

from __future__ import annotations

import logging
import urllib.request

import pytest
from tools.internal_plugins._common import daemon as daemon_common
from tools.internal_plugins._common.bridge.daemon_client import DaemonClient


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"browser": "connected"}'


class TestFailedDaemonLog:
    def test_a_failed_daemon_is_not_reported_as_ready(self, monkeypatch, caplog):
        import importlib.util
        import sys
        from pathlib import Path
        from unittest.mock import MagicMock

        path = (
            Path(__file__).resolve().parents[2]
            / "tools"
            / "internal_plugins"
            / "anthropic_stt"
            / "plugin.py"
        )
        name = "anthropic_stt_liveness_log_under_test"
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        monkeypatch.setattr(module, "ensure_daemon", lambda: False)

        session = module.PluginSession(MagicMock())
        monkeypatch.setattr(session, "_notify", lambda _msg: None)
        caplog.set_level(logging.INFO)

        session.start()

        assert not any("bridge ready" in r.getMessage() for r in caplog.records)


class TestDaemonLiveness:
    def test_a_patient_probe_counts_a_slow_status_as_alive(self, monkeypatch):
        seen: list[float] = []

        def _urlopen(_request, timeout):
            seen.append(timeout)
            return _Response()

        monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
        client = DaemonClient("TEST_PLUGIN_URL", port=17875)

        assert client.alive() is True
        assert seen and seen[0] >= 5.0

    def test_a_listening_daemon_is_never_spawned_twice(self, monkeypatch, tmp_path):
        polls = iter([False, False, True])

        def _forbidden_spawn(*_args, **_kwargs):
            pytest.fail("a listening daemon must not be spawned again")

        monkeypatch.setattr(daemon_common.subprocess, "Popen", _forbidden_spawn)

        ok = daemon_common.ensure_daemon(
            tmp_path,
            lambda: next(polls),
            logging.getLogger("test-daemon-liveness"),
            listening_fn=lambda: True,
            attempts=10,
            interval=0.0,
        )

        assert ok is True

    def test_a_dead_daemon_is_still_spawned(self, monkeypatch, tmp_path):
        spawned: list[object] = []

        class _Process:
            pass

        monkeypatch.setattr(
            daemon_common.subprocess,
            "Popen",
            lambda *args, **kwargs: spawned.append(args) or _Process(),
        )

        ok = daemon_common.ensure_daemon(
            tmp_path,
            lambda: True,
            logging.getLogger("test-daemon-liveness"),
            listening_fn=lambda: False,
        )

        assert ok is True
        assert len(spawned) == 0, "an already-alive daemon needs no spawn"

        polls = iter([False, True])
        ok = daemon_common.ensure_daemon(
            tmp_path,
            lambda: next(polls),
            logging.getLogger("test-daemon-liveness"),
            listening_fn=lambda: False,
            attempts=5,
            interval=0.0,
        )
        assert ok is True
        assert len(spawned) == 1
