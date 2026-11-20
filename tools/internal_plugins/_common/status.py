"""Drive the app's canonical tray status from an internal plugin cycle.

The sidebar dot, Home pill and tray tooltip all read ``app.tray.state``; the IPC
server turns every ``tray.set_state`` into a ``status_change`` push. Plugins that
only publish bubble events leave that authority at idle (owner report 2026-11-19).
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("voice_typer.internal_plugin.common.status")

_STATES = {
    "recording": "RECORDING",
    "transcribing": "TRANSCRIBING",
    "idle": "IDLE",
    "error": "ERROR",
    "cancelling": "CANCELLING",
    "loading": "LOADING",
}


def set_cycle_state(app: Any, state: str, message: str = "") -> None:
    """Set tray state for a plugin cycle. Never raises: status is best-effort."""
    from voice_typer.server.tray_types import AppState

    try:
        app.tray.set_state(getattr(AppState, _STATES.get(state, "IDLE")), message)
    except Exception as exc:
        log.debug("[PLUGIN] tray state update failed (%s)", exc)
