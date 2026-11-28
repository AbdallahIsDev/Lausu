"""One decision point for the ASR worker process around idle unload.

The worker is the only thing that really returns ASR memory (R9 measured
in-process ``unload()`` as noise-level). Idle unload therefore asks the host
to STOP the worker; the next user start asks it to start again. Crashes are
the mirror image: the host supervisor owns the respawn, this module owns the
event, the notice and the tray state. Both paths use the existing
``worker_unloaded`` / ``worker_crashed`` / ``offline_pack_verified`` events,
so no new IPC name is introduced.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from voice_typer.server import event_bus
from voice_typer.server.branding import APP_NAME
from voice_typer.server.i18n import t
from voice_typer.server.tray_types import AppState

log = logging.getLogger("voice_typer.server.model_lifecycle.worker")

_RESTART_WAIT_SECONDS = 30.0
_STOP_WAIT_SECONDS = 5.0
_CRASH_WINDOW_SECONDS = 60.0
_CRASH_NOTICE_THRESHOLD = 3
_NOTICE_WINDOW_SECONDS = 5.0

_lock = threading.RLock()
_stopping = False
_stop_done = threading.Event()
_stop_done.set()
_intentional_stop = False
_last_pid: int | None = None
_restarted = threading.Event()
_start_inflight = threading.Event()
_crash_times: list[float] = []
_crash_notified = False
_last_notice: dict[str, float] = {}


def _client() -> Any | None:
    try:
        from voice_typer.server.worker_client import get_shared_client

        return get_shared_client()
    except Exception:
        log.debug("[WORKER-LIFE] shared client unavailable", exc_info=True)
        return None


def note_worker_started(payload: object) -> None:
    """A fresh bind heals a crash episode or an intentional stop."""
    global _intentional_stop, _last_pid, _crash_times, _crash_notified
    data = payload if isinstance(payload, dict) else {}
    pid = data.get("pid")
    with _lock:
        if isinstance(pid, int) and pid >= 0:
            _last_pid = pid
        _intentional_stop = False
        _crash_notified = False
        _crash_times.clear()
        _restarted.set()
        _start_inflight.clear()


def is_worker_ready() -> bool:
    """True only when a live worker port exists and we did not stop it."""
    with _lock:
        if _intentional_stop or _stopping:
            return False
    client = _client()
    return bool(client is not None and client.port is not None)


def is_busy() -> bool:
    """Never stop a worker with a decode, load or streaming session in flight."""
    client = _client()
    if client is None:
        return False
    try:
        return bool(client.has_outstanding())
    except Exception:
        log.debug("[WORKER-LIFE] busy probe failed (fail closed to idle)", exc_info=True)
        return False


def _keep_in_memory() -> bool:
    from .registry import current_app

    app = current_app()
    if app is not None and getattr(app, "_shutting_down", False):
        return True
    minutes = getattr(getattr(app, "config", None), "model_idle_unload_minutes", 0)
    return not isinstance(minutes, (int, float)) or minutes <= 0


def _mark_backend_unloaded() -> None:
    """Make the next ``ensure_active_engine_loaded`` actually reload."""
    from .registry import current_app

    app = current_app()
    models = getattr(app, "models", None) if app is not None else None  # C-ATTR-1: one hop at a time
    if models is None:
        return
    try:
        engine = models.active_transcriber()
        if engine is not None and getattr(engine, "worker_backed", False):
            engine._loaded = False
    except Exception:
        log.debug("[WORKER-LIFE] backend unload mark failed", exc_info=True)


def request_idle_stop() -> bool:
    """Stop the worker for an ASR idle deadline. Idempotent and busy-safe."""
    global _stopping, _intentional_stop
    with _lock:
        if _stopping or _intentional_stop:
            return True
        if _keep_in_memory():
            log.info("[WORKER-LIFE] keep-in-memory is on (0 minutes): worker not stopped")
            return False
    if is_busy():
        log.info("[WORKER-LIFE] idle stop deferred: worker is busy")
        return False
    with _lock:
        _stopping = True
    _stop_done.clear()
    try:
        client = _client()
        if client is not None:
            # Fail every blocked waiter; a stop must never hang a dictation.
            client.abort_all_outstanding()
            client.close()
        _mark_backend_unloaded()
        event_bus.publish({"type": "worker_unloaded", "data": {"reason": "idle_timeout"}})
        with _lock:
            _intentional_stop = True
        log.info("[WORKER-LIFE] idle stop requested (worker_unloaded published)")
        return True
    except Exception:
        log.warning("[WORKER-LIFE] idle stop failed", exc_info=True)
        return False
    finally:
        with _lock:
            _stopping = False
        _stop_done.set()


def request_start(reason: str = "idle_reload") -> bool:
    """Ask the host to (re)spawn the worker and wait for the new bind."""
    # A press during a stop must wait for worker_unloaded to reach the
    # host first; otherwise the host could start the new child and then
    # kill it with the older stop signal.
    _stop_done.wait(_RESTART_WAIT_SECONDS)
    with _lock:
        if not _intentional_stop and _restarted.is_set():
            client = _client()
            if client is not None and client.port is not None:
                return True
        if _start_inflight.is_set():
            return _restarted.wait(_RESTART_WAIT_SECONDS)
        _start_inflight.set()
        _restarted.clear()
    try:
        # ``offline_pack_verified`` is the existing host trigger for
        # ``start_worker_if_ready`` (stop-first + spawn + port relay).
        event_bus.publish({"type": "offline_pack_verified", "data": {"reason": reason}})
        ok = _restarted.wait(_RESTART_WAIT_SECONDS)
        if not ok:
            _notify_once(
                "restart_failed",
                "notify.worker.restart_failed",
                "state.worker.restart_failed",
                click_path="/settings",
            )
        return ok
    finally:
        with _lock:
            _start_inflight.clear()


def _notice_allowed(key: str) -> bool:
    now = time.monotonic()
    with _lock:
        last = _last_notice.get(key)
        if last is not None and now - last < _NOTICE_WINDOW_SECONDS:
            return False
        _last_notice[key] = now
    return True


def _notify_once(key: str, message_key: str, state_key: str, *, click_path: str | None = None) -> None:
    """One in-app + tray notice per episode; worker loss is critical."""
    if not _notice_allowed(key):
        return
    message = t(message_key)
    data: dict[str, Any] = {
        "title": APP_NAME,
        "message": message,
        "duration_ms": 0,
        "critical": True,
    }
    if click_path:
        data["click_path"] = click_path
    try:
        event_bus.publish({"type": "notification", "data": data})
    except Exception:
        log.debug("[WORKER-LIFE] in-app notice failed", exc_info=True)
    try:
        from .registry import current_app

        app = current_app()
        log.info("[WORKER-LIFE] critical tray notice app_bound=%s", app is not None)
        if app is not None:
            app.tray.set_state(AppState.ERROR, t(state_key))
            app.tray.notify_safety(APP_NAME, message)
    except Exception:
        log.debug("[WORKER-LIFE] tray notice failed", exc_info=True)


def note_connection_lost(*, generation: int | None = None) -> None:
    """The worker WS session died. Publish ONE crash event, never respawn here."""
    global _crash_times, _crash_notified
    if generation is not None:
        client = _client()
        if client is not None:
            with client._lock:
                if generation != client._generation:
                    log.info("[WORKER-LIFE] stale worker generation ended: ignoring")
                    return
    log.info("[WORKER-LIFE] worker connection ended; classifying crash episode")
    with _lock:
        if _intentional_stop or _stopping:
            log.info("[WORKER-LIFE] connection loss during intentional stop: no crash notice")
            return
        now = time.monotonic()
        _crash_times = [stamp for stamp in _crash_times if now - stamp < _CRASH_WINDOW_SECONDS]
        _crash_times.append(now)
        count = len(_crash_times)
        pid = _last_pid if _last_pid is not None else -1
        first = not _crash_notified
        _crash_notified = True
    if first:
        client = _client()
        if client is not None:
            try:
                # Wake every blocked waiter instead of letting a dead
                # worker hold the dictation until the 120 s future timeout.
                client.abort_all_outstanding()
            except Exception:
                log.debug("[WORKER-LIFE] could not abort outstanding requests", exc_info=True)
        published = event_bus.publish({"type": "worker_crashed", "data": {"pid": pid, "exit_code": -1}})
        log.info(
            "[WORKER-LIFE] worker_crashed published=%s subscribers=%d",
            published,
            event_bus._subscriber_count(),
        )
        _notify_once("crashed", "notify.worker.crashed", "state.worker.crashed", click_path="/settings")
    if count >= _CRASH_NOTICE_THRESHOLD:
        log.error("[WORKER-LIFE] worker crashed %d times in %.0fs", count, _CRASH_WINDOW_SECONDS)
        _notify_once(
            "restart_failed",
            "notify.worker.restart_failed",
            "state.worker.restart_failed",
            click_path="/settings",
        )


def reset_for_tests() -> None:
    global _intentional_stop, _stopping, _last_pid, _crash_times, _crash_notified
    with _lock:
        _stopping = False
        _intentional_stop = False
        _crash_notified = False
        _last_pid = None
        _crash_times = []
        _stop_done.set()
        _last_notice.clear()
        _restarted.clear()
        _start_inflight.clear()


__all__ = [
    "is_busy",
    "is_worker_ready",
    "note_connection_lost",
    "note_worker_started",
    "request_idle_stop",
    "request_start",
    "reset_for_tests",
]
