"""No-model start refusal at the shared entry, not just the hotkey guard.

REAL-PATH TEST RULE: enters through ``app.toggle_dictation`` with a real
button origin; only the OS/process boundary (recorder, tray, event bus sink)
is faked. Live bug: 2026-11-27 18:37 a no-model press opened the microphone.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from voice_typer.server import dictation_origin, event_bus, i18n


def test_no_model_button_press_is_refused_before_the_microphone_opens(app, monkeypatch):
    app.config.model_size = ""
    app.config.asr_backend = "parakeet"
    app.config.active_plugin = ""
    app.recorder = MagicMock()
    app.recorder.recording = False
    app.tray = MagicMock()
    published: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event))

    with dictation_origin.user_action("button"):
        app.toggle_dictation()

    app.recorder.start.assert_not_called()
    app.tray.notify.assert_called_once_with(i18n.t("notify.model_manager.no_model_selected"))
    assert any(event.get("type") == "notification" for event in published)
