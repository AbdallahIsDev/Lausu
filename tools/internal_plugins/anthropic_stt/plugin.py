"""Internal Anthropic STT plugin. Bundled but gated.

Loaded by the tiny gated hook in ``voice_typer/server/internal_plugin_hook.py`` only
when ``plugins_enabled()`` is true (the plugin workspace's PLUGINS_ENABLED
marker, which developer mode writes). The source ships inside the packaged
app; the marker and the developer-mode flag are the opt-ins. Everything it
touches is a product path:
bubble_show/hide + recording_started/stopped (bubble + sound cues),
app.clipboard copy+paste, app.history_db.add_transcription.

Browser control lives in the external Node daemon (run.js) driven over
127.0.0.1. The daemon talks to a Chrome extension inside the owner's dictation
profile. When that profile is not open, the plugin starts it through
chrome_profile.py with plain flags only: no automation switches, no debugging
port, no Playwright.
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

from tools.internal_plugins.anthropic_stt.chrome_profile import launch as launch_profile

log = logging.getLogger("voice_typer.internal_plugin.anthropic_stt")

HERE = Path(__file__).resolve().parent
PLUGINS_DIR = HERE.parent
DAEMON_URL = os.environ.get("ANTHROPIC_STT_URL", "http://127.0.0.1:17875")
_MODEL_LABEL = "anthropic-stt-web"

# Daemon failure kinds → what the user is actually told. The daemon reports a
# slug; without this the toast said nothing useful and the log carried a
# 20-line urllib traceback that hid the reason entirely.
_START_HINTS = {
    "browser-not-open": (
        "The Claude dictation window could not be started, or its extension is not loaded. "
        "Check the window, load the extension once if it is missing, then press the hotkey again."
    ),
    "page-not-ready": ("The Claude tab is still loading. Wait a moment, then press the hotkey again."),
    "bridge-timeout": (
        "The Claude page did not answer in time. Check that its window is open on the Claude tab, "
        "then press the hotkey again."
    ),
    "mic-missing": "Anthropic STT could not find the dictation button on the Claude page.",
    "no-recording-indicator": "The Claude page never started recording.",
    "platform-not-recording": "The Claude page did not start capturing audio.",
    "composer-dirty": "The Claude prompt box would not clear - press the hotkey again.",
    "signed-out": "The Claude session is signed out - open the Claude browser window and sign in again.",
    "challenge": (
        "Claude's security check is blocking the page - finish the check in the Claude "
        "browser window, then press the hotkey again."
    ),
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
        raise BridgeError(f"cannot reach the Anthropic STT bridge ({e.reason})") from None


def _daemon_status() -> dict | None:
    """The daemon's bridge snapshot, or None when it is not answering."""
    try:
        with urllib.request.urlopen(DAEMON_URL + "/status", timeout=1.5) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def _daemon_alive() -> bool:
    return _daemon_status() is not None


def _daemon_config() -> dict:
    """The daemon's browser knobs (profileDir/claudeUrl), or {} if unavailable."""
    try:
        with urllib.request.urlopen(DAEMON_URL + "/config", timeout=2.0) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _bridge_ready(status: dict | None) -> bool:
    """Connected AND the tab has answered once (a page state, not unknown)."""
    if not status or status.get("browser") != "connected":
        return False
    page = status.get("page")
    return isinstance(page, str) and page not in ("", "unknown")


def shutdown_daemon() -> None:
    """Close the daemon when the user selects another plugin.

    The browser window belongs to the owner and stays open; only the bridge to
    the extension is torn down.
    """
    try:
        _post("/shutdown", timeout=3.0)
    except Exception:
        log.debug("[PLUGIN] daemon shutdown request failed", exc_info=True)


def _node_exe() -> str:
    import shutil

    return shutil.which("node") or "node"


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


