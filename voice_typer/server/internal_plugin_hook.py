"""Internal-plugin STT seam. Ships as dead code, never active.

Single gated seam: ``install(app)`` wraps the product dictation entry
points (toggle / stop / cancel) so the plugin selected in ``config``
reuses the product hotkey, bubble, sound cues, clipboard and history
paths. Every call falls through to the original product method unless
``internal_plugin_hook.plugins_enabled(app)`` is true (selected plugin +
workspace/env opt-in + PLUGINS_ENABLED marker + not frozen), so the
shipped build behaves exactly as before.

The selection is resolved on EVERY press, not at install time: the Pages
UI writes ``active_plugin`` through ``set_config`` and the very next
hotkey uses it, with no restart. The wrappers are only installed when the
developer-only plugin surface exists at all (``internal_surface_enabled``),
which a frozen/shipped build never satisfies.

Why instance-level wrapping: the hotkey backends capture bound methods
at registration time, so patching after ``HotkeyDispatcher.__init__``
(the wiring-only call site in ``app.py``) intercepts every later press,
including remaps, PTT release, ESC cancel and tray/API calls.

Which plugin runs is ``config.active_plugin``; an id with no entry in
``PLUGIN_MODULES`` selects nothing and the local model stays in charge.
Plan: docs/plan-internal-plugin-google-stt.md.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

log = logging.getLogger("voice_typer.server.internal_plugin_hook")

ENV_FLAG = "VOICE_TYPER_INTERNAL_PLUGINS"

# Plugin id (as declared in plugin.json) -> the module that owns its session.
# Adding a plugin means adding a manifest directory AND one line here; an
# unknown id deliberately resolves to nothing so the gate fails closed.
PLUGIN_MODULES = {
    "google_stt": "tools.internal_plugins.google_stt.plugin",
    "anthropic_stt": "tools.internal_plugins.anthropic_stt.plugin",
}


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

    The discriminator is the plugin workspace. Its source is tracked in the
    repository (visible for review), but every packaging input excludes it,
    so a built app never contains it and answers False. The env flag is
    honoured as a second way in, for testing the surface without the
    workspace present.
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

    Fail-closed at every step: no selected plugin means the local model, an
    unknown id has no module, a frozen build never imports the plugin, and
    the plugin's own gate (PLUGINS_ENABLED marker + not frozen) has the final
    say so that switch stays the single source of truth.

    The VISIBILITY gate is reused here on purpose. It used to require
    ``VOICE_TYPER_INTERNAL_PLUGINS=1`` on top of everything else, and nothing
    in the repo ever set that variable — so a developer with the workspace
    present could switch a plugin to Active in the UI and still get the local
    model on every hotkey press. The workspace (tracked source, never
    packaged) plus the plugin's own marker are already deliberate opt-ins.
    """
    if requested_plugin_id(app) == "":
        return False
    if not internal_surface_enabled():
        return False
    plugin = _plugin(app)
    return bool(plugin is not None and plugin.plugins_enabled())


def _plugin_for(plugin_id: str) -> Any | None:
    module_path = PLUGIN_MODULES.get(plugin_id)
    if module_path is None:
        return None
    try:
        import importlib
        import sys
        from pathlib import Path

        root = str(Path(__file__).resolve().parents[2])
        if root not in sys.path:
            sys.path.insert(0, root)
        return importlib.import_module(module_path)
    except Exception:
        log.warning("[PLUGIN] import failed for %s", plugin_id, exc_info=True)
        return None


def _plugin(app: Any | None = None) -> Any | None:
    return _plugin_for(requested_plugin_id(app))


def _selected_session(app: Any) -> Any | None:
    """The session belonging to the CURRENT selection, or None for local STT."""
    if not plugins_enabled(app):
        return None
    plugin = _plugin(app)
    if plugin is None:
        return None
    return plugin.attach(app)


def _shutdown_plugin_daemon(plugin_id: str) -> None:
    """Best-effort: close the plugin we just switched away from.

    Both plugins drive the SAME Chrome profile, so leaving the old browser
    open would make the next start fail as ``profile-busy``. A plugin without
    the hook (or an already-dead daemon) is not an error.
    """
    plugin = _plugin_for(plugin_id)
    shutdown = getattr(plugin, "shutdown_daemon", None)
    if not callable(shutdown):
        return
    try:
        shutdown()
    except Exception:
        log.debug("[PLUGIN] %s daemon shutdown failed", plugin_id, exc_info=True)


def _switch_away(app: Any, session: Any, next_id: str) -> None:
    """Abandon whatever the previous selection was doing, without pasting."""
    previous_id = str(getattr(app, "_internal_plugin_active_id", "") or "")
    if session is not None and session.active:
        session.cancel()
    if previous_id and previous_id != next_id:
        _shutdown_plugin_daemon(previous_id)


