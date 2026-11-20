"""Orphan self-exit: a child process watches the host that spawned it.

When a host dies without reaping its child (hard kill, panic, OOM), the
child outlives it and keeps doing the host's work with no UI to stop it —
the worker squats the single-instance lock, the sidecar keeps serving
hotkeys and dictation. The host forwards its PID via
``VOICE_TYPER_PARENT_PID``; this module polls that PID and fires
``on_gone`` exactly once. Each caller wires ``on_gone`` to its own
shutdown path.

Both long-lived children (``voice_typer.worker`` and the Tauri sidecar)
share this one implementation so the liveness contract cannot drift.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Mapping

log = logging.getLogger("voice_typer.parent_watch")

# Env var set by the Tauri host (release + dev spawn paths, worker + sidecar).
PARENT_PID_ENV_VAR = "VOICE_TYPER_PARENT_PID"

# Liveness poll cadence. PID reuse inside one interval is the known
# residual risk (same as the lock's stale-PID recovery): accepted.
POLL_INTERVAL_S = 5.0

# Default tag keeps the worker's lines byte-identical to their
# pre-extraction form; the sidecar passes its own.
DEFAULT_LOG_TAG = "[WORKER]"

DEFAULT_GONE_MESSAGE = "parent process (pid=%d) is gone: shutting down so a new session can spawn"


def parent_pid_from_env(
    env: Mapping[str, str] | None = None,
    *,
    log_tag: str = DEFAULT_LOG_TAG,
) -> int | None:
    """Return the host PID from the environment, or ``None`` to disable."""
    raw = (env if env is not None else os.environ).get(PARENT_PID_ENV_VAR)
    if not raw:
        return None
    try:
        pid = int(raw.strip())
    except (TypeError, ValueError):
        log.debug("%s ignoring unparsable %s=%r", log_tag, PARENT_PID_ENV_VAR, raw)
        return None
    if pid <= 0:
        return None
    return pid


def _read_proc_stat(pid: int) -> str:
    """Read ``/proc/<pid>/stat`` (Linux only, absent on macOS/Windows)."""
    with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
        return handle.read()


def _proc_stat_state(pid: int, *, _read: Callable[[int], str] | None = None) -> str | None:
    """Return field 3 (single-char state) of ``/proc/<pid>/stat``, or ``None``.

    Field 2 (``comm``) is parenthesized and may itself contain spaces or
    ``)``, so the state is parsed AFTER the last ``)`` rather than by a
    fixed field index. Any read/parse failure returns ``None``: the caller
    then keeps its fail-alive verdict (genuine permission/uncertainty
    errors must never be reported as a dead parent).
    """
    read = _read or _read_proc_stat
    try:
        raw = read(pid)
        return raw.rsplit(")", 1)[1].split()[0]
    except (OSError, ValueError, IndexError, AttributeError):
        return None


def is_parent_alive(
    pid: int,
    *,
    _os_name: str | None = None,
    _kill: Callable[[int, int], None] | None = None,
    _proc_state: Callable[[int], str | None] | None = None,
    log_tag: str = DEFAULT_LOG_TAG,
) -> bool:
    """Return True when *pid* looks alive. Fail-alive on uncertainty.

    The ``_os_name``/``_kill`` seams exist so tests can exercise the
    POSIX branch without patching the global ``os`` module (patching
    ``os.name`` process-wide confuses pytest's own thread machinery on
    Windows and hangs the suite). ``_proc_state`` injects the Linux
    ``/proc`` state probe: it is auto-installed ONLY for a real POSIX
    probe (``_os_name is None``), so a test that fakes ``_os_name`` must
    also pass ``_proc_state`` to exercise zombie detection.
    """
    name = os.name if _os_name is None else _os_name
    kill = os.kill if _kill is None else _kill
    state_fn = _proc_state
    if state_fn is None and _os_name is None and name == "posix":
        state_fn = _proc_stat_state
    if name == "posix":
        try:
            kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return True
        # kill(pid, 0) also succeeds for a defunct but unreaped process.
        # On Linux a state of 'Z' means the host already exited, so the
        # child must leave even though no reaper has collected it yet.
        # macOS has no /proc: the read fails, state is None, and the
        # fail-alive behavior is kept (proc_pidinfo would need an
        # unvalidated ctypes binding; see the host-liveness review item).
        if state_fn is not None:
            try:
                state = state_fn(pid)
            except Exception:
                log.debug("%s proc state probe raised, assuming alive", log_tag, exc_info=True)
                state = None
            if state == "Z":
                log.info("%s parent process (pid=%d) is a zombie: treating as gone", log_tag, pid)
                return False
        return True
    try:
        from voice_typer.server.single_instance import _is_pid_alive
    except ImportError:
        log.debug("%s pid-alive probe unavailable, assuming parent alive", log_tag, exc_info=True)
        return True
    try:
        return bool(_is_pid_alive(pid))
    except Exception:
        log.debug("%s pid-alive probe raised, assuming parent alive", log_tag, exc_info=True)
        return True


def start_parent_watch(
    *,
    on_gone: Callable[[], None],
    poll_interval: float = POLL_INTERVAL_S,
    stop: threading.Event | None = None,
    log_tag: str = DEFAULT_LOG_TAG,
    gone_message: str = DEFAULT_GONE_MESSAGE,
    gone_level: int = logging.INFO,
    thread_name: str = "worker-parent-watch",
    _alive_fn: Callable[[int], bool] | None = None,
    _pid_fn: Callable[[], int | None] | None = None,
) -> threading.Thread | None:
    """Spawn the parent-watch daemon; ``None`` when disabled (no env).

    The watcher fires ``on_gone`` exactly once when the parent dies,
    then exits. ``stop`` terminates the loop early (tests + future
    explicit teardown; production relies on daemon reaping).
    """
    alive_fn = _alive_fn or (lambda p: is_parent_alive(p, log_tag=log_tag))
    pid_fn = _pid_fn or (lambda: parent_pid_from_env(log_tag=log_tag))
    pid = pid_fn()
    if pid is None:
        log.debug("%s parent watch disabled (no %s)", log_tag, PARENT_PID_ENV_VAR)
        return None

    def _watch() -> None:
        while True:
            if stop is not None and stop.is_set():
                return
            try:
                alive = alive_fn(pid)
            except Exception:
                log.debug("%s parent-alive probe raised, assuming alive", log_tag, exc_info=True)
                alive = True
            if not alive:
                # Level is the caller's call: routine on every clean
                # worker quit (INFO), a real defect for the sidecar.
                log.log(gone_level, "%s " + gone_message, log_tag, pid)
                try:
                    on_gone()
                except Exception:
                    log.debug("%s on_gone raised, exiting watch anyway", log_tag, exc_info=True)
                return
            if stop is not None:
                if stop.wait(timeout=poll_interval):
                    return
            else:
                time.sleep(poll_interval)

    # RACE-008: daemon=True is acceptable, the watch only observes; a
    # dead parent means the process is exiting anyway.
    thread = threading.Thread(target=_watch, name=thread_name, daemon=True)
    thread.start()
    log.debug("%s parent watch started (pid=%d, interval=%.1fs)", log_tag, pid, poll_interval)
    return thread
