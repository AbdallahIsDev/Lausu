"""Internal Google STT plugin. Bundled but gated.

Loaded by the tiny gated hook in ``voice_typer/server/internal_plugin_hook.py`` only
when ``plugins_enabled()`` is true (the plugin workspace's PLUGINS_ENABLED
marker, which developer mode writes). The source ships inside the packaged
app; the marker and the developer-mode flag are the opt-ins. Everything it
touches is a product path:
bubble_show/hide + recording_started/stopped (bubble + sound cues),
app.clipboard copy+paste, app.history_db.add_transcription.

Browser control lives in the external Node daemon (run.js) driven over
127.0.0.1. Plan: docs/plan-internal-plugin-google-stt.md.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

log = logging.getLogger("voice_typer.internal_plugin.google_stt")

HERE = Path(__file__).resolve().parent
PLUGINS_DIR = HERE.parent
DAEMON_URL = os.environ.get("GOOGLE_STT_URL", "http://127.0.0.1:17874")
_MODEL_LABEL = "google-stt-web"

# Daemon failure kinds → what the user is actually told. The daemon reports a
# slug; without this the toast said nothing useful and the log carried a
# 20-line urllib traceback that hid the reason entirely.
_START_HINTS = {
    "browser-closed": "The Google STT browser window closed - press the hotkey again to relaunch it.",
    "mic-missing": "Google STT could not find the microphone button on the page.",
    "no-recording-indicator": "The page never started recording.",
    "platform-not-recording": "The page did not start capturing audio.",
    "composer-dirty": "The page's prompt box would not clear - press the hotkey again.",
    "signed-out": "The burner Google session is signed out - run login.js.",
}

_state_lock = threading.RLock()
_session: PluginSession | None = None


class BridgeError(RuntimeError):
    """The daemon answered with an error; ``kind`` maps to a user-facing hint."""

    def __init__(self, reason: str, kind: str = "") -> None:
        super().__init__(reason)
        self.kind = kind


def plugins_enabled() -> bool:
    """Whether this plugin may own dictation.

    The PLUGINS_ENABLED marker in the plugin workspace is the switch. It is
    written when the owner unlocks developer mode, so a packaged build stays
    inert until then; the marker's presence is the whole gate.
    """
    return (PLUGINS_DIR / "PLUGINS_ENABLED").is_file()


def _post(path: str, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(DAEMON_URL + path, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # The daemon puts the real reason in the body. urllib discards it, so
        # every failure surfaced as a bare "HTTP Error 500" traceback.
        raw = ""
        try:
            raw = e.read().decode("utf-8", "replace")
        except Exception:
            raw = ""
        reason = ""
        kind = ""
        if raw:
            try:
                body = json.loads(raw)
                reason = str(body.get("error") or "")
                kind = str(body.get("kind") or "")
            except Exception:
                reason = raw[:200]
        raise BridgeError(reason or f"HTTP {e.code}", kind) from None
    except urllib.error.URLError as e:
        raise BridgeError(f"cannot reach the Google STT bridge ({e.reason})") from None


def _daemon_alive() -> bool:
    try:
        with urllib.request.urlopen(DAEMON_URL + "/status", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def shutdown_daemon() -> None:
    """Close the browser + daemon when the user selects another plugin.

    The profile is shared, so an idle daemon still holds Chromium's lock
    and would make the newly selected plugin fail as ``profile-busy``.
    """
    try:
        _post("/shutdown", timeout=3.0)
    except Exception:
        log.debug("[PLUGIN] daemon shutdown request failed", exc_info=True)


def _node_exe() -> str:
    import shutil

    return shutil.which("node") or "node"


def _hotkey_to_spec(raw: str) -> str:
    """``<ctrl>+<shift>+<space>`` -> ``ctrl+shift+space``."""
    return raw.replace("<", "").replace(">", "").strip().lower()


def _mute_bubble_levels() -> None:
    """No PCM is routed to the bubble, emit a flat level so consumers
    that expect motion at low rate still render."""
    from voice_typer.server import event_bus

    while True:
        with _state_lock:
            if _session is None or not _session.active:
                return
        event_bus.publish({"type": "bubble_level", "data": {"rms": 0.08, "peak": 0.12}})
        time.sleep(0.1)


class PluginSession:
    """Toggle state machine bound to the product hotkey + bubble + cues."""

    def __init__(self, app: Any) -> None:
        self._app = app
        self._lock = threading.RLock()
        self._active = False
        self._hwnd = 0
        self._t0 = 0.0
        self._busy = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def toggle(self) -> None:
        with self._lock:
            if self._busy:
                return
            self._busy = True
            active = self._active
        try:
            if active:
                self.stop()
            else:
                self.start()
        finally:
            with self._lock:
                self._busy = False

    def _report_start_failure(self, exc: BridgeError) -> None:
        # Deliberately a plain error line: a failed hotkey press is a routine,
        # recoverable event, and the old traceback-per-press buried the actual
        # reason. The traceback stays available at DEBUG.
        log.error("[PLUGIN] start failed: %s", exc)
        log.debug("[PLUGIN] start failure context", exc_info=True)
        self._notify(_START_HINTS.get(exc.kind, "Google STT could not start. See log."))

    def start(self) -> None:
        if not ensure_daemon():
            self._notify("Google STT bridge unavailable (daemon did not start).")
            return
        try:
            _post("/start", timeout=30.0)
        except BridgeError as exc:
            # One actionable line instead of a 20-line urllib traceback, which
            # surfaced as a bare "HTTP Error 500" and told nobody anything.
            self._report_start_failure(exc)
            return
        except Exception:
            log.exception("[PLUGIN] start failed")
            self._notify("Google STT start failed. See log.")
            return
        with self._lock:
            self._active = True
            try:
                import ctypes

                self._hwnd = int(ctypes.windll.user32.GetForegroundWindow())
            except Exception:
                self._hwnd = 0
            self._t0 = time.monotonic()
        self._session_events(start=True)
        threading.Thread(target=_mute_bubble_levels, daemon=True, name="plugin-bubble-level").start()

    def stop(self) -> None:
        try:
            res = _post("/stop", timeout=75.0)
        except Exception:
            log.exception("[PLUGIN] stop failed")
            with self._lock:
                self._active = False
            self._session_events(start=False)
            self._notify("Google STT stop failed. See log.")
            return
        text = str(res.get("text", "")).strip()
        duration = float(res.get("duration_s", 0.0) or (time.monotonic() - self._t0))
        with self._lock:
            hwnd = self._hwnd
            self._active = False
            self._hwnd = 0
        self._restore_foreground(hwnd)
        self._session_events(start=False)
        if not text:
            # The daemon names WHY it is empty (see run.js): an auto-stop
            # with no transcript is the known platform failure, distinct
            # from polite silence. Say which one happened.
            if res.get("auto_stopped"):
                self._notify(
                    "The platform stopped the recording on its own and sent "
                    "no transcription. Speak again in a shorter burst."
                )
            else:
                self._notify("Empty transcript.")
            return
        self._deliver(text, duration)

    def cancel(self) -> bool:
        """ESC path: abort the session without pasting; clear the page."""
        with self._lock:
            if not self._active:
                return False
            self._active = False
        try:
            _post("/cancel", timeout=30.0)
        except Exception:
            log.debug("[PLUGIN] cancel request failed", exc_info=True)
        self._session_events(start=False)
        return True

    def _deliver(self, text: str, duration: float) -> None:
        app = self._app
        try:
            snapshot = app.clipboard.copy(text)
            paste_seq = app.clipboard._clipboard_seq
            app.clipboard.paste(snapshot=snapshot, pasted_text=text, pasted_seq=paste_seq)
        except Exception:
            log.exception("[PLUGIN] paste failed; text stays in clipboard")
        try:
            row_id = app.history_db.add_transcription(
                text,
                duration=duration,
                model=_MODEL_LABEL,
                device=getattr(app.config, "device", ""),
                language=getattr(app.config, "language", ""),
            )
            if row_id <= 0:
                log.error("[PLUGIN] history add returned %s", row_id)
            app._last_transcription = text
            from voice_typer.server import event_bus

            event_bus.publish({"type": "transcription_final", "data": {"text": text[:200]}})
            event_bus.publish({"type": "history_changed"})
        except Exception:
            log.exception("[PLUGIN] history store failed")

    def _restore_foreground(self, hwnd: int) -> None:
        if not hwnd:
            return
        try:
            import ctypes

            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(0.15)
        except Exception:
            log.debug("[PLUGIN] foreground restore failed", exc_info=True)

    def _session_events(self, *, start: bool) -> None:
        from voice_typer.server import event_bus

        if start:
            event_bus.publish({"type": "bubble_show"})
            event_bus.publish({"type": "recording_started", "data": {"source": _MODEL_LABEL}})
        else:
            event_bus.publish({"type": "recording_stopped", "data": {"source": _MODEL_LABEL}})
            event_bus.publish({"type": "bubble_hide"})

    def _notify(self, msg: str) -> None:
        try:
            self._app.tray.notify("Google STT (internal)", msg)
        except Exception:
            log.debug("[PLUGIN] notify failed", exc_info=True)


def _node_deps_root() -> str:
    """Per-user directory the plugin's Node dependencies are installed into."""
    override = os.environ.get("PLUGINS_NODE_DEPS")
    if override:
        return override
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "voice-typer-internal-plugins", "node-deps")


