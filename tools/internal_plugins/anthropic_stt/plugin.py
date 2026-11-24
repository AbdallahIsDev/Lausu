"""Internal Anthropic STT plugin - entry module.

Bundled but gated: ``voice_typer/server/internal_plugin_hook.py`` loads this
module only when ``plugins_enabled()`` is true (the plugin workspace's
PLUGINS_ENABLED marker, written by developer mode). This file is wiring only.
The HTTP client, keepalive, browser readiness and dictation state machine live
in focused siblings; the shared daemon/delivery/level-meter helpers live under
``tools/internal_plugins/_common``.

Everything here that a test or tool patches at module level (``_post``,
``_daemon_status``, ``_daemon_config``, ``launch_profile``, ``_last_launch_ts``,
``ensure_daemon``, ``attach``) stays a real module attribute. ``session.py``
resolves its callables through ``bind_entry`` so those patches reach the logic.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any

from tools.internal_plugins._common import daemon as _daemon_common
from tools.internal_plugins._common.bridge import daemon_client, session
from tools.internal_plugins._common.bridge.chrome_profile import (
    launch as _launch_chrome,
    resolve_browser_pids as _browser_pids,
)
from tools.internal_plugins._common.bridge.install_paths import profile_dir as _profile_dir
from tools.internal_plugins._common.bridge.keepalive import (
    _KEEPALIVE_INTERVAL_S,
    BridgeKeepalive as _BridgeKeepalive,
)
from tools.internal_plugins._common.daemon import (
    BridgeError,
    daemon_env as _daemon_env,
    node_deps_root as _node_deps_root,
    node_exe as _node_exe,
)
from tools.internal_plugins._common.delivery import deliver_transcription
from tools.internal_plugins._common.level_meter import LevelMeter, _meter_device
from tools.internal_plugins.anthropic_stt import copy as _copy

__all__ = [
    "BridgeError",
    "BridgeKeepalive",
    "LevelMeter",
    "PluginSession",
    "_KEEPALIVE_INTERVAL_S",
    "_daemon_config",
    "_daemon_env",
    "_daemon_status",
    "_dur",
    "_meter_device",
    "_ms",
    "_node_deps_root",
    "_node_exe",
    "_notify_enabled",
    "_post",
    "_START_HINTS",
    "deliver_transcription",
]

HERE = Path(__file__).resolve().parent
PLUGINS_DIR = HERE.parent
_BRIDGE_DIR = PLUGINS_DIR / "_common" / "bridge"

# Re-exports: every symbol that used to live here keeps resolving. One shared
# client instance, configured with this plugin's platform descriptor.
_CLIENT = daemon_client.DaemonClient(
    "ANTHROPIC_STT_URL",
    "Anthropic STT bridge",
    config_dir=str(HERE),
    daemon_script=str(_BRIDGE_DIR / "run.js"),
    daemon_cwd=str(_BRIDGE_DIR),
    daemon_args=(f"--plugin-dir={HERE}", "--platform=claude"),
)
DAEMON_URL = _CLIENT.url
_post = _CLIENT.post
_daemon_status = _CLIENT.status
_daemon_alive = _CLIENT.alive
_daemon_config = _CLIENT.config
_bridge_ready = daemon_client.DaemonClient.bridge_ready
_browser_connected = daemon_client.DaemonClient.browser_connected
class PluginSession(session.PluginSession):
    """The shared state machine bound to Anthropic's copy and platform."""

    def __init__(self, app: Any, **kwargs: Any) -> None:
        kwargs.setdefault("entry", sys.modules[__name__])
        kwargs.setdefault("client", _CLIENT)
        kwargs.setdefault("copy_mod", _copy)
        kwargs.setdefault("log", log)
        super().__init__(app, **kwargs)


_dur = _copy.duration
_ms = _copy.millis
_notify_enabled = _copy.notify_enabled
_START_HINTS = _copy.START_HINTS
_MODEL_LABEL = _copy.MODEL_LABEL
DISPLAY_NAME = _copy.DISPLAY_NAME
_PLATFORM_WATCH_GRACE_S = session._WATCH_GRACE_S
_PLATFORM_WATCH_POLL_S = session._WATCH_POLL_S
_BROWSER_START_TIMEOUT_S = session._BROWSER_START_TIMEOUT_S
_COLD_BROWSER_START_TIMEOUT_S = session._COLD_BROWSER_START_TIMEOUT_S
_LAUNCH_COOLDOWN_S = session._LAUNCH_COOLDOWN_S

log = logging.getLogger(_copy.LOG_NAME)

_state_lock = threading.RLock()
_session: PluginSession | None = None
_last_launch_ts = 0.0


def _owns_cycle() -> bool:
    current = _session
    return current is not None and current.owns_cycle


class BridgeKeepalive(_BridgeKeepalive):
    """Shared keepalive bound to this plugin's logger and status seam."""

    def __init__(self, interval_s: float = _KEEPALIVE_INTERVAL_S, **kwargs: Any) -> None:
        kwargs.setdefault("status_fn", _daemon_status)
        kwargs.setdefault("owns_cycle_fn", _owns_cycle)
        kwargs.setdefault("log", log)
        super().__init__(interval_s, **kwargs)

# The state machine reads its patchable callables back from this module.
session.bind_entry(sys.modules[__name__])


