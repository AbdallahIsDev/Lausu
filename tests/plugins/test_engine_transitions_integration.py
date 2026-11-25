"""Engine transitions through the REAL config handler and config object.

Only the browser/native edges (plugin daemon sync, tray OS calls) are faked.
Validation, allowlist, config application and the config_changed event use the
same production objects as the running sidecar.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest
from voice_typer.server.config import Config


@pytest.fixture
def real_ipc():
    from voice_typer.server.ipc_server import IPCServer
    from voice_typer.server.service import LausuService

    config = Config()
    config.model_size = "parakeet"
    config.asr_backend = "parakeet"
    config.active_plugin = "anthropic_stt"
    config.active_plugin_name = "Claude STT"
    app = MagicMock()
    app.config = config
    app._config_mutation_lock = threading.RLock()
    app.clipboard = MagicMock()
    app.tray = MagicMock()
    app.tray.set_state = MagicMock()
    app.hotkeys = MagicMock()
    app.recorder = MagicMock()
    app._busy_event = MagicMock()
    app._busy_event.is_set.return_value = True
    app._llm_polisher = None
    app._shutting_down = False
    service = LausuService(app)
    server = IPCServer(app, service)
    return server, app, config


def test_selecting_a_local_model_releases_the_plugin(real_ipc, monkeypatch):
    from voice_typer.server import internal_plugin_hook

    server, app, config = real_ipc
    synced: list[object] = []
    monkeypatch.setattr(
        internal_plugin_hook,
        "sync_selection",
        lambda target: synced.append(target) or True,
    )
    events: list[dict] = []
    monkeypatch.setattr(
        "voice_typer.server.handlers.config_handlers.event_bus.publish",
        lambda event: events.append(event),
    )

    resp = server._handle_set_config({"model_size": "parakeet", "asr_backend": "parakeet"}, {})

    assert resp["type"] == "ack"
    assert config.active_plugin == ""
    assert config.model_size == "parakeet"
    assert len(synced) == 1, "the plugin browser must be deactivated on the real path"
    assert events and events[-1]["data"]["active_plugin"] == ""
    assert events[-1]["data"]["active_plugin_name"] == ""


def test_enabling_a_plugin_keeps_the_selection_authoritative(real_ipc, monkeypatch):
    from voice_typer.server import internal_plugin_hook

    server, _app, config = real_ipc
    synced: list[object] = []
    monkeypatch.setattr(
        internal_plugin_hook,
        "sync_selection",
        lambda target: synced.append(target) or True,
    )
    monkeypatch.setattr(
        internal_plugin_hook,
        "plugin_display_name_for",
        lambda cfg: "Claude STT",
    )

    resp = server._handle_set_config({"active_plugin": "anthropic_stt"}, {})

    assert resp["type"] == "ack"
    assert config.active_plugin == "anthropic_stt"
    assert len(synced) == 1


def test_plugin_off_with_no_local_model_is_a_true_no_engine_state(real_ipc, monkeypatch):
    from voice_typer.server import internal_plugin_hook
    from voice_typer.server.tray_types import AppState

    server, app, config = real_ipc
    config.model_size = ""
    monkeypatch.setattr(
        internal_plugin_hook,
        "sync_selection",
        lambda target: True,
    )

    server._handle_set_config({"active_plugin": ""}, {})
    assert config.active_plugin == ""
    assert internal_plugin_hook.reconcile_status(app) is True
    state, message = app.tray.set_state.call_args.args
    assert state == AppState.IDLE
    assert "No model selected" in message


def test_local_only_changes_do_not_touch_plugin_ownership(real_ipc, monkeypatch):
    from voice_typer.server import internal_plugin_hook

    server, _app, config = real_ipc
    called: list[object] = []
    monkeypatch.setattr(internal_plugin_hook, "sync_selection", lambda target: called.append(target))

    server._handle_set_config({"hotkey": "<f4>"}, {})

    assert config.active_plugin == "anthropic_stt"
    assert called == []
