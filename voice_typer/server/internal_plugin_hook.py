"""Internal-plugin STT seam. Ships as dead code, never active.

Single gated seam: ``install(app)`` wraps the product dictation entry
points (toggle / stop / cancel) so the in-development Google STT plugin
reuses the product hotkey, bubble, sound cues, clipboard and history
paths. Every call returns immediately unless
``internal_plugin_hook.plugins_enabled()`` is true (env flag +
tools/internal_plugins/PLUGINS_ENABLED + not frozen), so the shipped
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


def requested_plugin_id(app: Any | None = None) -> str:
    """The plugin the user selected in the Plugins page ("" = local model).

    Read from the running app's config; with no app (a CLI probe, a test)
    the answer is "" so the local model stays in charge.
    """
    config = getattr(app, "config", None)
    return str(getattr(config, "active_plugin", "") or "")


def internal_surface_enabled() -> bool:
    """Whether this install may show the Plugins UI at all.

    This is the VISIBILITY gate, and it is deliberately independent of
    ``active_plugin``: the UI has to be reachable in order to turn a plugin
    on in the first place.

    The discriminator is the plugin workspace, which is gitignored and never
    packaged (``.gitignore``: ``tools/internal_plugins/``). Only a developer
    running from source has it, so every shipped build answers False. The
    env flag is honoured as a second way in, for testing the surface without
    the workspace present.
    """
    import os
    import sys

    if bool(getattr(sys, "frozen", False)):
        return False
    if os.environ.get(ENV_FLAG) == "1":
        return True
    from voice_typer.server.plugins import plugins_dir

    return plugins_dir() is not None


def plugins_enabled(app: Any | None = None) -> bool:
    """Whether a plugin should own dictation right now.

    Fail-closed at every step: no selected plugin means the local model, a
    frozen build never imports the plugin, and the plugin's own gate (env +
    PLUGINS_ENABLED marker) has the final say so that switch stays the single
    source of truth.
    """
    import os
    import sys

    if requested_plugin_id(app) == "":
        return False
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
    if not plugins_enabled(app):
        return False
    if getattr(app, "_internal_plugin_wrapped", False):
        # Already wrapped: a second pass would nest the wrappers and handle
        # one key press twice.
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
    app._internal_plugin_wrapped = True
    log.info("[PLUGIN] dictation entry points routed to Google STT")
    return True
