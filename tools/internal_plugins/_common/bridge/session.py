"""Dictation state machine shared by both internal STT plugins.

The owning plugin supplies its copy module, daemon client and patchable
module-level callables through ``bind_entry``/constructor injection, so the
hotkey, bubble and delivery flows stay identical on both platforms.
resolve to the entry module even though the logic lives here.
"""

from __future__ import annotations

import contextlib
import inspect
import logging
import threading
import time
from pathlib import Path
from typing import Any

from tools.internal_plugins._common import daemon as _daemon_common
from tools.internal_plugins._common.bridge.daemon_client import DaemonClient
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
_ACTIVATION_PREPARE_TIMEOUT_S = 5.0
_PAGE_READY_TIMEOUT_S = 12.0
_PAGE_READY_POLL_S = 0.1
_START_RETRY_KINDS = frozenset({"browser-not-open", "browser-closed", "wrong-platform"})
# Failures whose cause is invisible when the browser window is hidden: these
# bypass the user's notify preference through one named mechanism (CRITICAL-NOTICE).
_CRITICAL_STOP_KINDS = frozenset({"browser-not-open", "browser-closed", "page-not-ready", "bridge-timeout"})
_START_MAX_RELAUNCHES = 3
# Three cold launches (about 6 s each worst case) plus two short backoffs.
_START_TOTAL_BUDGET_S = 24.0
_START_CLICK_ATTEMPTS = 3
_START_CLICK_RETRY_KINDS = frozenset({"platform-not-recording", "no-recording-indicator"})
# Platform states the user can fix in the browser. They are expected outcomes,
# not crashes: one actionable line, no traceback (C-UXERR-1, C-LOG-3).
_EXPECTED_START_KINDS = frozenset(
    {
        "signed-out",
        "challenge",
        "mic-missing",
        "no-recording-indicator",
        "platform-not-recording",
        "composer-dirty",
        "selectors-missing",
        "page-not-ready",
        "bridge-timeout",
    }
)

log = logging.getLogger("voice_typer.internal_plugin.bridge")

# One process-wide gate: activation (startup/switch thread) and the hotkey
# thread both call launch_profile_if_due. Without a lock both can observe a
# stale timestamp and spawn two Chrome processes -> two extra tabs (P4).
_launch_lock = threading.RLock()
_suppress_exception = contextlib.suppress(Exception)

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
    running_fn: Any | None = None,
    caller: str = "plugin-activation",
) -> tuple[bool, float]:
    """Open the dictation profile at most once per cooldown window (C-START-3).

    ``on_due`` records the timestamp before the launch attempt so a failing
    launch is still bounded. Returns ``(launched, new_timestamp)``.
    """
    with _launch_lock:
        now = clock.monotonic()
        # A running profile is never relaunched: Chrome would append another
        # tab (about:blank or the platform) to an existing window. The
        # extension owns tab resolution once Chrome is up (C-PLUGIN-3).
        if running_fn is not None and running_fn():
            return False, last_ts
        # A profile the user actually closed is reopened immediately; the
        # cooldown only bounds repeat launches against a browser that is down.
        if not (bypass_fn is not None and bypass_fn()) and now - last_ts < cooldown_s:
            return False, last_ts
        if on_due is not None:
            on_due(now)
        config = config_fn()
        configured = str(config.get("profileDir") or "")
        legacy = legacy_profile_dir()
        # A daemon started before the profile rename keeps the OLD path in
        # memory; the migrated path from install.json always wins here.
        profile = str(profile_dir()) if legacy is not None and configured and Path(configured) == legacy else configured
        # The extension is the ONLY tab authority (C-PLUGIN-3). A platform URL
        # on the command line races /ensure-tab on domains that redirect
        # (chatgpt.com/accounts.google.com), so Chrome used to end up with two
        # tabs of the same platform. The launch opens one blank tab, which the
        # extension adopts and navigates to the target URL once.
        url = "about:blank"
        launched = launch_fn(profile, url)
        log.info(
            "[PLUGIN] Chrome launch at=%s caller=%s url=%s pid=%s profile=%s",
            time.strftime("%Y-%m-%dT%H:%M:%S"),
            caller,
            url,
            launched,
            profile,
        )
        return launched, now