def _notify_enabled(directory: Path | None = None) -> bool:
    """The Plugins page's notification switch; a missing or invalid value is on."""
    try:
        raw = json.loads(((directory or HERE) / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    value = raw.get("notify") if isinstance(raw, dict) else None
    return value if isinstance(value, bool) else True


class PluginSession:
    """Toggle state machine bound to the product hotkey + bubble + cues."""

    def __init__(self, app: Any) -> None:
        self._app = app
        self._lock = threading.RLock()
        self._active = False
        self._starting = False
        self._t0 = 0.0
        self._busy = False
        # A push-to-talk release can arrive while the start is still warming
        # up (browser launch, daemon spawn, /start handshake). It must stop as
        # soon as the start lands instead of leaving the platform recording.
        self._stop_requested = False
        # The user's stop and the platform-stop watchdog can race; only one of
        # them may run the stop/deliver path.
        self._stopping = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def owns_cycle(self) -> bool:
        """This session owns the in-flight dictation cycle (starting or live)."""
        with self._lock:
            return self._active or self._starting

    def toggle(self) -> None:
        with self._lock:
            if self._busy:
                log.debug("[PLUGIN] press ignored: a cycle transition is in flight")
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

    def _publish_state(self, state: str) -> None:
        """Drive the pill's own state machine (recording / transcribing / idle)."""
        from voice_typer.server import event_bus

        try:
            event_bus.publish({"type": "bubble_set_state", "data": {"state": state}})
        except Exception:
            log.debug("[PLUGIN] bubble state publish failed", exc_info=True)

    def _duck(self) -> None:
        """Duck the system volume for the capture, like the local model does."""
        try:
            self._app._duck_volume()
        except Exception:
            log.debug("[PLUGIN] volume duck failed", exc_info=True)

    def _restore_volume(self) -> None:
        try:
            self._app._restore_volume()
        except Exception:
            log.debug("[PLUGIN] volume restore failed", exc_info=True)

    def _report_start_failure(self, exc: BridgeError) -> None:
        # Deliberately a plain error line: a failed hotkey press is a routine,
        # recoverable event, and the old traceback-per-press buried the actual
        # reason. The traceback stays available at DEBUG.
        log.error("[PLUGIN] start failed: %s", exc)
        log.debug("[PLUGIN] start failure context", exc_info=True)
        self._notify(_START_HINTS.get(exc.kind, "Anthropic STT could not start. See log."))

    def start(self) -> None:
        with self._lock:
            if self._active or self._starting:
                return
            self._starting = True
            self._stop_requested = False
        try:
            self._start()
        finally:
            with self._lock:
                self._starting = False
                stop_now = self._active and self._stop_requested
                self._stop_requested = False
            if stop_now:
                # The release arrived mid-start: finish the cycle now.
                self._stop_and_deliver()

    def _start(self) -> None:
        if not ensure_daemon():
            self._notify("Anthropic STT bridge unavailable (daemon did not start).")
            return
        # Press-to-dictate: a closed profile is opened here and waited for, so
        # the first press ends in a recording instead of a "window closed" toast.
        if not _ensure_browser():
            self._notify(_START_HINTS["browser-not-open"])
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
            self._notify("Anthropic STT start failed. See log.")
            return
        with self._lock:
            self._active = True
            self._t0 = time.monotonic()
        self._session_events(start=True)
        self._duck()
        threading.Thread(target=_mute_bubble_levels, daemon=True, name="plugin-bubble-level").start()
        threading.Thread(target=self._watch_platform, daemon=True, name="plugin-platform-watch").start()

    def stop(self) -> bool:
        """Stop the cycle: a release during a start is deferred, not dropped."""
        with self._lock:
            if self._starting:
                self._stop_requested = True
                log.debug("[PLUGIN] stop deferred: the start is still in flight")
                return True
            if not self._active:
                log.debug("[PLUGIN] stop ignored: no cycle is running")
                return False
        self._stop_and_deliver()
        return True

    def _stop_and_deliver(self) -> None:
        with self._lock:
            if self._stopping or not self._active:
                return
            self._stopping = True
        try:
            self._publish_state("transcribing")
            try:
                res = _post("/stop", timeout=75.0)
            except Exception:
                log.exception("[PLUGIN] stop failed")
                with self._lock:
                    self._active = False
                self._session_events(start=False)
                self._notify("Anthropic STT stop failed. See log.")
                return
            finally:
                self._restore_volume()
            self._finish(res)
        finally:
            with self._lock:
                self._stopping = False

    def _finish(self, res: dict) -> None:
        """Deliver a completed stop response (text, history, paste, cleanup)."""
        text = str(res.get("text", "")).strip()
        duration = float(res.get("duration_s", 0.0) or (time.monotonic() - self._t0))
        with self._lock:
            self._active = False
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
        self._clear_prompt_box()

    def _watch_platform(self) -> None:
        """Deliver the capture when the PLATFORM stops the dictation itself.

        Claude ends a dictation on its own (focus loss, its own length cap, a
        page reload). The user did not press anything, so the audio it already
        captured must still be committed, transcribed, pasted and stored --
        otherwise the whole cycle is silently lost. Two consecutive idle reads
        are required so a transient status blip cannot cut a live capture.
        """
        time.sleep(_PLATFORM_WATCH_GRACE_S)
        idle_reads = 0
        while True:
            with self._lock:
                if not self._active or self._stopping:
                    return
            status = _daemon_status()
            state = str((status or {}).get("state") or "")
            if state == "recording":
                idle_reads = 0
            elif state in ("idle", "no-page", "unknown"):
                idle_reads += 1
                if idle_reads >= 2:
                    log.info(
                        "[PLUGIN] the platform stopped the dictation on its own (state=%s); "
                        "delivering what it captured",
                        state,
                    )
                    self._stop_and_deliver()
                    return
            time.sleep(_PLATFORM_WATCH_POLL_S)

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
        self._restore_volume()
        self._session_events(start=False)
        return True

    def _clear_prompt_box(self) -> None:
        """Empty Claude's composer once the text has been delivered.

        The transcript is already pasted into the user's app, so leaving it in
        the platform's prompt box only invites an accidental send. Best effort:
        the next start cleans the box anyway, so a failure is cosmetic.
        """
        try:
            res = _post("/clear", timeout=10.0)
        except Exception:
            log.debug("[PLUGIN] prompt-box clear failed", exc_info=True)
            return
        if not res.get("cleared"):
            log.debug("[PLUGIN] prompt box not cleared: %s", res.get("reason") or "unknown")

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

    def _session_events(self, *, start: bool) -> None:
        from voice_typer.server import event_bus

        if start:
            event_bus.publish({"type": "bubble_show"})
            event_bus.publish({"type": "bubble_set_state", "data": {"state": "recording"}})
            event_bus.publish({"type": "recording_started", "data": {"source": _MODEL_LABEL}})
        else:
            event_bus.publish({"type": "bubble_set_state", "data": {"state": "idle"}})
            event_bus.publish({"type": "recording_stopped", "data": {"source": _MODEL_LABEL}})
            event_bus.publish({"type": "bubble_hide"})

    def _notify(self, msg: str) -> None:
        if not _notify_enabled():
            return
        try:
            self._app.tray.notify("Anthropic STT (internal)", msg)
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
    """Environment for the Node daemon.

    Tauri spawns the sidecar with a trimmed environment, so the external
    ``node-deps`` folder (where ``ws`` lives) is added to ``NODE_PATH`` and the
    standard Windows paths are backfilled for any Node tooling that still reads
    them.
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


# The platform-stop watchdog: a short grace so the start's own status settles,
# then a poll that needs two consecutive idle reads before it acts.
_PLATFORM_WATCH_GRACE_S = 2.0
_PLATFORM_WATCH_POLL_S = 1.0

_BROWSER_START_TIMEOUT_S = 15.0
# A dead extension must not spawn a new tab on every hotkey press: one launch
# attempt per window is enough, the wait below still covers a slow boot.
_LAUNCH_COOLDOWN_S = 30.0
_last_launch_ts = 0.0


def _ensure_browser(timeout: float = _BROWSER_START_TIMEOUT_S) -> bool:
    """Open the dictation profile if needed, and wait until its page answers."""
    global _last_launch_ts
    if _bridge_ready(_daemon_status()):
        return True
    now = time.monotonic()
    if now - _last_launch_ts >= _LAUNCH_COOLDOWN_S:
        _last_launch_ts = now
        config = _daemon_config()
        profile_dir = str(config.get("profileDir") or "")
        claude_url = str(config.get("claudeUrl") or "")
        if not launch_profile(profile_dir, claude_url):
            return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _bridge_ready(_daemon_status()):
            return True
        time.sleep(0.5)
    log.error("[PLUGIN] the dictation window did not answer within %.0fs", timeout)
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
    log.info("[PLUGIN] Anthropic STT plugin attached")
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


DISPLAY_NAME = "Anthropic STT"


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
    _ensure_browser()
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
    detach()
    shutdown_daemon()
