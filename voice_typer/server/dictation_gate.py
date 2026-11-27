"""Application-level dictation gesture gate (all engines).

One source of truth for rapid/out-of-order user input: a burst of presses is
one gesture, presses during a transition are ignored, and a stop immediately
after a start is ignored. Local, cloud and plugin engines all reach it before
their engine-specific state machine.
"""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

PRESS_DEBOUNCE_S = 0.5
MIN_RECORDING_S = 0.35


class DictationGate:
    def __init__(self, clock: Any = time) -> None:
        self._clock = clock
        self._last_press = 0.0
        self.generation = 0

    @staticmethod
    def _engine_state(app: Any) -> str:
        session = getattr(app, "_internal_plugin_active_session", None)
        if session is not None:
            if getattr(session, "_starting", False):
                return "starting"
            if getattr(session, "_stopping", False):
                return "stopping"
            if getattr(session, "_active", False):
                return "recording"
        tray = getattr(app, "tray", None)
        state = getattr(tray, "_state", None)
        value = getattr(state, "value", state)
        if value in ("loading", "starting"):
            return "starting"
        if value == "recording":
            return "recording"
        if value == "transcribing":
            return "stopping"
        return "idle"

    def decide(self, app: Any) -> str:
        """Return 'start', 'stop', 'ignore-burst' or 'ignore-transition'."""
        now = self._clock.monotonic()
        if self._last_press and now - self._last_press < PRESS_DEBOUNCE_S:
            self._last_press = now
            return "ignore-burst"
        self._last_press = now
        state = self._engine_state(app)
        if state in ("starting", "stopping"):
            return "ignore-transition"
        if state == "recording":
            tray = getattr(app, "tray", None)
            started = getattr(tray, "_recording_started_at", None)
            if isinstance(started, (int, float)) and (now - started) < MIN_RECORDING_S:
                return "ignore-transition"
            return "stop"
        self.generation += 1
        return "start"

    def cancel(self) -> None:
        self.generation += 1
        self._last_press = 0.0


def gate_for(app: Any) -> DictationGate:
    gate = getattr(app, "_dictation_gate", None)
    if gate is None:
        gate = DictationGate()
        app._dictation_gate = gate
    return gate


def decide_toggle(app: Any) -> str:
    action = gate_for(app).decide(app)
    if action.startswith("ignore"):
        log.info("[DICTATION-GATE] %s (generation=%d)", action, gate_for(app).generation)
    if action == "start":
        # Shared for local, cloud and plugin starts. The lifecycle hook checks
        # the user origin itself and never blocks dictation.
        try:
            from voice_typer.server.model_lifecycle import on_dictation_start

            on_dictation_start(app)
        except Exception:
            log.debug("[DICTATION-GATE] model lifecycle start hook failed", exc_info=True)
    return action