def wait_for_page_ready(
    *,
    status_fn: Any,
    ready_fn: Any,
    clock: Any,
    timeout: float | None = None,
    log: Any = None,
    cycle: int = 0,
    reason_out: dict | None = None,
) -> bool:
    """Wait for a clickable dictation control, not just a live socket (P2).

    One status call carries the whole readiness state. Log only on a real
    state transition (no per-poll spam), fail fast on unrecoverable states,
    and keep the overall monotonic budget. The mic gate itself is unchanged.
    """
    budget = _PAGE_READY_TIMEOUT_S if timeout is None else timeout
    started = clock.monotonic()
    deadline = started + budget
    last: tuple[str, ...] | None = None
    streak = 0
    for _ in range(1, int(budget / _PAGE_READY_POLL_S) + 2):
        snapshot = status_fn()
        state = DaemonClient.readiness_state(snapshot)
        key = (
            state["browser"],
            state["tab"],
            state["content_script"],
            state["control"],
            state["signed_in"],
            state["reason"],
        )
        if key != last:
            last = key
            streak = 0
            if log is not None:
                log.info(
                    "[PLUGIN] readiness (cycle=#%d): browser=%s tab=%s content=%s control=%s signed_in=%s reason=%s%s",
                    cycle,
                    *key,
                    f" {max(0.0, clock.monotonic() - started):.1f}s",
                )
        if ready_fn(snapshot):
            streak += 1
            # The same ready verdict on two consecutive probes. A mic that
            # appeared before the platform hydrated must not be clicked.
            if streak >= 2:
                return True
        else:
            streak = 0
        # Terminal states: waiting cannot repair them from the app side.
        if state["signed_in"] == "no" or state["reason"] in (
            "tab.crashed",
            "browser.down",
            "challenge",
            "signed_in.no",
        ):
            if reason_out is not None:
                reason_out["reason"] = state["reason"]
            return False
        if clock.monotonic() >= deadline:
            break
        clock.sleep(_PAGE_READY_POLL_S)
    if reason_out is not None:
        reason_out["reason"] = "page-not-ready"
    return False


def ensure_target_ready(
    *,
    browser_fn: Any,
    post_fn: Any,
    status_fn: Any,
    ready_fn: Any,
    clock: Any,
    timeout: float | None = None,
    log: Any = None,
    cycle: int = 0,
    ensure_timeout: float = 20.0,
    budget: RelaunchBudget | None = None,
    stage: str = "tab",
) -> tuple[bool, str]:
    """ONE idempotent, coalesced step that makes the target tab usable.

    Every start path (hotkey, retry, activation) goes through here. The
    extension is the only tab authority: /ensure-tab adopts a blank launch
    tab or recreates a closed one, and dedupes. A live WebSocket is NOT tab
    readiness, so the real mic-control gate still runs last (P2).
    """
    try:
        browser_ok = browser_fn(budget=budget)
    except TypeError:
        browser_ok = browser_fn()
    if not browser_ok:
        return False, "browser-not-open"
    try:
        post_fn("/ensure-tab", timeout=20.0)
    except BridgeError as exc:
        # An older extension can reject the route; /start still resolves its
        # own tab in that case (fdd3758fd's legacy fallback).
        if "unknown command" not in str(exc).lower():
            if log is not None:
                log.warning(
                    "[PLUGIN] target tab could not be resolved (cycle=#%d): %s",
                    cycle,
                    type(exc).__name__,
                )
            return False, "tab-not-ready"
    except Exception:
        return False, "tab-not-ready"
    reason_out: dict = {"reason": "page-not-ready"}
    for recovery in range(2):
        if not wait_for_page_ready(
            status_fn=status_fn,
            ready_fn=ready_fn,
            clock=clock,
            timeout=timeout,
            log=log,
            cycle=cycle,
            reason_out=reason_out,
        ):
            reason = reason_out["reason"]
            # A profile that dies AFTER transport connected used to fall
            # through as a plain "browser.down" refusal. It is the same
            # recoverable failure as a close during the transport wait.
            if reason in ("browser.down", "tab.missing", "status.unavailable", "browser-not-open"):
                if budget is None or not budget.can_relaunch():
                    return False, "relaunches-exhausted"
                budget.record(stage, reason)
                budget.backoff()
                try:
                    browser_fn(force=True, budget=budget)
                except TypeError:
                    browser_fn()
                continue
            # A discarded or wrong-URL tab cannot heal by waiting: ask the
            # extension to activate/reload it once, then re-run the gate.
            if recovery == 0 and reason in ("tab.discarded", "tab.wrong_url"):
                if log is not None:
                    log.info(
                        "[PLUGIN] target needs recovery (cycle=#%d): %s",
                        cycle,
                        reason,
                    )
                try:
                    post_fn("/ensure-tab", timeout=20.0)
                except Exception:
                    return False, reason
                continue
            return False, reason
        return True, "ready"
    return False, reason_out["reason"]


