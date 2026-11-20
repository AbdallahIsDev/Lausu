"""Plugin delivery: the separating space reaches the paste, never the history row.

The plugin path (Anthropic STT) mirrors the local pipeline's paste step: the
clipboard copy and the paste keystroke carry the padded text, while
``history_db.add_transcription``, ``_last_transcription`` and the
``transcription_final`` payload keep the transcript exactly as returned.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tools.internal_plugins.anthropic_stt import plugin as plugin_module
from voice_typer.server import event_bus
from voice_typer.server.clipboard_target_safety import caret_text


@pytest.fixture()
def caret(monkeypatch: pytest.MonkeyPatch):
    """Control the text in front of the caret."""

    def _set(value: str | None) -> None:
        monkeypatch.setattr(caret_text, "_char_before_caret", lambda: value)

    return _set


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


def _deliver(app: SimpleNamespace, text: str) -> None:
    plugin_module.PluginSession(app)._deliver(text, 2.5)


class TestPluginSeparator:
    def test_paste_carries_one_space_while_history_keeps_the_text(self, caret, _quiet_event_bus):
        caret("existing text")
        app = _make_app()
        _deliver(app, "dictated words")

        app.clipboard.copy.assert_called_once_with(" dictated words")
        assert app.clipboard.paste.call_args.kwargs["pasted_text"] == " dictated words"
        app.history_db.add_transcription.assert_called_once()
        assert app.history_db.add_transcription.call_args.args[0] == "dictated words"
        assert app._last_transcription == "dictated words"
        finals = [e for e in _quiet_event_bus if e["type"] == "transcription_final"]
        assert finals == [{"type": "transcription_final", "data": {"text": "dictated words"}}]

    def test_empty_field_capitalizes_paste_but_not_stored_text(self, caret, _quiet_event_bus):
        """C-TRANS-2: case is delivery-only on the plugin path too."""
        caret("")
        app = _make_app()
        _deliver(app, "Hello there")

        app.clipboard.copy.assert_called_once_with("Hello there")
        app.history_db.add_transcription.assert_called_once()
        assert app.history_db.add_transcription.call_args.args[0] == "Hello there"
        assert app._last_transcription == "Hello there"
        finals = [e for e in _quiet_event_bus if e["type"] == "transcription_final"]
        assert finals == [{"type": "transcription_final", "data": {"text": "Hello there"}}]

    def test_empty_field_pastes_capitalized_without_a_space(self, caret):
        caret("")
        app = _make_app()
        _deliver(app, "dictated words")

        app.clipboard.copy.assert_called_once_with("Dictated words")
        assert app.clipboard.paste.call_args.kwargs["pasted_text"] == "Dictated words"
        assert app.history_db.add_transcription.call_args.args[0] == "dictated words"

    def test_trailing_space_pastes_as_is(self, caret):
        caret("already spaced ")
        app = _make_app()
        _deliver(app, "dictated words")

        app.clipboard.copy.assert_called_once_with("dictated words")

    def test_unknown_caret_context_fails_open(self, caret):
        caret(None)
        app = _make_app()
        _deliver(app, "dictated words")

        app.clipboard.copy.assert_called_once_with("dictated words")

    def test_caret_probe_failure_still_pastes(self, caret, monkeypatch):
        """A broken caret reader must not cost the user the paste."""

        def _raise():
            raise RuntimeError("UIA unreachable")

        monkeypatch.setattr(caret_text, "_char_before_caret", _raise)
        app = _make_app()
        _deliver(app, "dictated words")

        app.clipboard.copy.assert_called_once_with("dictated words")
        app.clipboard.paste.assert_called_once()
        assert app.history_db.add_transcription.call_args.args[0] == "dictated words"
