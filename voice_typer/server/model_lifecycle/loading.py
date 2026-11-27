"""Load orchestration: user-record start, single-flight, shared wait.

All loads run on ONE background daemon thread per trigger, never on the
hotkey/UI thread. Per-kind single-flight means a second trigger cannot start a
parallel load of the same kind; it either skips or waits on the shared rule.
No code here downloads a model.
"""

from __future__ import annotations

import logging
import threading
import time

from . import idle, registry
from .policy import ModelPolicy

log = logging.getLogger(__name__)

_inflight: dict[str, threading.Event] = {}
_lock = threading.Lock()
_cancel = threading.Event()
_threads: list[threading.Thread] = []


def is_cancelled() -> bool:
    """Cooperative abort flag policies can check inside a long load."""
    return _cancel.is_set()


def _mark_use(policy: ModelPolicy) -> None:
    try:
        policy.note_use()
    except Exception:
        log.debug("[LIFECYCLE] %s note_use failed", policy.name, exc_info=True)
    idle.touch(policy.name)


def _load_one_reserved(policy: ModelPolicy, config: object, event: threading.Event) -> bool:
    try:
        if _cancel.is_set():
            return False
        try:
            if policy.is_loaded(config):
                _mark_use(policy)
                return True
            ok = bool(policy.load(config))
            if ok:
                _mark_use(policy)
            return ok
        except Exception:
            log.debug("[LIFECYCLE] load failed kind=%s", policy.name, exc_info=True)
            return False
    finally:
        with _lock:
            _inflight.pop(policy.name, None)
        event.set()


def load_one(policy: ModelPolicy, config: object) -> bool:
    """Single-flight load. False means 'skipped' or 'failed', never an exception."""
    if _cancel.is_set():
        return False
    with _lock:
        if policy.name in _inflight:
            return False
        event = threading.Event()
        _inflight[policy.name] = event
    return _load_one_reserved(policy, config, event)


def load_in_background(kind: str, config: object) -> bool:
    """Start ONE daemon load for ``kind``; False if one is already in flight.

    The slot is reserved under the same lock before the thread starts, so two
    concurrent callers cannot both spawn a loader. The caller never waits and
    this path never downloads a model; it only invokes the registered policy.
    """
    policy = registry.get(kind)
    if policy is None or _cancel.is_set():
        return False
    with _lock:
        if kind in _inflight:
            return False
        event = threading.Event()
        _inflight[kind] = event

    def _run() -> None:
        _load_one_reserved(policy, config, event)

    thread = threading.Thread(target=_run, name=f"model-lifecycle-load-{kind}", daemon=True)
    # daemon=True: a slow load must never delay app quit (RACE-016).
    with _lock:
        _threads.append(thread)
    try:
        thread.start()
    except Exception:
        with _lock:
            _inflight.pop(kind, None)
        event.set()
        log.debug("[LIFECYCLE] %s background load could not start", kind, exc_info=True)
        return False
    return True


def ensure_loaded(kind: str, config: object, timeout_s: float) -> bool:
    """Shared wait rule for the stop/pipeline side.

    Wait for an in-flight load instead of becoming a second loader; then ask
    the policy's own wait verb (ASR delegates to model_manager's bounded
    wait). One documented timeout covers both.
    """
    policy = registry.get(kind)
    if policy is None:
        return False
    with _lock:
        event = _inflight.get(kind)
    if event is not None:
        event.wait(timeout_s)
    try:
        if policy.is_loaded(config):
            _mark_use(policy)
            return True
        if policy.wait(timeout_s) and policy.is_loaded(config):
            _mark_use(policy)
            return True
    except Exception:
        log.debug("[LIFECYCLE] wait failed kind=%s", kind, exc_info=True)
    return False


def on_dictation_start(app: object) -> None:
    """User-record hook. No origin => no-op; never mints one; never downloads."""
    from voice_typer.server import dictation_origin

    if dictation_origin.current() not in dictation_origin.USER_ORIGINS:
        return
    registry.bind_app(app)
    config = getattr(app, "config", None)
    if config is None:
        return
    from .idle import apply_idle_setting

    apply_idle_setting(getattr(config, "model_idle_unload_minutes", 0))

    def _run() -> None:
        for kind in registry.ordered_kinds():
            if _cancel.is_set():
                break
            policy = registry.get(kind)
            if policy is None:
                continue
            try:
                if not policy.applicable(config):
                    continue
                if policy.is_loaded(config):
                    _mark_use(policy)
                    continue
                load_one(policy, config)
            except Exception:
                log.debug("[LIFECYCLE] record-start load failed kind=%s", kind, exc_info=True)

    thread = threading.Thread(target=_run, name="model-lifecycle-start", daemon=True)
    # daemon=True: a slow model load must never block app quit (RACE-016).
    with _lock:
        _threads.append(thread)
    thread.start()


def cancel_loads() -> None:
    _cancel.set()


def join_loaders(timeout_s: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_s
    with _lock:
        threads = list(_threads)
        _threads.clear()
    for thread in threads:
        remaining = max(0.0, deadline - time.monotonic())
        if thread.is_alive():
            thread.join(timeout=remaining)


def _reset_for_tests() -> None:
    global _cancel
    with _lock:
        for event in _inflight.values():
            event.set()
        _inflight.clear()
        _threads.clear()
    _cancel = threading.Event()


__all__ = [
    "cancel_loads",
    "ensure_loaded",
    "is_cancelled",
    "load_in_background",
    "load_one",
    "on_dictation_start",
]