def activate_platform_async(
    *,
    ensure_daemon_fn: Any,
    status_fn: Any,
    connected_fn: Any,
    post_fn: Any,
    launch_fn: Any,
    ready_fn: Any,
    clock: Any,
    log: Any,
    display_name: str,
) -> None:
    """Boot/warm the bridge off the plugin-selection thread (Item 2).

    The UI activation returns immediately; this thread does the slow daemon
    spawn, the profile launch or /warm, then makes the platform tab ready.
    """
    started = time.perf_counter()
    if not ensure_daemon_fn():
        log.error("[PLUGIN] activation failed: the control daemon did not start")
        return
    daemon_s = time.perf_counter() - started
    status_started = time.perf_counter()
    connected = connected_fn(status_fn())
    status_s = time.perf_counter() - status_started
    if not connected:
        launch_fn()
        log_line = "[PLUGIN] %s activated; the dictation window is starting, the first hotkey press waits for it"
    else:
        warm_started = time.perf_counter()
        try:
            post_fn("/warm", timeout=120.0)
        except BridgeError as exc:
            log.exception("[PLUGIN] activation warm-up failed: %s", exc)
            return
        except Exception:
            log.exception("[PLUGIN] activation warm-up failed")
            return
        status_s += time.perf_counter() - warm_started
        log_line = "[PLUGIN] %s activated; browser is up"
    prepare_started = time.perf_counter()
    ready = prepare_platform(
        status_fn=status_fn,
        post_fn=post_fn,
        connected_fn=connected_fn,
        ready_fn=ready_fn,
        clock=clock,
        timeout=_ACTIVATION_PREPARE_TIMEOUT_S,
    )
    prepare_s = time.perf_counter() - prepare_started
    total_s = time.perf_counter() - started
    log.debug(
        "[PLUGIN] activation stages daemon=%.1fs status=%.1fs prepare=%.1fs total=%.1fs",
        daemon_s,
        status_s,
        prepare_s,
        total_s,
    )
    if ready:
        log.info(log_line + " %.1fs", display_name, total_s)
    else:
        log.warning(
            "[PLUGIN] %s activation preparation incomplete (reason=tab-not-ready) %.1fs; "
            "the first hotkey press resolves the tab",
            display_name,
            total_s,
        )


def prepare_platform(
    *,
    status_fn: Any,
    post_fn: Any,
    connected_fn: Any,
    ready_fn: Any,
    clock: Any,
    timeout: float = 60.0,
    poll_s: float = 0.25,
) -> bool:
    """Make the active platform tab ready after plugin activation (P3).

    Runs off the UI thread. It never launches Chrome: only the extension
    resolves/creates the tab, via /ensure-tab, once the bridge is connected.
    """
    deadline = clock.monotonic() + timeout
    for _ in range(1, int(timeout / poll_s) + 2):
        if connected_fn(status_fn()):
            ok, _reason = ensure_target_ready(
                browser_fn=lambda: True,
                post_fn=post_fn,
                status_fn=status_fn,
                ready_fn=ready_fn,
                clock=clock,
                timeout=max(1.0, deadline - clock.monotonic()),
            )
            if ok:
                return True
        if clock.monotonic() >= deadline:
            break
        clock.sleep(poll_s)
    return False


class RelaunchBudget:
    """One authoritative relaunch counter for a single start request."""

    def __init__(self, clock: Any = time, log: Any = log) -> None:
        self.clock = clock
        self.log = log
        self.started = clock.monotonic()
        self.count = 0
        self.last_reason = ""

    @property
    def expired(self) -> bool:
        return self.clock.monotonic() - self.started >= _START_TOTAL_BUDGET_S

    def can_relaunch(self) -> bool:
        return self.count < _START_MAX_RELAUNCHES and not self.expired

    def record(self, stage: str, reason: str) -> bool:
        self.count += 1
        self.last_reason = reason
        self.log.info(
            "[PLUGIN] relaunch attempt %d/%d stage=%s reason=%s%s",
            self.count,
            _START_MAX_RELAUNCHES,
            stage,
            reason,
            f" {max(0.0, self.clock.monotonic() - self.started):.1f}s",
        )
        return self.can_relaunch()

    def backoff(self) -> None:
        # 0.5 s, then 1 s: short enough to feel immediate, long enough for
        # Chrome's graceful teardown to finish before the next launch.
        self.clock.sleep(0.5 * self.count)


