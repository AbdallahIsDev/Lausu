"""One active engine on the server: plugin, local model, or none (Item 6)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from voice_typer.server.tray_types import AppState


def test_plugin_tooltip_drops_the_state_and_model_segments(monkeypatch):
    from voice_typer.server import internal_plugin_hook
    from voice_typer.server.tray import TrayIcon

    monkeypatch.setattr(internal_plugin_hook, "plugin_display_name_for", lambda cfg: "Claude STT")
    monkeypatch.setattr(
        "voice_typer.server.tray_models.is_active_model_downloaded",
        lambda cfg: True,
    )
    cfg = SimpleNamespace(hotkey="<caps_lock>", asr_backend="parakeet", model_size="")
    tray = TrayIcon(controller=MagicMock(), config=cfg)
    tray._cpu_fallback_active = False

    tooltip = tray._compute_tooltip(AppState.IDLE, "")

    assert "Ready" not in tooltip
    assert "Parakeet" not in tooltip
    assert "Claude STT" in tooltip
    assert tooltip.count(" | ") == 2, tooltip


def test_startup_reconciles_even_when_a_load_is_in_flight(monkeypatch):
    from voice_typer.server import internal_plugin_hook
    from voice_typer.server.startup_sequence import _phases_late
    from voice_typer.server.tray_types import AppState

    monkeypatch.setattr(internal_plugin_hook, "plugin_display_name", lambda app: "Claude STT")
    app = MagicMock()
    app.config.model_size = ""
    app.models._model_load_thread = SimpleNamespace(is_alive=lambda: True)
    phase = SimpleNamespace(_app=app, _t0=0.0)

    _phases_late.LatePhases._phase_8_finalize_and_signal(phase)

    state, message = app.tray.set_state.call_args.args
    assert state is AppState.IDLE
    assert "Claude STT" in message


def test_hotkey_with_no_engine_is_refused_and_notified(monkeypatch):
    from voice_typer.server import event_bus, internal_plugin_hook
    from voice_typer.server.hotkey_dispatch import HotkeyDispatchMixin

    monkeypatch.setattr(internal_plugin_hook, "plugin_display_name", lambda app: "")
    published: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", lambda payload: published.append(payload))
    app = SimpleNamespace(
        config=SimpleNamespace(model_size="", asr_backend="whisper", recording_mode="toggle"),
        tray=MagicMock(),
    )
    dispatcher = HotkeyDispatchMixin()
    dispatcher._app = app

    assert dispatcher._no_active_engine() is True
    app.tray.notify.assert_called_once()
    assert published and published[0]["type"] == "notification"
