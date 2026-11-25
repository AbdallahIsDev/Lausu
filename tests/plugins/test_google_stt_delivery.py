"""Google STT delivery mirrors the canonical paste step.

The separating space reaches ONLY the clipboard copy and paste keystroke;
history, crash recovery and ``transcription_final`` keep the decoded text
byte-identical (C-TRANS-2). The bubble is driven by a real measured level
meter, never a hardcoded ``bubble_level`` payload (C-UI-15).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tools.internal_plugins.google_stt import plugin as google_plugin
from voice_typer.server import event_bus
from voice_typer.server.clipboard_target_safety import caret_text


@pytest.fixture(autouse=True)
def _quiet_event_bus(monkeypatch: pytest.MonkeyPatch):
    published: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event))
    return published


def _make_app() -> SimpleNamespace:
    app = SimpleNamespace()
    app.config = SimpleNamespace(device="cpu", language="en")
    app.clipboard = MagicMock()
    app.clipboard.copy.return_value = None
    app.clipboard._clipboard_seq = 42
    app.clipboard.paste.return_value = True
    app.history_db = MagicMock()
    app.history_db.add_transcription.return_value = 7
    app._last_transcription = None
    return app


class TestGoogleDeliverySeparator:
    def test_separator_reaches_paste_but_not_history(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(caret_text, "_char_before_caret", lambda: "existing text")
        app = _make_app()

        google_plugin.PluginSession(app)._deliver("dictated words", 2.5)

        app.clipboard.copy.assert_called_once_with(" dictated words")
        assert app.clipboard.paste.call_args.kwargs["pasted_text"] == " dictated words"
        app.history_db.add_transcription.assert_called_once()
        assert app.history_db.add_transcription.call_args.args[0] == "dictated words"
        assert app._last_transcription == "dictated words"

    def test_empty_field_pastes_capitalized_without_a_space(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(caret_text, "_char_before_caret", lambda: "")
        app = _make_app()

        google_plugin.PluginSession(app)._deliver("dictated words", 2.5)

        app.clipboard.copy.assert_called_once_with("Dictated words")
        assert app.history_db.add_transcription.call_args.args[0] == "dictated words"

    def test_caret_probe_failure_still_delivers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _raise() -> str:
            raise RuntimeError("UIA unreachable")

        monkeypatch.setattr(caret_text, "_char_before_caret", _raise)
        app = _make_app()

        google_plugin.PluginSession(app)._deliver("dictated words", 2.5)

        app.clipboard.copy.assert_called_once_with("dictated words")
        app.clipboard.paste.assert_called_once()
        assert app.history_db.add_transcription.call_args.args[0] == "dictated words"


class TestGoogleBubbleLevels:
    def test_start_uses_a_measured_level_meter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The hardcoded level publisher is gone; a meter measures the mic."""
        meters: list[object] = []

        class FakeMeter:
            def __init__(self, app: object) -> None:
                self.app = app
                self.started = False
                meters.append(self)

            def start(self) -> None:
                self.started = True

            def stop(self) -> None:
                pass

        monkeypatch.setattr(google_plugin, "LevelMeter", FakeMeter)
        monkeypatch.setattr(google_plugin, "ensure_daemon", lambda: True)
        monkeypatch.setattr(google_plugin, "_post", lambda path, timeout=None: {})
        monkeypatch.setattr(
            google_plugin, "_daemon_status",
            lambda: {"browser": "connected", "page": "ok", "platform": "gemini", "micCount": 1, "selectorsReady": True},
        )
        app = _make_app()
        session = google_plugin.PluginSession(app)
        monkeypatch.setattr(session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(session, "_duck", lambda: None)

        session.start()

        assert len(meters) == 1, "Google must start the shared measured level meter"
        assert meters[0].started
        assert not hasattr(google_plugin, "_mute_bubble_levels"), (
            "the hardcoded bubble_level publisher must be deleted, not left dormant"
        )

    def test_stop_and_deliver_uses_stop_time_snapshot_before_post_stop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = _make_app()
        session = google_plugin.PluginSession(app)
        session._active = True
        session._t0 = 1.0
        session._cycle = 1
        monkeypatch.setattr(session, "_stop_meter", lambda: None)
        monkeypatch.setattr(session, "_publish_state", lambda _s: None)
        monkeypatch.setattr(session, "_restore_volume", lambda: None)
        monkeypatch.setattr(session, "_session_events", lambda *, start: None)
        monkeypatch.setattr(session, "_clear_prompt_box", lambda: None)

        state = {"caret": ""}
        monkeypatch.setattr(caret_text, "_char_before_caret", lambda: state["caret"])

        def _post(path: str, timeout: float = 0.0) -> dict:
            assert path == "/stop"
            # Caret changes while waiting for page transcript scrape.
            state["caret"] = "unexpected window"
            return {"text": "dictated words", "duration_s": 1.5}

        monkeypatch.setattr(session, "_post", _post)

        session.stop()

        app.clipboard.copy.assert_called_once_with("Dictated words")
        paste_kwargs = app.clipboard.paste.call_args.kwargs
        assert paste_kwargs["pasted_text"] == "Dictated words"
        assert paste_kwargs["target_snapshot"].prefix_context.verdict == "empty"
        assert app.history_db.add_transcription.call_args.args[0] == "dictated words"
