"""Dev-only plugin diagnostics must be absent from frozen builds."""

from __future__ import annotations

import sys

from tools.internal_plugins._common import daemon as _daemon


def test_dev_flag_is_not_forwarded_by_default(monkeypatch):
    monkeypatch.delenv("VOICE_TYPER_PLUGIN_DIAGNOSTICS", raising=False)
    monkeypatch.delenv("VOICE_TYPER_FROZEN", raising=False)
    env = _daemon.daemon_env()
    assert env.get("VOICE_TYPER_PLUGIN_DIAGNOSTICS") is None
    assert env.get("VOICE_TYPER_FROZEN") is None


def test_frozen_simulation_marks_the_daemon_even_with_the_dev_flag(monkeypatch):
    monkeypatch.setenv("VOICE_TYPER_PLUGIN_DIAGNOSTICS", "1")
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("VOICE_TYPER_FROZEN", raising=False)

    env = _daemon.daemon_env()

    assert env["VOICE_TYPER_PLUGIN_DIAGNOSTICS"] == "1"
    assert env["VOICE_TYPER_FROZEN"] == "1"
