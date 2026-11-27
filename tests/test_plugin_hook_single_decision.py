"""Live bug guard: local fallback with the plugin hook installed.

REAL-PATH TEST RULE: enters through the wrapped ``app.toggle_dictation`` with
a real origin context and the real dictation gate; only plugin/browser modules
are stubbed at the process boundary.
"""

from __future__ import annotations

from voice_typer.server import dictation_origin

from tests.plugins.test_user_initiated_start import _installed_app


def test_local_fallback_decides_the_gate_once(monkeypatch) -> None:
    events: list[str] = []
    # No plugin selected: the wrapper must fall through to the local entry,
    # which decides the gate itself. A second decision here was an
    # ignore-burst and swallowed every press (live log 2026-11-27 17:56).
    app = _installed_app(monkeypatch, plugin_id="", events=events)

    with dictation_origin.user_action("hotkey"):
        app.toggle_dictation()

    assert events == ["local:toggle"], events
