"""An unconfirmed auto-paste must tell the user where the text went.

``SendInput`` returning 0 (or the pynput fallback landing unverified) left
the transcript on the clipboard with no visible signal at all, so the
dictation silently never appeared in the target app.
"""

from __future__ import annotations

from tests.fixtures.clipboard_helpers import make_clipboard_manager


class TestUnconfirmedDispatchSignals:
    def test_publishes_paste_deferred(self, monkeypatch):
        published: list = []
        monkeypatch.setattr("voice_typer.server.event_bus.publish", published.append)

        make_clipboard_manager()._settle_pending_restore(("pending",), dispatched_ok=False)

        assert {"type": "paste_deferred", "data": {"reason": "delivery_unconfirmed"}} in published

    def test_no_pending_entry_means_no_signal(self, monkeypatch):
        published: list = []
        monkeypatch.setattr("voice_typer.server.event_bus.publish", published.append)

        make_clipboard_manager()._settle_pending_restore(None, dispatched_ok=False)

        assert published == []
