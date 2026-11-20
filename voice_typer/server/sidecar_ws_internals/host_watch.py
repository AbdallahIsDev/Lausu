"""Host-liveness watch for the Tauri sidecar.

Under ``TAURI_SIDECAR=1`` the IPC heartbeat watchdog is deliberately
skipped (the Rust host owns liveness), so a host that dies abnormally —
panic, taskkill, OOM — leaves the sidecar serving hotkeys, the plugin
bridge and dictation with no window and no tray icon. The host forwards
its PID via ``VOICE_TYPER_PARENT_PID``; when that PID dies this watch
runs the ordinary ``app.quit()`` teardown, so nothing can dictate while
the application is closed.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from voice_typer.server.parent_watch import (
    PARENT_PID_ENV_VAR,
    POLL_INTERVAL_S,
    is_parent_alive,
    parent_pid_from_env,
    start_parent_watch,
)

if TYPE_CHECKING:  # pragma: no cover - type-checker-only
    from voice_typer.server.ipc_server import IPCServer

log = logging.getLogger("voice_typer.server.sidecar_ws")

LOG_TAG = "[SIDECAR-WS]"

GONE_MESSAGE = "host process (pid=%d) is gone: shutting down so nothing can dictate while the application is closed"

# ``app.quit()`` runs the full teardown, itself bounded at ~20s; this is
# the outer bound so one wedged teardown step cannot keep the orphan alive.
FORCE_EXIT_GRACE_S = 30.0

_EXIT_GUARD_NAME = "sidecar-host-exit-guard"


def _arm_force_exit(
    grace_s: float,
    exit_fn: Callable[[int], None],
    cancel: threading.Event | None = None,
) -> threading.Thread:
    """RACE-013: daemon waiting on an Event, never a one-shot Timer."""

    stop = cancel if cancel is not None else threading.Event()

    def _guard() -> None:
        if stop.wait(grace_s):
            return
        log.warning(
            "%s still alive %.1fs after host loss, calling os._exit(0) to guarantee the orphan dies",
            LOG_TAG,
            grace_s,
        )
        exit_fn(0)

    thread = threading.Thread(target=_guard, name=_EXIT_GUARD_NAME, daemon=True)
    thread.start()
    return thread


def make_on_gone(
    server: IPCServer,
    *,
    force_exit_grace_s: float = FORCE_EXIT_GRACE_S,
    _exit_fn: Callable[[int], None] = os._exit,
    _guard_cancel: threading.Event | None = None,
) -> Callable[[], None]:
    """Build the host-loss handler bound to *server* + an exit callable."""

    def _on_gone() -> None:
        app = getattr(server, "app", None)
        if app is None:
            # Early-bind: only the listener exists (no config, no model,
            # no hotkeys), so there is nothing to tear down.
            log.warning("%s host process is gone before app construction: exiting", LOG_TAG)
            _exit_fn(0)
            return
        # Arm the outer bound BEFORE quit(): a hang inside one teardown
        # step must not resurrect the orphan.
        _arm_force_exit(force_exit_grace_s, _exit_fn, cancel=_guard_cancel)
        try:
            app.quit()
        except Exception:
            log.warning("%s app.quit() raised after host loss", LOG_TAG, exc_info=True)
        # ``quit()`` on a non-main thread arms its own watchdog
        # (SHUTDOWN_WATCHDOG_TIMEOUT_S) after cleanup, so the process
        # still exits even when the main thread never unwinds.

    return _on_gone


def install_host_watch(
    server: IPCServer,
    *,
    on_gone: Callable[[], None] | None = None,
    poll_interval: float = POLL_INTERVAL_S,
    force_exit_grace_s: float = FORCE_EXIT_GRACE_S,
    _pid_fn: Callable[[], int | None] | None = None,
    _alive_fn: Callable[[int], bool] | None = None,
    _exit_fn: Callable[[int], None] = os._exit,
) -> threading.Thread | None:
    """Start the watch; ``None`` when the host passed no PID."""
    handler = on_gone or make_on_gone(
        server,
        force_exit_grace_s=force_exit_grace_s,
        _exit_fn=_exit_fn,
    )
    return start_parent_watch(
        on_gone=handler,
        poll_interval=poll_interval,
        log_tag=LOG_TAG,
        gone_message=GONE_MESSAGE,
        gone_level=logging.WARNING,
        thread_name="sidecar-host-watch",
        _alive_fn=_alive_fn or (lambda p: is_parent_alive(p, log_tag=LOG_TAG)),
        _pid_fn=_pid_fn or (lambda: parent_pid_from_env(log_tag=LOG_TAG)),
    )


__all__ = [
    "FORCE_EXIT_GRACE_S",
    "GONE_MESSAGE",
    "LOG_TAG",
    "PARENT_PID_ENV_VAR",
    "install_host_watch",
    "make_on_gone",
]
