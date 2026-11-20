"""Single bubble visibility policy + reality reconciliation (always_visible)."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from voice_typer.server.waveform import WaveformBubble


def _bubble(behavior: str) -> tuple[WaveformBubble, list]:
    bubble = WaveformBubble()
    bubble.set_behavior_provider(lambda: behavior)
    fired: list = []
    bubble.on_show = lambda: fired.append("show")
    bubble.on_hide = lambda: fired.append("hide")
    bubble.on_set_state = lambda state: fired.append(("state", state))
    return bubble, fired


class TestSinglePolicy:
    def test_always_visible_never_hides_in_any_state(self):
        for state in ("idle", "recording", "transcribing", "error", "paste_failed"):
            bubble, fired = _bubble("always_visible")
            bubble.apply_visibility(state, reason="test")
            assert fired == ["show", ("state", state)]
            assert bubble.visible is True

    def test_always_visible_reasserts_even_when_mirror_says_visible(self):
        bubble, fired = _bubble("always_visible")
        bubble.show()
        fired.clear()
        bubble.apply_visibility("idle", reason="host-reconcile")
        assert fired == ["show", ("state", "idle")], "stale mirror must not block re-assert"

    def test_show_on_record_shows_only_for_active_states(self):
        bubble, fired = _bubble("show_on_record")
        bubble.apply_visibility("recording", reason="test")
        assert fired == ["show", ("state", "recording")]
        fired.clear()
        bubble.apply_visibility("idle", reason="test")
        assert fired == ["hide"], "hidden transition pushes no state (unchanged behavior)"

    def test_hidden_mode_never_shows(self):
        for state in ("idle", "recording"):
            bubble, fired = _bubble("hidden")
            bubble.apply_visibility(state, reason="test")
            assert fired == ["hide"]
            assert bubble.visible is False

    def test_host_hide_reconciles_and_restores_always_visible(self):
        bubble, fired = _bubble("always_visible")
        bubble.show()
        fired.clear()
        # Host hid the real window behind the backend's back.
        bubble.note_host_hidden(reason="host-dismiss")
        assert "show" in fired, "always_visible must come back after a host hide"

    def test_host_hide_respects_show_on_record(self):
        bubble, fired = _bubble("show_on_record")
        bubble.apply_visibility("recording", reason="test")
        fired.clear()
        bubble.note_host_hidden(reason="host-dismiss")
        # recording is an active state: the host hide must be undone.
        assert "show" in fired


class TestStartupRetry:
    def test_flag_not_consumed_when_app_not_ready(self):
        from voice_typer.server.sidecar_ws_internals import connection as conn

        server = SimpleNamespace(_lock=threading.RLock(), app=None)
        assert conn._emit_bubble_startup_show(server) is False
        assert getattr(server, "_bubble_startup_show_done", False) is False

        bubble, _ = _bubble("always_visible")
        bubble.on_config = lambda cfg: None
        server.app = SimpleNamespace(
            config=SimpleNamespace(bubble_behavior="always_visible", bubble_show_on_startup=True),
            _waveform_bubble=bubble,
        )
        assert conn._emit_bubble_startup_show(server) is True
        assert conn._emit_bubble_startup_show(server) is False

    def test_phase8_reasserts_when_mirror_is_stale(self):
        bubble, fired = _bubble("always_visible")
        bubble.on_config = lambda cfg: None
        bubble.show()  # mirror says visible, real window may be hidden
        fired.clear()
        from voice_typer.server.startup_sequence import StartupSequence

        config = SimpleNamespace(
            bubble_x=None,
            bubble_y=None,
            bubble_behavior="always_visible",
            bubble_show_on_startup=True,
            model_size="tiny",
            save=MagicMock(),
        )
        app = MagicMock()
        app.config = config
        app._waveform_bubble = bubble
        app.models = SimpleNamespace(_model_load_thread=SimpleNamespace(is_alive=lambda: False))
        app._shutting_down = False
        seq = StartupSequence(app)
        seq._t0 = 0.0
        seq._phase_8_finalize_and_signal()
        assert "show" in fired


class TestProviderNeutrality:
    def test_plugin_stop_routes_through_policy_without_raw_hide(self):
        from tools.internal_plugins._common.bridge import session as plugin_session

        bubble = MagicMock()
        app = MagicMock()
        app._waveform_bubble = bubble
        session = plugin_session.PluginSession(app)
        session._copy = MagicMock(MODEL_LABEL="test")
        with patch("voice_typer.server.event_bus.publish") as publish:
            session._session_events(start=False)
        bubble.apply_visibility.assert_called_once_with("idle", reason="plugin-stop")
        published = [c.args[0]["type"] for c in publish.call_args_list if c.args]
        assert "bubble_hide" not in published
        assert "bubble_show" not in published

    def test_plugin_start_routes_through_policy(self):
        from tools.internal_plugins._common.bridge import session as plugin_session

        bubble = MagicMock()
        app = MagicMock()
        app._waveform_bubble = bubble
        session = plugin_session.PluginSession(app)
        session._copy = MagicMock(MODEL_LABEL="test")
        with patch("voice_typer.server.event_bus.publish"):
            session._session_events(start=True)
        bubble.apply_visibility.assert_called_once_with("recording", reason="plugin-start")


class TestHostHiddenCommand:
    def test_handler_notifies_coordinator(self):
        from voice_typer.server.ipc_server import IPCServer

        bubble = MagicMock()
        app = MagicMock()
        app._waveform_bubble = bubble
        server = IPCServer.__new__(IPCServer)
        server.app = app
        resp = server._handle_bubble_host_hidden({"reason": "host-dismiss"}, {})
        assert resp["type"] == "result"
        bubble.note_host_hidden.assert_called_once_with(reason="host-dismiss")
