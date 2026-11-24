"""Dictation state machine shared by both internal STT plugins.

The owning plugin supplies its copy module, daemon client and patchable
module-level callables through ``bind_entry``/constructor injection, so the
hotkey, bubble and delivery flows stay identical on both platforms.
resolve to the entry module even though the logic lives here.
"""

from __future__ import annotations

import inspect
import logging
import threading
import time
from pathlib import Path
from typing import Any

from tools.internal_plugins._common import daemon as _daemon_common
from tools.internal_plugins._common.bridge.install_paths import legacy_profile_dir, profile_dir
from tools.internal_plugins._common.daemon import BridgeError
from tools.internal_plugins._common.delivery import deliver_transcription
from tools.internal_plugins._common.level_meter import LevelMeter
from tools.internal_plugins._common.status import set_cycle_state

_WATCH_GRACE_S = 2.0
_WATCH_POLL_S = 1.0
_BROWSER_START_TIMEOUT_S = 15.0
_COLD_BROWSER_START_TIMEOUT_S = 30.0
_LAUNCH_COOLDOWN_S = 30.0
_START_ATTEMPTS = 2
_START_RETRY_PAUSE_S = 0.4
_START_RETRY_KINDS = frozenset({"browser-not-open", "browser-closed", "wrong-platform"})

log = logging.getLogger("voice_typer.internal_plugin.bridge")

_entry: Any | None = None


def bind_entry(entry: Any) -> None:
    """Point session lookups at the entry module's patchable callables."""
    global _entry
    _entry = entry


def launch_profile_if_due(
    *,
    last_ts: float,
    config_fn: Any,
    launch_fn: Any,
    clock: Any,
    on_due: Any = None,
    cooldown_s: float = _LAUNCH_COOLDOWN_S,
    bypass_fn: Any | None = None,
) -> tuple[bool, float]:
    """Open the dictation profile at most once per cooldown window (C-START-3).

    ``on_due`` records the timestamp before the launch attempt so a failing
    launch is still bounded. Returns ``(launched, new_timestamp)``.
    """
    now = clock.monotonic()
    # A profile the user actually closed is reopened immediately; the cooldown
    # only bounds repeat launches against a browser that is still running.
    if not (bypass_fn is not None and bypass_fn()) and now - last_ts < cooldown_s:
        return False, last_ts
    if on_due is not None:
        on_due(now)
    config = config_fn()
    configured = str(config.get("profileDir") or "")
    legacy = legacy_profile_dir()
    # A daemon started before the profile rename keeps the OLD path in memory.
    # Launching it makes Chrome create a brand-new empty profile and lose every
    # sign-in, so the migrated path from install.json always wins here.
    profile = str(profile_dir()) if legacy is not None and configured and Path(configured) == legacy else configured
    launched = launch_fn(
        profile,
        str(config.get("url") or config.get("claudeUrl") or config.get("geminiUrl") or ""),
    )
    return launched, now


def ensure_browser(
    *,
    status_fn: Any,
    launch_fn: Any,
    ready_fn: Any,
    clock: Any,
    timeout: float | None = None,
    transport_fn: Any | None = None,
) -> bool:
    """Open the dictation profile if needed, and wait for the bridge transport.

    ``transport_fn`` gates the launch (browser connected vs not); ``ready_fn``
    stays the page-level check for callers that need it. Keeping them separate
    is what stops a closed target tab from spawning another Chrome tab.
    """
    connected = transport_fn or ready_fn
    if connected(status_fn()):
        return True
    launched = launch_fn()
    default_budget = _COLD_BROWSER_START_TIMEOUT_S if launched else _BROWSER_START_TIMEOUT_S
    budget = default_budget if timeout is None else timeout
    deadline = clock.monotonic() + budget
    while clock.monotonic() < deadline:
        if connected(status_fn()):
            return True
        clock.sleep(0.5)
    log.error("[PLUGIN] the dictation window did not answer within %.0fs", budget)
    return False