def plugin_display_name_for(config: Any | None) -> str:
    """Plugin name for a bare ``Config`` (no app needed).

    Used by ``get_config`` and the tray, both of which only hold the config.
    Returns "" when the local model owns dictation, so every caller keeps
    showing the model name in that case.
    """
    plugin_id = str(getattr(config, "active_plugin", "") or "")
    if not plugin_id or not internal_surface_enabled():
        return ""
    plugin = _plugin_for(plugin_id)
    if plugin is None or not plugin.plugins_enabled():
        return ""
    return str(getattr(plugin, "DISPLAY_NAME", "") or "")


def plugin_display_name(app: Any | None = None) -> str:
    """Name of the plugin that owns dictation ("" = the local model does).

    The sidebar caption and the tray menu show this instead of the local
    model name while a plugin is selected: the model is not what is
    transcribing.
    """
    if not plugins_enabled(app):
        return ""
    plugin = _plugin(app)
    return str(getattr(plugin, "DISPLAY_NAME", "") or "")


def sync_selection(app: Any) -> bool:
    """Bring the selected plugin's browser up, or tear the old one down.

    Called when ``active_plugin`` changes and once at startup. Selecting a
    plugin has to have an immediate, visible effect — the browser window
    opens (per the plugin's own ``visible`` setting) instead of waiting for
    the first hotkey press. Idempotent: syncing the same selection twice
    does nothing.
    """
    if not internal_surface_enabled():
        return False
    plugin_id = requested_plugin_id(app)
    previous = str(getattr(app, "_internal_plugin_selected_id", "") or "")
    if previous == plugin_id:
        return False
    app._internal_plugin_selected_id = plugin_id
    if previous:
        _deactivate_plugin(previous)
    if not plugin_id:
        return True
    return _activate_plugin(plugin_id, app)


def _activate_plugin(plugin_id: str, app: Any) -> bool:
    plugin = _plugin_for(plugin_id)
    activate = getattr(plugin, "activate", None) if plugin is not None else None
    if not callable(activate):
        return False
    try:
        return bool(activate(app))
    except Exception:
        log.warning("[PLUGIN] %s activation failed", plugin_id, exc_info=True)
        return False


def _deactivate_plugin(plugin_id: str) -> None:
    """Stop the plugin we just switched away from, browser included."""
    plugin = _plugin_for(plugin_id)
    if plugin is None:
        return
    fn = getattr(plugin, "deactivate", None)
    if callable(fn):
        try:
            fn()
        except Exception:
            log.debug("[PLUGIN] %s deactivate failed", plugin_id, exc_info=True)
        return
    _shutdown_plugin_daemon(plugin_id)


def install(app: Any) -> bool:
    """Wrap the product dictation entry points when the surface exists."""
    if not internal_surface_enabled():
        return False
    if getattr(app, "_internal_plugin_wrapped", False):
        # Already wrapped: a second pass would nest the wrappers and handle
        # one key press twice.
        return False
    orig_toggle = app.toggle_dictation
    orig_stop = app._stop_dictation
    orig_cancel = app._cancel_dictation

    def toggle_dictation() -> None:
        session = _selected_session(app)
        previous = getattr(app, "_internal_plugin_active_session", None)
        plugin_id = requested_plugin_id(app) if session is not None else ""
        if session is previous and session is not None:
            session.toggle()
            return
        # Selection changed (or was cleared) since the last press: stop the
        # old owner first so two sessions can never run at once.
        if previous is not None:
            _switch_away(app, previous, plugin_id)
        app._internal_plugin_active_session = session
        app._internal_plugin_active_id = plugin_id
        if session is None:
            orig_toggle()
        else:
            session.toggle()

    def stop_dictation() -> None:
        # Route to the session that OWNS the in-flight cycle, not to the
        # current selection: switching mid-recording must not orphan it.
        session = getattr(app, "_internal_plugin_active_session", None)
        # Push-to-talk releases the key while the browser/daemon handshake may
        # still be running, so "owns the cycle" includes a start in flight --
        # otherwise the release fell through to the local recorder and the
        # platform kept listening forever.
        owns = getattr(session, "owns_cycle", None) if session is not None else None
        if owns is None and session is not None:
            owns = session.active
        if session is not None and owns:
            session.stop()
        else:
            orig_stop()

    def cancel_dictation() -> None:
        session = getattr(app, "_internal_plugin_active_session", None)
        if session is None or not session.cancel():
            orig_cancel()

    app.toggle_dictation = toggle_dictation
    app._stop_dictation = stop_dictation
    app._cancel_dictation = cancel_dictation
    app._internal_plugin_wrapped = True
    log.info("[PLUGIN] dictation entry points installed; selection resolved per press")
    # A selection made in a previous run must survive the restart: activating
    # a plugin was the user's decision, and the browser should be up without
    # them having to press the hotkey first. Off-thread so a slow Chrome boot
    # never delays startup.
    threading.Thread(
        target=sync_selection,
        args=(app,),
        name="plugin-startup-sync",
        daemon=True,
    ).start()
    return True
