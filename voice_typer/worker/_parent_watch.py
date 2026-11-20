"""Worker-side re-export of the shared parent watch.

The watch lives in :mod:`voice_typer.server.parent_watch`: the Tauri
sidecar needs the identical liveness contract, and one implementation
cannot drift from itself.
"""

from __future__ import annotations

from voice_typer.server.parent_watch import (  # noqa: F401 - re-exported
    DEFAULT_GONE_MESSAGE,
    DEFAULT_LOG_TAG,
    PARENT_PID_ENV_VAR,
    POLL_INTERVAL_S,
    is_parent_alive,
    parent_pid_from_env,
    start_parent_watch,
)

__all__ = [
    "DEFAULT_GONE_MESSAGE",
    "DEFAULT_LOG_TAG",
    "PARENT_PID_ENV_VAR",
    "POLL_INTERVAL_S",
    "is_parent_alive",
    "parent_pid_from_env",
    "start_parent_watch",
]
