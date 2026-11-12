"""Non-blocking startup prewarm for the configured TTS engine.

This module exists so enabling spoken replies pays its 3-4 s runtime start once,
in the background, instead of on the user's first click. It runs ONLY after the
startup sequence has logged its ready marker and it never raises into startup:
a missing pack, a disabled engine, or a failing runtime is one debug line.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

log = logging.getLogger(__name__)


def _configured_engine(config: Any) -> str:
    engine = str(getattr(config, "tts_engine", "off") or "off")
    return engine if engine in ("audio8", "magpie") else ""


def _prewarm_callable(app: Any) -> Any:
    """The TTS service lives on the IPC server, not on the app.

    ``LausuApp`` owns subsystems (config, models, tray); the service mixins —
    including ``TtsMixin.tts_prewarm`` — are composed into ``LausuService``,
    which the IPC server holds as ``.service`` and registers back onto the app
    as ``._ipc_server`` in ``IPCServer.start()``. Calling ``app.service`` raised
    ``AttributeError`` on every startup and was swallowed into a debug line, so
    the warm-up silently never ran.
    """
    server = getattr(app, "_ipc_server", None)
    return getattr(getattr(server, "service", None), "tts_prewarm", None)


def start_prewarm(app: Any) -> threading.Thread | None:
    """Start the prewarm thread when TTS is enabled; return it (tests/teardown)."""
    try:
        config = app.config
    except AttributeError:
        return None
    if not bool(getattr(config, "tts_enabled", False)):
        log.debug("[TTS] prewarm skipped: spoken replies are disabled")
        return None
    engine = _configured_engine(config)
    if not engine:
        log.debug("[TTS] prewarm skipped: no engine selected")
        return None

    def _run() -> None:
        prewarm = _prewarm_callable(app)
        if not callable(prewarm):
            # Startup order is a legitimate reason for this (the phase runs
            # post-ready, but a test or a headless boot may have no server).
            log.debug("[TTS] prewarm skipped: TTS service not attached yet")
            return
        try:
            prewarm(engine)
        except Exception:
            log.debug("[TTS] prewarm failed engine=%s", engine, exc_info=True)

    # daemon=True: a slow runtime must never delay or block app quit (RACE-016).
    thread = threading.Thread(target=_run, name="tts-prewarm", daemon=True)
    thread.start()
    return thread


__all__ = ["start_prewarm"]