def ensure_browser(
    *,
    status_fn: Any,
    launch_fn: Any,
    ready_fn: Any,
    clock: Any,
    timeout: float | None = None,
    transport_fn: Any | None = None,
    alive_fn: Any | None = None,
    budget: RelaunchBudget | None = None,
    stage: str = "browser",
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
    wait_budget = default_budget if timeout is None else timeout
    deadline = clock.monotonic() + wait_budget
    while clock.monotonic() < deadline:
        if connected(status_fn()):
            return True
        # A profile closed mid-wait must abort NOW, not after the full budget.
        # A start request owns a bounded relaunch; a deliberate close outside a
        # start is never treated as success.
        if alive_fn is not None and not alive_fn():
            if budget is None or not budget.can_relaunch():
                log.warning("[PLUGIN] the dictation profile closed while waiting (%s)", stage)
                return False
            budget.record(stage, "profile-closed")
            budget.backoff()
            try:
                launch_fn(force=True)
            except TypeError:
                launch_fn()
            continue
        clock.sleep(0.5)
    log.error("[PLUGIN] the dictation window did not answer within %.0fs", wait_budget)
    return False


def _fallback_ensure_daemon(client, log):
    return _daemon_common.ensure_daemon(
        Path(client.config_dir),
        client.alive,
        log,
        daemon_script=client.daemon_script,
        cwd=client.daemon_cwd,
        daemon_args=client.daemon_args,
    )


def _fallback_ensure_browser(client):
    return ensure_browser(
        status_fn=client.status,
        launch_fn=lambda: False,
        ready_fn=client.bridge_ready,
        clock=time,
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
        self._start_generation = 0
        self._restart_requested = False
        self._t0 = 0.0
        self._busy = False
        # A push-to-talk release can arrive while the start is still warming
        # up (browser launch, daemon spawn, /start handshake). It must stop as
        # soon as the start lands instead of leaving the platform recording.
        self._stop_requested = False
        self._pending_stop_snapshot: Any = None
        self._critical_notices: set[str] = set()
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
                # RAPID-INPUT RULE: presses during an in-flight transition are
                # ignored, never queued/replayed as the opposite action.
                self._log.info("[PLUGIN] press ignored: a cycle transition is in flight")
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

    def _report_start_failure(self, exc: BridgeError, *, attempts: int = 0) -> None:
        # Deliberately a plain error line: a failed hotkey press is a routine,
        # recoverable event, and the old traceback-per-press buried the actual
        # reason. The traceback stays available at DEBUG.
        # Expected page states (signed out, challenge, missing mic) are routine
        # outcomes the user can act on: one warning line, never a traceback.
        # Unexpected failures keep the error plus DEBUG context.
        if attempts:
            self._log.warning(
                "[PLUGIN] start needs user action (%s, verified clicks=%d): %s",
                exc.kind,
                attempts,
                exc,
            )
        elif exc.kind in _EXPECTED_START_KINDS:
            self._log.warning("[PLUGIN] start needs user action (%s): %s", exc.kind, exc)
        else:
            self._log.error("[PLUGIN] start failed: %s", exc)
            self._log.debug("[PLUGIN] start failure context", exc_info=True)
        hint = self._copy.START_HINTS.get(exc.kind, self._copy.START_FAILURE_FALLBACK)
        if attempts:
            hint = f"{hint} Retried {attempts} times."
        if exc.kind in ("browser-not-open", "browser-closed", "wrong-platform"):
            from tools.internal_plugins._common.bridge.install_paths import install_hint

            hint = f"{hint} {install_hint()}"
        self._notify(hint)

    def _report_stop_failure(self, exc: Exception, cycle: int) -> None:
        """Expected browser/bridge losses get one line and plain copy."""
        kind = getattr(exc, "kind", "") or "bridge-error"
        expected = kind in ("browser-not-open", "page-not-ready", "bridge-timeout", "not-recording")
        if expected:
            self._log.warning(
                "[PLUGIN] stop lost the browser (cycle=#%d, kind=%s): %s",
                cycle,
                kind,
                str(exc)[:120],
            )
        else:
            self._log.error("[PLUGIN] stop failed (cycle=#%d, kind=%s): %s", cycle, kind, exc)
            self._log.debug("[PLUGIN] stop failure context", exc_info=True)
        hints = getattr(self._copy, "STOP_HINTS", {})
        hint = hints.get(kind, self._copy.STOP_FAILURE_FALLBACK)
        if not expected:
            hint = self._copy.STOP_FAILURE_FALLBACK
        if expected and kind in _CRITICAL_STOP_KINDS:
            self._critical_notify(hint, "stop-lost")
        else:
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
            generation = self._start_generation
            self._restart_requested = False
            self._critical_notices.clear()
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
        self._log.info(
            "[PLUGIN] bridge daemon ready (cycle=#%d)%s",
            cycle,
            self._copy.duration(time.monotonic() - t_press),
        )
        budget = RelaunchBudget(clock=time, log=self._log)
        for attempt in range(_START_ATTEMPTS):
            if generation != self._start_generation:
                self._log.info("[PLUGIN] start superseded (cycle=#%d)", cycle)
                return
            # Press-to-dictate: a closed profile is opened here and waited for,
            # so the press ends in a recording instead of a "window closed" toast.
            t_target = time.monotonic()
            ready, reason = ensure_target_ready(
                browser_fn=self._ensure_browser,
                post_fn=self._post,
                status_fn=self._status,
                ready_fn=DaemonClient.page_ready,
                clock=time,
                log=self._log,
                cycle=cycle,
                budget=budget,
                stage="tab",
            )
            if generation != self._start_generation:
                self._log.info("[PLUGIN] start superseded while waiting (cycle=#%d)", cycle)
                return
            if not ready:
                self._log.error(
                    "[PLUGIN] start refused (cycle=#%d): target=%s%s",
                    cycle,
                    reason,
                    self._copy.duration(time.monotonic() - t_target),
                )
                hint = self._copy.START_HINTS.get(reason, self._copy.START_HINTS["page-not-ready"])
                if reason == "relaunches-exhausted":
                    hint = self._copy.START_HINTS["relaunches-exhausted"].format(count=_START_MAX_RELAUNCHES)
                if reason == "relaunches-exhausted":
                    self._critical_notify(hint, "start-gave-up")
                else:
                    self._notify(hint)
                return
            self._log.debug(
                "[PLUGIN] page ready with a live mic control (cycle=#%d)%s",
                cycle,
                self._copy.duration(time.monotonic() - t_target),
            )
            click_attempts = 0
            transient_retry = False
            for click in range(1, _START_CLICK_ATTEMPTS + 1):
                # Re-probe before EVERY click: a toggle that did start may
                # only be slow to report it; a second click would stop it.
                if (self._status() or {}).get("recording"):
                    break
                if click > 1:
                    retry_ready, retry_reason = ensure_target_ready(
                        browser_fn=self._ensure_browser,
                        post_fn=self._post,
                        status_fn=self._status,
                        ready_fn=DaemonClient.page_ready,
                        clock=time,
                        log=self._log,
                        cycle=cycle,
                    )
                    if not retry_ready:
                        self._log.error(
                            "[PLUGIN] start retry %d/%d abandoned (cycle=#%d): target=%s%s",
                            click,
                            _START_CLICK_ATTEMPTS,
                            cycle,
                            retry_reason,
                            self._copy.duration(time.monotonic() - t_target),
                        )
                        self._notify(self._copy.START_HINTS.get(retry_reason, self._copy.START_HINTS["page-not-ready"]))
                        return
                click_attempts = click
                try:
                    self._post("/start", timeout=30.0)
                    break
                except BridgeError as exc:
                    if exc.kind in _START_CLICK_RETRY_KINDS and click < _START_CLICK_ATTEMPTS:
                        self._log.warning(
                            "[PLUGIN] click attempt %d/%d did not start recording (cycle=#%d): %s%s",
                            click,
                            _START_CLICK_ATTEMPTS,
                            cycle,
                            exc.kind,
                            self._copy.duration(time.monotonic() - t_target),
                        )
                        continue
                    # The user can close the profile in the middle of the handshake.
                    # The old audio never existed, so re-resolve the browser and try
                    # once more instead of treating it as a failed dictation.
                    transient = exc.kind in _START_RETRY_KINDS or "extension disconnected" in str(exc).lower()
                    if attempt + 1 < _START_ATTEMPTS and transient:
                        self._log.warning(
                            "[PLUGIN] the browser disconnected while starting (cycle=#%d); reopening and retrying once",
                            cycle,
                        )
                        time.sleep(_START_RETRY_PAUSE_S)
                        transient_retry = True
                        break
                    self._report_start_failure(exc, attempts=click_attempts)
                    return
                except Exception:
                    self._log.exception("[PLUGIN] start failed")
                    self._notify(self._copy.START_FAILURE_FALLBACK)
                    return
            else:
                self._report_start_failure(
                    BridgeError("platform-not-recording", "the platform did not start capturing"),
                    attempts=click_attempts,
                )
                return
            if attempt + 1 < _START_ATTEMPTS and (
                transient_retry or (self._status() or {}).get("browser") != "connected"
            ):
                continue
            break
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
            # A page that already auto-stopped may have lost its tab. Do not
            # POST into a tab that does not exist: report the real cause once.
            state = DaemonClient.readiness_state(self._status())
            if state["browser"] == "down" or state["tab"] == "missing":
                self._report_stop_failure(BridgeError("the target tab is not open", "browser-not-open"), cycle)
                with self._lock:
                    self._active = False
                self._session_events(start=False)
                return
            try:
                res = self._post("/stop", timeout=75.0)
            except Exception as exc:
                self._report_stop_failure(exc, cycle)
                with self._lock:
                    self._active = False
                self._session_events(start=False)
                return
            finally:
                self._restore_volume()
            # The page-side split (click vs transcript scrape) is the part the
            # user actually waits through, so it belongs in this log too.
            self._log.info(
                "[PLUGIN] platform returned the transcript (cycle=#%d, trigger=%s, state=%s, "
                "state_after=%s, reason=%s, control=%s, committed=%s, click=%s, scrape=%s)%s",
                cycle,
                trigger,
                res.get("state") or "unknown",
                res.get("state_after") or "unknown",
                res.get("reason") or "none",
                res.get("control") or "unknown",
                res.get("committed"),
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
            label = reason or ("auto_stopped" if res.get("auto_stopped") else "empty_transcript")
            # The control proof lives in the daemon log; restate it here so a
            # plain "no transcript" cannot look like a wrong stop click.
            verdict = "no-speech" if stopped_with_no_text else "investigate"
            self._log.warning(
                "[PLUGIN] no transcript (cycle=#%d, verdict=%s, reason=%s, page_state=%s, "
                "control=%s, committed=%s, click=%s, scrape=%s)%s",
                cycle,
                verdict,
                label,
                res.get("state_after") or res.get("state") or "unknown",
                res.get("control") or "unknown",
                res.get("committed"),
                self._copy.millis(res.get("click_ms")),
                self._copy.millis(res.get("scrape_ms")),
                self._copy.duration(elapsed) if elapsed is not None else "",
            )
            if stopped_with_no_text:
                self._notify(
                    "The recording ended without any speech, so there is "
                    "no text to paste. Press the hotkey and speak again."
                )
            elif res.get("auto_stopped"):
                self._notify(
                    "The page ended the recording on its own and sent no transcription. Speak again in a shorter burst."
                )
            else:
                self._notify(
                    "No transcript arrived in time. Nothing was pasted; check the dictation window and try again."
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
                        self._critical_notify(
                            "The browser closed while dictating; nothing was captured. Press the hotkey to try again.",
                            "recording-lost",
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
                if self._starting:
                    # ESC during a start aborts it by invalidating its
                    # generation; no deferred action may replay afterwards.
                    self._start_generation += 1
                    self._stop_requested = False
                    self._restart_requested = False
                    self._log.info("[PLUGIN] start cancelled (ESC, cycle=#%d)", self._cycle)
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

    def _critical_notify(self, msg: str, category: str) -> None:
        """One OS toast + one in-app toast, regardless of notify preference.

        Only failures whose cause the user cannot see (a hidden browser dying,
        a bridge drop at stop, giving up after relaunches) may call this.
        """
        key = f"{self._cycle}:{category}"
        if key in self._critical_notices:
            return
        self._critical_notices.add(key)
        try:
            self._app.tray.notify(f"{self._copy.DISPLAY_NAME} (internal)", msg)
        except Exception:
            self._log.debug("[PLUGIN] critical OS notification failed", exc_info=True)
        try:
            from voice_typer.server import event_bus

            event_bus.publish({"type": "plugin_failure", "data": {"message": msg}})
        except Exception:
            self._log.debug("[PLUGIN] critical in-app notification failed", exc_info=True)
