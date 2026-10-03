"""VOICE_TYPER_DEFER_MODEL_LOAD gate on startup phase 7."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def phase7_app(tmp_config_dir, monkeypatch):
    """Minimal LausuApp with stubbed platform seams for phase 7."""
    monkeypatch.setattr(
        "voice_typer.server.server_platform.autostart.is_autostart_enabled",
        lambda: False,
        raising=False,
    )
    monkeypatch.setattr(
        "voice_typer.server.server_platform.microphone_list.list_microphones",
        lambda: [],
        raising=False,
    )
    from voice_typer.server import startup_tasks
    from voice_typer.server.app import LausuApp

    monkeypatch.setattr(startup_tasks, "reconcile_configured_device", lambda app: None)
    monkeypatch.setattr(startup_tasks, "reconcile_configured_model", lambda app: None)
    instance = LausuApp()
    instance.models = MagicMock()
    return instance


def _run_phase_7(app):
    from voice_typer.server import startup_sequence as ss_mod

    return ss_mod.StartupSequence(app)._phase_7_hotkey_and_model_load()


def test_phase_7_skips_background_load_when_deferred(phase7_app, monkeypatch):
    monkeypatch.setenv("VOICE_TYPER_DEFER_MODEL_LOAD", "1")
    result = _run_phase_7(phase7_app)
    assert result.success is True
    phase7_app.models.start_background_load.assert_not_called()


def test_phase_7_loads_by_default(phase7_app, monkeypatch):
    monkeypatch.delenv("VOICE_TYPER_DEFER_MODEL_LOAD", raising=False)
    result = _run_phase_7(phase7_app)
    assert result.success is True
    phase7_app.models.start_background_load.assert_called_once()