def _owns_cycle() -> bool:
    with _state_lock:
        current = _session
    return current is not None and current.owns_cycle


_keepalive = BridgeKeepalive(status_fn=_daemon_status, owns_cycle_fn=_owns_cycle)


def plugins_enabled() -> bool:
    """Whether this plugin may own dictation (developer-mode marker present)."""
    return _daemon_common.plugins_enabled(PLUGINS_DIR)


def shutdown_daemon() -> None:
    """Close the daemon when the user selects another plugin."""
    _daemon_common.shutdown(_post, log)


def ensure_daemon() -> bool:
    """Spawn the ONE shared Node control daemon if not already listening."""
    return _daemon_common.ensure_daemon(
        HERE,
        _daemon_alive,
        log,
        daemon_script=Path(_CLIENT.daemon_script),
        daemon_args=_CLIENT.daemon_args,
        cwd=Path(_CLIENT.daemon_cwd),
        listening_fn=_CLIENT.listening,
    )


def _profile_visible() -> bool:
    """The "Show the browser window" setting; missing/invalid means visible."""
    try:
        raw = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    value = raw.get("visible") if isinstance(raw, dict) else None
    return value if isinstance(value, bool) else True


def launch_profile(profile_dir: str, url: str) -> bool:
    """Entry-module seam pinned by tests/tools; reads the visibility knob here."""
    return _launch_chrome(
        profile_dir,
        url,
        visible=_profile_visible(),
        plugin_dir=str(HERE),
    )


def _profile_missing() -> bool:
    """The user closed the profile, so reopen it without waiting out the cooldown."""
    if sys.platform != "win32":
        return False
    try:
        return not bool(_browser_pids(str(_profile_dir())))
    except Exception:
        return False


def _launch_profile_if_due() -> bool:
    """Open the dictation profile at most once per cooldown window (C-START-3)."""
    global _last_launch_ts

    def _record(ts: float) -> None:
        global _last_launch_ts
        _last_launch_ts = ts

    launched, new_ts = session.launch_profile_if_due(
        last_ts=_last_launch_ts,
        config_fn=_daemon_config,
        launch_fn=launch_profile,
        clock=time,
        on_due=_record,
        bypass_fn=_profile_missing,
    )
    _last_launch_ts = new_ts
    return launched


def _ensure_browser(timeout: float | None = None) -> bool:
    """Open the dictation profile if needed, and wait until its page answers.

    The visibility setting is applied at launch only; a press never shows or
    activates a window.
    """
    # Never reveal or activate a window on the dictation path: doing so steals
    # focus from the target field and can reveal a hidden helper window.
    return session.ensure_browser(
        status_fn=_daemon_status,
        launch_fn=_launch_profile_if_due,
        ready_fn=_bridge_ready,
        transport_fn=_browser_connected,
        clock=time,
        timeout=timeout,
    )


def handle_escape(app: Any) -> bool:
    """ESC hotkey hook: cancel the plugin session if it is running."""
    with _state_lock:
        current = _session
    if current is None:
        return False
    return current.cancel()


def attach(app: Any) -> PluginSession | None:
    """Called from the product hotkey path; idempotent."""
    if not plugins_enabled():
        return None
    global _session
    with _state_lock:
        if _session is not None:
            return _session
        _session = PluginSession(
            app,
            entry=sys.modules[__name__],
            client=_CLIENT,
            copy_mod=_copy,
            log=log,
        )
    log.info("[PLUGIN] Anthropic STT plugin attached")
    return _session


def detach() -> None:
    global _session
    with _state_lock:
        current = _session
        _session = None
    if current is not None and current.active:
        try:
            current.cancel()
        except Exception:
            log.exception("[PLUGIN] detach: daemon cancel failed")


def activate(app: Any) -> bool:
    """Check the bridge because the user selected this plugin.

    Selecting the plugin (and every app start while it stays selected) opens
    the dictation profile if it is not already open, so the hotkey is ready
    without a manual window launch. The profile is started with plain flags
    only; nothing here moves, resizes or re-focuses it afterwards.
    """
    if not plugins_enabled():
        return False
    if attach(app) is None:
        return False
    if not ensure_daemon():
        log.error("[PLUGIN] activation failed: the control daemon did not start")
        return False
    _keepalive.start()
    if not _browser_connected(_daemon_status()):
        # A cold browser is the normal case: opening the window is the useful
        # action, and the first hotkey press waits for the handshake.
        _launch_profile_if_due()
        log.info(
            "[PLUGIN] %s activated; the dictation window is starting, the first hotkey press waits for it",
            DISPLAY_NAME,
        )
        return True
    reason = ""
    try:
        _post("/warm", timeout=120.0)
    except BridgeError as exc:
        reason = str(exc)
    except Exception:
        log.exception("[PLUGIN] activation warm-up failed")
        return False
    if reason:
        # The daemon already names the reason; a traceback would bury it.
        log.error("[PLUGIN] activation warm-up failed: %s", reason)
        return False
    log.info("[PLUGIN] Anthropic STT activated; browser is up")
    return True


def deactivate() -> None:
    """Drop the session and stop the bridge when another engine is chosen."""
    _keepalive.stop()
    detach()
    shutdown_daemon()
