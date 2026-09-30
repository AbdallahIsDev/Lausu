"""Owner Gemini web-STT integration hook. Ships as dead code, never active.

Single gated seam: ``install(app)`` wraps the product dictation entry
points (toggle / stop / cancel) so the owner Gemini session reuses the
product hotkey, bubble, sound cues, clipboard and history paths. Every
call returns immediately unless ``owner_plugin.owner_enabled()`` is true
(env flag + tools/owner/OWNER_ENABLED + not frozen), so the shipped
build behaves exactly as before.

Why instance-level wrapping: the hotkey backends capture bound methods
at registration time, so patching after ``HotkeyDispatcher.__init__``
(the wiring-only call site in ``app.py``) intercepts every later press,
including remaps, PTT release, ESC cancel and tray/API calls.

Plan: docs/plan-owner-gemini-web-stt.md §14.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("owner.gemini_stt.hook")


def owner_enabled() -> bool:
    """Cheap pre-check, then defer to the plugin's own gate.

    The env + frozen test runs first so a shipped build never imports
    tools/owner at all; the OWNER_ENABLED marker is judged by the plugin so
    the gate has exactly one source of truth.
    """
    import os
    import sys

    if os.environ.get("VOICE_TYPER_OWNER_TOOLS") != "1":
        return False
    if bool(getattr(sys, "frozen", False)):
        return False
    plugin = _plugin()
    return bool(plugin is not None and plugin.owner_enabled())


def _plugin() -> Any | None:
    try:
        import importlib
        import sys
        from pathlib import Path

        root = str(Path(__file__).resolve().parents[2])
        if root not in sys.path:
            sys.path.insert(0, root)
        return importlib.import_module("tools.owner.gemini_stt.plugin")
    except Exception:
        log.warning("[OWNER] plugin import failed", exc_info=True)
        return None


def install(app: Any) -> bool:
    """Wrap product dictation entry points when the owner gate is open."""
    if not owner_enabled():
        return False
    plugin = _plugin()
    if plugin is None:
        return False
    session = plugin.attach(app)
    if session is None:
        return False

    orig_stop = app._stop_dictation
    orig_cancel = app._cancel_dictation

    def toggle_dictation() -> None:
        # Owner mode replaces local STT wholesale: the session owns both
        # edges of the toggle, so the product path is never reached here.
        session.toggle()

    def stop_dictation() -> None:
        if session.active:
            session.stop()
        else:
            orig_stop()

    def cancel_dictation() -> None:
        if not session.cancel():
            orig_cancel()

    app.toggle_dictation = toggle_dictation
    app._stop_dictation = stop_dictation
    app._cancel_dictation = cancel_dictation
    log.info("[OWNER] dictation entry points routed to Gemini web-STT")
    return True
