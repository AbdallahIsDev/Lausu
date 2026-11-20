"""Internal STT plugins must drive the SAME status authority as local dictation.

The sidebar dot and Home pill read ``recordingState``, which is written only by
``status_change``/``state_changed``/``get_status`` — all derived from
``app.tray.state``. A plugin that only publishes bubble events leaves that
authority at idle (owner report 2026-11-19).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tools.internal_plugins._common.status import set_cycle_state
from tools.internal_plugins.anthropic_stt import plugin as anthropic_plugin
from tools.internal_plugins.google_stt import plugin as google_plugin
from voice_typer.server.tray_types import AppState


def _app_with_tray() -> tuple[MagicMock, list[AppState]]:
    app = MagicMock()
    seen: list[AppState] = []

    def record(state: AppState, message: str = "") -> None:
        seen.append(state)
        app.tray.state = state

    app.tray.set_state.side_effect = record
    return app, seen


class TestSharedStatusAuthority:
    def test_maps_cycle_states_to_tray_states(self):
        app, seen = _app_with_tray()
        set_cycle_state(app, "recording")
        set_cycle_state(app, "transcribing")
        set_cycle_state(app, "error")
        set_cycle_state(app, "idle")
        assert seen == [
            AppState.RECORDING,
            AppState.TRANSCRIBING,
            AppState.ERROR,
            AppState.IDLE,
        ]

    def test_unknown_state_is_idle_and_never_raises(self):
        app, seen = _app_with_tray()
        set_cycle_state(app, "mystery")
        assert seen == [AppState.IDLE]
        app.tray.set_state.side_effect = RuntimeError("tray gone")
        set_cycle_state(app, "recording")  # must not raise


class TestAnthropicPluginStatus:
    def test_session_events_drive_recording_transcribing_idle(self):
        app, seen = _app_with_tray()
        session = anthropic_plugin.PluginSession(app)
        with patch("voice_typer.server.event_bus.publish"):
            session._session_events(start=True)
            session._publish_state("transcribing")
            session._session_events(start=False)
        assert seen == [AppState.RECORDING, AppState.TRANSCRIBING, AppState.IDLE]


class TestGooglePluginStatus:
    def test_start_and_stop_drive_the_same_authority(self):
        app, seen = _app_with_tray()
        session = google_plugin.PluginSession(app)
        session._active = True
        session._t0 = 0.0
        with patch("voice_typer.server.event_bus.publish"):
            session._session_events(start=True)
            with patch.object(
                google_plugin,
                "_post",
                return_value={"text": "", "duration_s": 0.0},
            ):
                session.stop()
        assert seen == [AppState.RECORDING, AppState.TRANSCRIBING, AppState.IDLE]