def _daemon_env() -> dict[str, str]:
    """Environment for the Node daemon, including the Windows paths it needs.

    Tauri spawns the sidecar with a trimmed environment. Playwright's
    ``channel: 'chrome'`` resolves the Chrome install through PROGRAMFILES,
    and a missing value there failed the launch with
    ``Chromium distribution 'chrome' is not found at undefined\\Program Files\\...``.
    The runner also probes the binary directly; backfilling here keeps both
    resolution paths working.
    """
    env = dict(os.environ)
    env["NODE_PATH"] = _node_deps_root() + os.pathsep + env.get("NODE_PATH", "")
    for key, fallback in (
        ("PROGRAMFILES", r"C://Program Files"),
        ("PROGRAMFILES(X86)", r"C://Program Files (x86)"),
        ("PROGRAMW6432", r"C://Program Files"),
        ("SYSTEMROOT", r"C://Windows"),
        ("LOCALAPPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Local")),
    ):
        if not env.get(key):
            env[key] = fallback
    return env


def ensure_daemon() -> bool:
    """Spawn the Node control daemon if not already listening."""
    if _daemon_alive():
        return True
    env = _daemon_env()
    # The daemon is the only place a browser/selector failure can surface, so
    # its output must be inspectable instead of DEVNULL: a dead daemon
    # otherwise fails as an opaque ConnectionRefusedError at stop time.
    debug = HERE / "debug"
    debug.mkdir(exist_ok=True)
    try:
        with (
            open(debug / "daemon.out.log", "a", encoding="utf-8") as out,
            open(debug / "daemon.err.log", "a", encoding="utf-8") as err,
        ):
            subprocess.Popen(
                [_node_exe(), str(HERE / "run.js")],
                cwd=str(HERE),
                env=env,
                stdout=out,
                stderr=err,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except Exception:
        log.exception("[PLUGIN] failed to spawn daemon")
        return False
    for _ in range(40):
        if _daemon_alive():
            return True
        time.sleep(0.5)
    log.error("[PLUGIN] daemon did not come up")
    return False


def handle_escape(app: Any) -> bool:
    """ESC hotkey hook: cancel the plugin session if it is running."""
    with _state_lock:
        session = _session
    if session is None:
        return False
    return session.cancel()


def attach(app: Any) -> PluginSession | None:
    """Called from the product hotkey path; idempotent.

    Deliberately does NOT pre-spawn the browser daemon: the first session
    start brings it up, so app launch stays quiet.
    """
    if not plugins_enabled():
        return None
    global _session
    with _state_lock:
        if _session is not None:
            return _session
        _session = PluginSession(app)
    log.info("[PLUGIN] Google STT plugin attached")
    return _session


def detach() -> None:
    global _session
    with _state_lock:
        session = _session
        _session = None
    if session is not None and session.active:
        try:
            session.cancel()
        except Exception:
            log.exception("[PLUGIN] detach: daemon cancel failed")


DISPLAY_NAME = "Google STT"


def activate(app: Any) -> bool:
    """Bring the browser up because the user selected this plugin.

    Selecting a plugin has to do something immediately. The daemon boots the
    Chrome window with the shared profile and the platform URL; the plugin's
    own ``visible`` setting decides whether that window is on screen or
    parked off-screen (still headed, because a truly headless browser has no
    microphone).
    """
    if not plugins_enabled():
        return False
    if attach(app) is None:
        return False
    if not ensure_daemon():
        log.error("[PLUGIN] activation failed: the control daemon did not start")
        return False
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
    log.info("[PLUGIN] Google STT activated; browser is up")
    return True


def deactivate() -> None:
    """Drop the session and close the browser when another engine is chosen."""
    detach()
    shutdown_daemon()
