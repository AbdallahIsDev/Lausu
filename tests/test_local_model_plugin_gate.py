"""The local ASR model must not be warmed while a plugin serves dictation.

A plugin transcribes in the browser and never records locally, so warming an
engine spends RAM, a worker process and startup time on a model the hotkey will
not use. These tests pin the two places that could start that load (the startup
phase and the model manager's background-load entry point) and the fallback:
with no plugin selected, the local model still owns dictation.
"""

from __future__ import annotations

import logging
import threading
from unittest.mock import MagicMock

import pytest
from voice_typer.server.model_manager._loading import LoadingMixin
from voice_typer.server.startup_sequence import _phases_late


@pytest.fixture
def phase7_app(monkeypatch) -> MagicMock:
    from voice_typer.server import startup_tasks

    monkeypatch.setattr(startup_tasks, "reconcile_configured_device", lambda app: None)
    monkeypatch.setattr(startup_tasks, "reconcile_configured_model", lambda app: None)
    monkeypatch.delenv("VOICE_TYPER_DEFER_MODEL_LOAD", raising=False)

    app = MagicMock(name="app")
    app._shutting_down = False
    app.models = MagicMock()
    return app


def _phase_7(app):
    from voice_typer.server.startup_sequence import StartupSequence

    seq = StartupSequence.__new__(StartupSequence)
    seq._app = app
    seq._t0 = 0.0
    return _phases_late.LatePhases._phase_7_hotkey_and_model_load(seq)


def _phase_8(app):
    from voice_typer.server.startup_sequence import StartupSequence

    seq = StartupSequence.__new__(StartupSequence)
    seq._app = app
    seq._t0 = 0.0
    return _phases_late.LatePhases._phase_8_finalize_and_signal(seq)


def _patch_owner(monkeypatch, name: str) -> None:
    from voice_typer.server import internal_plugin_hook

    monkeypatch.setattr(internal_plugin_hook, "plugin_display_name", lambda app=None: name)


class TestStartupPhaseSkipsTheLocalModel:
    def test_plugin_owner_skips_the_background_load(self, phase7_app, monkeypatch, caplog):
        _patch_owner(monkeypatch, "Claude STT")
        caplog.set_level(logging.INFO, logger="voice_typer.server.startup_sequence")

        result = _phase_7(phase7_app)

        assert result.success is True
        phase7_app.models.start_background_load.assert_not_called()
        assert "Claude STT serves dictation, skipping the local model load" in caplog.text

    def test_no_plugin_still_loads_the_local_model(self, phase7_app, monkeypatch):
        _patch_owner(monkeypatch, "")

        result = _phase_7(phase7_app)

        assert result.success is True
        phase7_app.models.start_background_load.assert_called_once()

    def test_ownership_probe_failure_falls_back_to_loading(self, phase7_app, monkeypatch):
        from voice_typer.server import internal_plugin_hook

        def _boom(app=None):
            raise RuntimeError("workspace unavailable")

        # The probe itself is the failing seam; it must answer "no plugin" and
        # leave the local model in charge instead of breaking startup.
        monkeypatch.setattr(internal_plugin_hook, "plugins_enabled", _boom)

        result = _phase_7(phase7_app)

        assert result.success is True
        phase7_app.models.start_background_load.assert_called_once()

    def test_completion_line_names_the_plugin_instead_of_a_fake_load(self, phase7_app, monkeypatch, caplog):
        _patch_owner(monkeypatch, "Claude STT")
        phase7_app.config.model_size = "parakeet-ultra"
        phase7_app.models._model_load_thread = None
        caplog.set_level(logging.INFO, logger="voice_typer.server.startup_sequence")

        _phase_8(phase7_app)

        assert "Claude STT serves dictation, no local model loaded" in caplog.text
        assert "model still loading in background" not in caplog.text

    def test_completion_moves_the_tray_off_the_startup_loading_state(self, phase7_app, monkeypatch):
        """Nothing else clears the startup LOADING state in plugin mode.

        ``app.start()`` raises LOADING ("starting") and the local background
        loader is its only clearer; with the load skipped, Home sat on
        "Loading"/"Loading model…" forever while no model was loading.
        """
        from voice_typer.server.tray_types import AppState

        _patch_owner(monkeypatch, "Claude STT")
        phase7_app.models._model_load_thread = None

        _phase_8(phase7_app)

        phase7_app.tray.set_state.assert_called_once()
        state, message = phase7_app.tray.set_state.call_args.args
        assert state is AppState.IDLE
        assert message == "Claude STT serves dictation"

    def test_local_model_startup_leaves_the_tray_alone(self, phase7_app, monkeypatch):
        """The plugin branch must not run for a local-model install."""
        from voice_typer.server.tray_types import AppState

        _patch_owner(monkeypatch, "")
        phase7_app.config.model_size = "large-v3"
        phase7_app.models._model_load_thread = None

        _phase_8(phase7_app)

        for call in phase7_app.tray.set_state.call_args_list:
            assert call.args[0] is not AppState.IDLE or call.args[1] != "Claude STT serves dictation"


class _LoadingStub:
    """``LoadingMixin`` host: the attributes ``start_background_load`` reads."""

    _model_load_thread: threading.Thread | None = None

    def __init__(self, app: MagicMock) -> None:
        self._app = app
        self._model_load_spawn_lock = threading.Lock()
        self._thread_registry = MagicMock()
        self.load_background = MagicMock()

    @property
    def thread(self) -> threading.Thread | None:
        return self._model_load_thread


class TestModelManagerGate:
    def test_background_load_is_skipped_while_a_plugin_owns_dictation(self, monkeypatch, caplog):
        _patch_owner(monkeypatch, "Claude STT")
        stub = _LoadingStub(MagicMock(name="app"))
        caplog.set_level(logging.INFO, logger="voice_typer.server.model_manager")

        LoadingMixin.start_background_load(stub)

        assert stub.thread is None
        stub.load_background.assert_not_called()
        stub._thread_registry.register.assert_not_called()
        assert "background load skipped: Claude STT serves dictation" in caplog.text

    def test_background_load_still_spawns_for_the_local_model(self, monkeypatch):
        _patch_owner(monkeypatch, "")
        stub = _LoadingStub(MagicMock(name="app"))
        done = threading.Event()
        stub.load_background = lambda: done.set()

        LoadingMixin.start_background_load(stub)

        assert done.wait(5.0), "the background loader never ran for the local model"
