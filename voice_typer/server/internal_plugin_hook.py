"""Internal-plugin STT seam. Ships as dead code, never active.

Single gated seam: ``install(app)`` wraps the product dictation entry
points (toggle / stop / cancel) so the in-development Google STT plugin
reuses the product hotkey, bubble, sound cues, clipboard and history
paths. Every call returns immediately unless
``internal_plugin_hook.plugins_enabled()`` is true (env flag +
tools/internal-plugins/PLUGINS_ENABLED + not frozen), so the shipped
build behaves exactly as before.

Why instance-level wrapping: the hotkey backends capture bound methods
at registration time, so patching after ``HotkeyDispatcher.__init__``
(the wiring-only call site in ``app.py``) intercepts every later press,
including remaps, PTT release, ESC cancel and tray/API calls.

Plan: docs/plan-internal-plugin-google-stt.md.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("voice_typer.server.internal_plugin_hook")

ENV_FLAG = "VOICE_TYPER_INTERNAL_PLUGINS"
PLUGIN_MODULE = "tools.internal_plugins.google_stt.plugin"


def plugins_enabled() -> bool:
    """Cheap pre-check, then defer to the plugin's own gate.

    The env + frozen test runs first so a shipped build never imports
    tools/internal-plugins at all; the PLUGINS_ENABLED marker is judged
    by the plugin so the gate has exactly one source of truth.
    """
    import os
    import sys

    if os.environ.get(ENV_FLAG) != "1":
        return False
    if bool(getattr(sys, "frozen", False)):
        return False
    plugin = _plugin()
    return bool(plugin is not None and plugin.plugins_enabled())


def _plugin() -> Any | None:
    try:
        import importlib
        import sys
        from pathlib import Path

        root = str(Path(__file__).resolve().parents[2])
        if root not in sys.path:
            sys.path.insert(0, root)
        return importlib.import_module(PLUGIN_MODULE)
    except Exception:
        log.warning("[PLUGIN] import failed", exc_info=True)
        return None


def install(app: Any) -> bool:
    """Wrap product dictation entry points when the plugin gate is open."""
    if not plugins_enabled():
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
        # Plugin mode replaces local STT wholesale: the session owns both
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
    log.info("[PLUGIN] dictation entry points routed to Google STT")
    return True