def _fallback_ensure_daemon(client, log):
    return _daemon_common.ensure_daemon(
        Path(client.config_dir), client.alive, log,
        daemon_script=client.daemon_script, cwd=client.daemon_cwd,
        daemon_args=client.daemon_args,
    )


def _fallback_ensure_browser(client):
    return ensure_browser(
        status_fn=client.status, launch_fn=lambda: False,
        ready_fn=client.bridge_ready, clock=time,
    )


def _capture_target_snapshot() -> Any:
    """Capture stop-time target snapshot (lazy import keeps bridge self-contained)."""
    try:
        from voice_typer.server.clipboard_target_safety import capture_stop_time_target_snapshot

        return capture_stop_time_target_snapshot()
    except Exception:
        log.debug("[PLUGIN] stop-time target snapshot capture failed", exc_info=True)
        return None


def _accepts_kwarg(fn: object, name: str) -> bool:
    try:
        params = inspect.signature(fn).parameters.values()  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return any(p.kind == inspect.Parameter.VAR_KEYWORD or p.name == name for p in params)


class PluginSession:
    """Toggle state machine bound to the product hotkey + bubble + cues."""

    _stale_extension_warned = False

    def __init__(
        self,
        app: Any,
        *,
        entry: Any | None = None,
        client: Any | None = None,
        copy_mod: Any | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self._app = app
        self._client = client
        self._copy = copy_mod
        self._log = log or logging.getLogger("voice_typer.internal_plugin.bridge")
        self._entry = entry if entry is not None else _entry
        self._lock = threading.RLock()
        self._active = False
        self._starting = False
        self._t0 = 0.0
        self._busy = False
        # A push-to-talk release can arrive while the start is still warming
        # up (browser launch, daemon spawn, /start handshake). It must stop as
        # soon as the start lands instead of leaving the platform recording.
        self._stop_requested = False
        self._pending_stop_snapshot: Any = None
        # The user's stop and the platform-stop watchdog can race; only one of
        # them may run the stop/deliver path.
        self._stopping = False
        # Live microphone levels for the pill (the browser owns the capture).
        self._meter: LevelMeter | None = None
        self._cycle = 0

    def _host(self, name: str, default: Any) -> Any:
        return getattr(self._entry, name, default) if self._entry is not None else default

    def _post(self, path: str, timeout: float) -> dict:
        return self._host("_post", lambda p, t: self._client.post(p, t))(path, timeout)

    def _status(self) -> dict | None:
        return self._host("_daemon_status", self._client.status)()

    def _ensure_daemon(self) -> bool:
        return self._host("ensure_daemon", lambda: _fallback_ensure_daemon(self._client, self._log))()

    def _ensure_browser(self, timeout: float | None = None) -> bool:
        def default(timeout: float | None = None) -> bool:
            return _fallback_ensure_browser(self._client)

        return self._host("_ensure_browser", default)(timeout=timeout)

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
                self._log.debug("[PLUGIN] press ignored: a cycle transition is in flight")
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
        """Drive BOTH the pill and the canonical tray status from one state."""
        from voice_typer.server import event_bus

        try:
            event_bus.publish({"type": "bubble_set_state", "data": {"state": state}})
        except Exception:
            self._log.debug("[PLUGIN] bubble state publish failed", exc_info=True)
        set_cycle_state(self._app, state)

    def _duck(self) -> None:
        """Duck the system volume for the capture, like the local model does."""
        try:
            self._app._duck_volume()
        except Exception:
            self._log.debug("[PLUGIN] volume duck failed", exc_info=True)

    def _restore_volume(self) -> None:
        try:
            self._app._restore_volume()
        except Exception:
            self._log.debug("[PLUGIN] volume restore failed", exc_info=True)

    def _report_start_failure(self, exc: BridgeError) -> None:
        # Deliberately a plain error line: a failed hotkey press is a routine,
        # recoverable event, and the old traceback-per-press buried the actual
        # reason. The traceback stays available at DEBUG.
        self._log.error("[PLUGIN] start failed: %s", exc)
        self._log.debug("[PLUGIN] start failure context", exc_info=True)
        hint = self._copy.START_HINTS.get(exc.kind, self._copy.START_FAILURE_FALLBACK)
        if exc.kind in ("browser-not-open", "browser-closed", "wrong-platform"):
            from tools.internal_plugins._common.bridge.install_paths import install_hint

            hint = f"{hint} {install_hint()}"
        self._notify(hint)

    def start(self) -> None:
        with self._lock:
            if self._active or self._starting:
                return
            self._starting = True
            self._stop_requested = False
            self._pending_stop_snapshot = None
        try:
            self._start()
        finally:
            with self._lock:
                self._starting = False
                stop_now = self._active and self._stop_requested
                self._stop_requested = False
                pending_snapshot = self._pending_stop_snapshot
                self._pending_stop_snapshot = None
            if stop_now:
                # The release arrived mid-start: finish the cycle now.
                self._stop_and_deliver(target_snapshot=pending_snapshot)

    def _start(self) -> None:

        with self._lock:
            self._cycle += 1
            cycle = self._cycle
        # Per-step lines, same shape as the local dictation path: every stage
        # the user waits through is attributable from lausu.log alone.
        self._log.info("[PLUGIN] start requested (cycle=#%d)", cycle)
        t_press = time.monotonic()
        daemon_ok = self._ensure_daemon()
        if not daemon_ok:
            self._log.error(
                "[PLUGIN] start failed (cycle=#%d): the bridge did not come up%s",
                cycle,
                self._copy.duration(time.monotonic() - t_press),
            )
            self._notify(self._copy.BRIDGE_UNAVAILABLE)
            return
        self._log.info("[PLUGIN] bridge ready (cycle=#%d)%s", cycle, self._copy.duration(time.monotonic() - t_press))
        for attempt in range(_START_ATTEMPTS):
            # Press-to-dictate: a closed profile is opened here and waited for,
            # so the press ends in a recording instead of a "window closed" toast.
            t_browser = time.monotonic()
            if not self._ensure_browser():
                self._log.error(
                    "[PLUGIN] start failed (cycle=#%d): the dictation window is not answering%s",
                    cycle,
                    self._copy.duration(time.monotonic() - t_browser),
                )
                self._notify(self._copy.START_HINTS["browser-not-open"])
                return
            self._log.debug(
                "[PLUGIN] dictation window ready (cycle=#%d)%s",
                cycle,
                self._copy.duration(time.monotonic() - t_browser),
            )
            # Resolve the plugin's own tab BEFORE /start. Best effort here: the
            # extension also resolves inside /start, so an older daemon that does
            # not know this route still cannot start against a missing tab.
            try:
                self._post("/ensure-tab", timeout=20.0)
            except BridgeError as exc:
                if exc.kind == "bridge-error" and "unknown command ensure-tab" in str(exc):
                    # The extension still runs the pre-resolution content script:
                    # /start understands the old command and resolves its tab, so
                    # this is a capability gap, not a failed start. No traceback.
                    self._log.debug(
                        "[PLUGIN] target-tab pre-resolution needs an extension reload; "
                        "/start still resolves its tab"
                    )
                    if not type(self)._stale_extension_warned:
                        type(self)._stale_extension_warned = True
                        self._log.warning(
                            "[PLUGIN] reload the extension at chrome://extensions to enable target-tab recovery"
                        )
                else:
                    self._log.debug("[PLUGIN] target-tab pre-resolution failed: %s", exc)
            except Exception:
                self._log.debug("[PLUGIN] target-tab pre-resolution failed", exc_info=True)
            try:
                self._post("/start", timeout=30.0)
                break
            except BridgeError as exc:
                # The user can close the profile in the middle of the handshake.
                # The old audio never existed, so re-resolve the browser and try
                # once more instead of treating it as a failed dictation.
                transient = exc.kind in _START_RETRY_KINDS or "extension disconnected" in str(exc).lower()
                if attempt + 1 < _START_ATTEMPTS and transient:
                    self._log.warning(
                        "[PLUGIN] the browser disconnected while starting (cycle=#%d); "
                        "reopening and retrying once",
                        cycle,
                    )
                    time.sleep(_START_RETRY_PAUSE_S)
                    continue
                # One actionable line instead of a 20-line urllib traceback, which
                # surfaced as a bare "HTTP Error 500" and told nobody anything.
                self._report_start_failure(exc)
                return
            except Exception:
                self._log.exception("[PLUGIN] start failed")
                self._notify(self._copy.START_FAILURE_FALLBACK)
                return
        with self._lock:
            self._active = True
            self._t0 = time.monotonic()
        self._log.info(
            "[PLUGIN] recording started (cycle=#%d, platform=%s)%s",
            cycle,
            (status := self._status() or {}).get("state") or "unknown",
            self._copy.duration(time.monotonic() - t_press),
        )
        del status
        self._session_events(start=True)
        self._duck()
        self._meter = self._host("LevelMeter", LevelMeter)(self._app)
        self._meter.start()
        # Daemon: the platform watchdog is best-effort and must never hold process exit.
        threading.Thread(target=self._watch_platform, daemon=True, name="plugin-platform-watch").start()

    def stop(self) -> bool:
        """Stop the cycle: a release during a start is deferred, not dropped."""
        with self._lock:
            if self._starting:
                if not self._stop_requested:
                    self._stop_requested = True
                    self._pending_stop_snapshot = _capture_target_snapshot()
                self._log.debug("[PLUGIN] stop deferred: the start is still in flight")
                return True
            if not self._active:
                self._log.debug("[PLUGIN] stop ignored: no cycle is running")
                return False
        stop_snapshot = _capture_target_snapshot()
        self._log.info(
            "[PLUGIN] stop requested (cycle=#%d, captured=%s)",
            self._cycle,
            self._copy.duration(time.monotonic() - self._t0) if self._t0 else " 0.0s",
        )
        self._stop_and_deliver(target_snapshot=stop_snapshot)
        return True

    def _stop_and_deliver(
        self,
        *,
        trigger: str = "hotkey",
        target_snapshot: Any = None,
    ) -> None:
        with self._lock:
            if self._stopping or not self._active:
                return
            self._stopping = True
            captured = time.monotonic() - self._t0 if self._t0 else 0.0
            cycle = self._cycle
        if target_snapshot is None:
            target_snapshot = _capture_target_snapshot()
        t_stop = time.monotonic()
        try:
            self._stop_meter()
            self._publish_state("transcribing")
            try:
                res = self._post("/stop", timeout=75.0)
            except Exception:
                self._log.exception("[PLUGIN] stop failed (cycle=#%d)", cycle)
                with self._lock:
                    self._active = False
                self._session_events(start=False)
                self._notify(self._copy.STOP_FAILURE_FALLBACK)
                return
            finally:
                self._restore_volume()
            # The page-side split (click vs transcript scrape) is the part the
            # user actually waits through, so it belongs in this log too.
            self._log.info(
                "[PLUGIN] platform returned the transcript (cycle=#%d, trigger=%s, "
                "state=%s, click=%s, scrape=%s)%s",
                cycle,
                trigger,
                res.get("state") or "unknown",
                self._copy.millis(res.get("click_ms")),
                self._copy.millis(res.get("scrape_ms")),
                self._copy.duration(time.monotonic() - t_stop),
            )
            self._finish(
                res,
                cycle=cycle,
                captured=captured,
                elapsed=time.monotonic() - t_stop,
                target_snapshot=target_snapshot,
            )
        finally:
            self._stop_meter()
            with self._lock:
                self._stopping = False

    def _stop_meter(self) -> None:
        meter, self._meter = self._meter, None
        if meter is not None:
            meter.stop()

    def _finish(
        self,
        res: dict,
        *,
        cycle: int | None = None,
        captured: float | None = None,
        elapsed: float | None = None,
        target_snapshot: Any = None,
    ) -> None:
        """Deliver a completed stop response (text, history, paste, cleanup)."""
        text = str(res.get("text", "")).strip()
        duration = float(res.get("duration_s", 0.0) or (time.monotonic() - self._t0))
        with self._lock:
            self._active = False
        cycle = self._cycle if cycle is None else cycle
        self._session_events(start=False)
        if not text:
            # The page-side scrape now returns WHY it is empty (see
            # content.js). "The user said nothing" is a normal outcome, not
            # a failure, and must not wait out the platform timeout.
            reason = str(res.get("empty_reason") or "")
            stopped_with_no_text = reason in ("empty_after_stop", "no_text")
            label = (
                reason
                or ("auto_stopped" if res.get("auto_stopped") else "empty_transcript")
            )
            self._log.warning(
                "[PLUGIN] no transcript (cycle=#%d, reason=%s, page_state=%s)%s",
                cycle,
                label,
                res.get("state_after") or res.get("state") or "unknown",
                self._copy.duration(elapsed) if elapsed is not None else "",
            )
            if stopped_with_no_text:
                self._notify(
                    "The recording ended without any speech, so there is "
                    "no text to paste. Press the hotkey and speak again."
                )
            elif res.get("auto_stopped"):
                self._notify(
                    "The page ended the recording on its own and sent "
                    "no transcription. Speak again in a shorter burst."
                )
            else:
                self._notify(
                    "No transcript arrived in time. Nothing was pasted; "
                    "check the dictation window and try again."
                )
            return
        t_deliver = time.monotonic()
        if target_snapshot is not None and _accepts_kwarg(self._deliver, "target_snapshot"):
            self._deliver(text, duration, target_snapshot=target_snapshot)
        else:
            self._deliver(text, duration)
        self._log.info(
            "[PLUGIN] delivered %d chars (cycle=#%d, captured=%s, platform=%s, delivery=%s)%s",
            len(text),
            cycle,
            self._copy.duration(captured) if captured is not None else self._copy.duration(duration),
            self._copy.duration(elapsed) if elapsed is not None else " n/a",
            self._copy.duration(time.monotonic() - t_deliver),
            self._copy.duration((captured or 0.0) + (elapsed or 0.0)),
        )
        self._clear_prompt_box()

    def _watch_platform(self) -> None:
        """Deliver the capture when the PLATFORM stops the dictation itself.

        The platform ends a dictation on its own (focus loss, its own length cap, a
        page reload). The user did not press anything, so the audio it already
        captured must still be committed, transcribed, pasted and stored --
        otherwise the whole cycle is silently lost. Two consecutive idle reads
        are required so a transient status blip cannot cut a live capture.
        """
        time.sleep(self._host("_PLATFORM_WATCH_GRACE_S", _WATCH_GRACE_S))
        idle_reads = 0
        while True:
            with self._lock:
                if not self._active or self._stopping:
                    return
            status = self._status()
            state = str((status or {}).get("state") or "")
            if state == "recording":
                idle_reads = 0
            elif state in ("idle", "no-page", "unknown"):
                idle_reads += 1
                if idle_reads >= 2:
                    captured = self._copy.duration(time.monotonic() - self._t0) if self._t0 else " 0.0s"
                    browser = str((status or {}).get("browser") or "")
                    if browser == "disconnected" or state == "no-page":
                        # The browser is gone: /stop cannot answer and there is
                        # no page left to scrape. Cancel cleanly; do NOT post a
                        # command that can only return not-recording.
                        with self._lock:
                            self._active = False
                        self._stop_meter()
                        self._restore_volume()
                        self._session_events(start=False)
                        self._log.warning(
                            "[PLUGIN] the dictation window closed mid-capture "
                            "(cycle=#%d, state=%s, captured=%s); nothing was pasted",
                            self._cycle,
                            state,
                            captured,
                        )
                        self._notify(
                            "The dictation window closed before the transcription could be "
                            "saved. Nothing was pasted. Press the hotkey again to record."
                        )
                        return
                    # Not "the platform stopped the dictation": what we KNOW is
                    # that the page left the recording state without the hotkey
                    # being pressed (the screenshot/focus-loss case), so the
                    # capture is committed instead of dropped.
                    self._log.info(
                        "[PLUGIN] the page ended the capture without a stop press "
                        "(state=%s, captured=%s); delivering what it captured",
                        state,
                        captured,
                    )
                    self._stop_and_deliver(trigger="page")
                    return
            time.sleep(self._host("_PLATFORM_WATCH_POLL_S", _WATCH_POLL_S))

    def cancel(self) -> bool:
        """ESC path: abort the session without pasting; clear the page."""
        with self._lock:
            if not self._active:
                return False
            self._active = False
            self._pending_stop_snapshot = None
        self._log.info(
            "[PLUGIN] cycle cancelled (ESC, cycle=#%d, captured=%s)",
            self._cycle,
            self._copy.duration(time.monotonic() - self._t0) if self._t0 else " 0.0s",
        )
        self._stop_meter()
        try:
            self._post("/cancel", timeout=30.0)
        except Exception:
            self._log.debug("[PLUGIN] cancel request failed", exc_info=True)
        self._restore_volume()
        self._session_events(start=False)
        return True

    def _clear_prompt_box(self) -> None:
        """Empty the platform's composer once the text has been delivered.

        The transcript is already pasted into the user's app, so leaving it in
        the platform's prompt box only invites an accidental send. Best effort:
        the next start cleans the box anyway, so a failure is cosmetic.
        """
        try:
            res = self._post("/clear", timeout=10.0)
        except Exception:
            self._log.debug("[PLUGIN] prompt-box clear failed", exc_info=True)
            return
        if not res.get("cleared"):
            self._log.debug("[PLUGIN] prompt box not cleared: %s", res.get("reason") or "unknown")

    def _deliver(
        self,
        text: str,
        duration: float,
        *,
        target_snapshot: Any = None,
    ) -> None:
        if target_snapshot is not None and _accepts_kwarg(deliver_transcription, "target_snapshot"):
            deliver_transcription(
                self._app,
                text,
                duration,
                self._copy.MODEL_LABEL,
                log,
                target_snapshot=target_snapshot,
            )
        else:
            deliver_transcription(self._app, text, duration, self._copy.MODEL_LABEL, log)

    def _session_events(self, *, start: bool) -> None:
        from voice_typer.server import event_bus

        # Visibility belongs to the ONE coordinator policy, never to a
        # provider. Publishing raw bubble_show/bubble_hide here used to
        # hide the always-visible pill at every plugin stop while the
        # coordinator's mirror stayed True.
        state = "recording" if start else "idle"
        bubble = getattr(self._app, "_waveform_bubble", None)
        apply_visibility = getattr(bubble, "apply_visibility", None)
        if callable(apply_visibility):
            apply_visibility(state, reason="plugin-start" if start else "plugin-stop")
        self._publish_state(state)
        event_bus.publish(
            {
                "type": "recording_started" if start else "recording_stopped",
                "data": {"source": self._copy.MODEL_LABEL},
            }
        )

    def _notify(self, msg: str) -> None:
        if not self._copy.notify_enabled():
            return
        try:
            self._app.tray.notify(f"{self._copy.DISPLAY_NAME} (internal)", msg)
        except Exception:
            self._log.debug("[PLUGIN] notify failed", exc_info=True)
