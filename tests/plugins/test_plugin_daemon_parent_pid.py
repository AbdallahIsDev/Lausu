"""Internal-plugin daemon env: the Node bridge inherits the host-PID contract.

On POSIX the OS reaper kills only the sidecar, so the Node daemon needs its own
watch to exit when the host dies (Windows also has the Job Object). Both
plugins build their daemon env explicitly, so the handoff needs a pin.
"""

from __future__ import annotations

import pytest
from tools.internal_plugins.anthropic_stt import plugin as anthropic_plugin
from tools.internal_plugins.google_stt import plugin as google_plugin
from voice_typer.server.parent_watch import PARENT_PID_ENV_VAR


@pytest.mark.parametrize("plugin", [anthropic_plugin, google_plugin])
class TestDaemonParentPid:
    def test_forwards_the_host_pid(self, monkeypatch: pytest.MonkeyPatch, plugin) -> None:
        monkeypatch.setenv(PARENT_PID_ENV_VAR, "4242")
        assert plugin._daemon_env()[PARENT_PID_ENV_VAR] == "4242"

    def test_absent_pid_stays_absent(self, monkeypatch: pytest.MonkeyPatch, plugin) -> None:
        monkeypatch.delenv(PARENT_PID_ENV_VAR, raising=False)
        assert PARENT_PID_ENV_VAR not in plugin._daemon_env()
