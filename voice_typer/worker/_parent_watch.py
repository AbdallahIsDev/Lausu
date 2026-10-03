"""Orphan self-exit: worker watches the host process that spawned it.

When a host dies without reaping its worker (hard kill, crash), the
worker outlives it, keeps the single-instance lock, and every later
session's spawn fails as a duplicate. The host passes its PID via
``VOICE_TYPER_PARENT_PID`` (see ``worker_shared_env``); this module
polls that PID and fires ``on_gone`` once when it dies. The caller
wires ``on_gone`` to its graceful-shutdown path.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Mapping

log = logging.getLogger("voice_typer.worker")

# Env var set by the Tauri host (both release + dev spawn paths).
PARENT_PID_ENV_VAR = "VOICE_TYPER_PARENT_PID"

# Liveness poll cadence. PID reuse inside one interval is the known
# residual risk (same as the lock's stale-PID recovery): accepted.
POLL_INTERVAL_S = 5.0


def parent_pid_from_env(env: Mapping[str, str] | None = None) -> int | None:
    """Return the host PID from the environment, or ``None`` to disable."""
    raw = (env if env is not None else os.environ).get(PARENT_PID_ENV_VAR)
    if not raw:
        return None
    try:
        pid = int(raw.strip())
    except (TypeError, ValueError):
        log.debug("[WORKER] ignoring unparsable %s=%r", PARENT_PID_ENV_VAR, raw)
        return None
    if pid <= 0:
        return None
    return pid


def is_parent_alive(
    pid: int,
    *,
    _os_name: str | None = None,
    _kill: Callable[[int, int], None] | None = None,
) -> bool:
    """Return True when *pid* looks alive. Fail-alive on uncertainty.

    The ``_os_name``/``_kill`` seams exist so tests can exercise the
    POSIX branch without patching the global ``os`` module (patching
    ``os.name`` process-wide confuses pytest's own thread machinery on
    Windows and hangs the suite).
    """
    name = os.name if _os_name is None else _os_name
    kill = os.kill if _kill is None else _kill
    if name == "posix":
        try:
            kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return True
        return True
    try:
        from voice_typer.server.single_instance import _is_pid_alive
    except ImportError:
        log.debug("[WORKER] pid-alive probe unavailable, assuming parent alive", exc_info=True)
        return True
    try:
        return bool(_is_pid_alive(pid))
    except Exception:
        log.debug("[WORKER] pid-alive probe raised, assuming parent alive", exc_info=True)
        return True


def start_parent_watch(
    *,
    on_gone: Callable[[], None],
    poll_interval: float = POLL_INTERVAL_S,
    stop: threading.Event | None = None,
    _alive_fn: Callable[[int], bool] = is_parent_alive,
    _pid_fn: Callable[[], int | None] = parent_pid_from_env,
) -> threading.Thread | None:
    """Spawn the parent-watch daemon; ``None`` when disabled (no env).

    The watcher fires ``on_gone`` exactly once when the parent dies,
    then exits. ``stop`` terminates the loop early (tests + future
    explicit teardown; production relies on daemon reaping).
    """
    pid = _pid_fn()
    if pid is None:
        log.debug("[WORKER] parent watch disabled (no %s)", PARENT_PID_ENV_VAR)
        return None

    def _watch() -> None:
        while True:
            if stop is not None and stop.is_set():
                return
            try:
                alive = _alive_fn(pid)
            except Exception:
                log.debug("[WORKER] parent-alive probe raised, assuming alive", exc_info=True)
                alive = True
            if not alive:
                # INFO, not WARN: the host exits without reaping the
                # worker first (see on_host_exit), so this fires on
                # every clean quit, not just crashes.
                log.info(
                    "[WORKER] parent process (pid=%d) is gone: shutting down so a new session can spawn",
                    pid,
                )
                try:
                    on_gone()
                except Exception:
                    log.debug("[WORKER] on_gone raised, exiting watch anyway", exc_info=True)
                return
            if stop is not None:
                if stop.wait(timeout=poll_interval):
                    return
            else:
                time.sleep(poll_interval)

    # RACE-008: daemon=True is acceptable, the watch only observes; a
    # dead parent means the process is exiting anyway.
    thread = threading.Thread(target=_watch, name="worker-parent-watch", daemon=True)
    thread.start()
    log.debug("[WORKER] parent watch started (pid=%d, interval=%.1fs)", pid, poll_interval)
    return thread
