"""Idle bridge keepalive shared by both internal STT plugins.

Chrome suspends an MV3 service worker after ~30 s of inactivity, and a
suspended worker made the first dictation after a long idle take seconds. A
status round trip is real extension traffic, so it resets that timer; it only
runs while no cycle is being dictated.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

_KEEPALIVE_INTERVAL_S = 20.0


class BridgeKeepalive:
    """Periodic no-op status round trip while the plugin owns dictation.

    Failures are DEBUG only: an idle bridge that is temporarily unreachable is
    not a user-facing event. Status and cycle ownership are injected by the
    entry module, which owns the patchable module-level callables.
    """

    def __init__(
        self,
        interval_s: float = _KEEPALIVE_INTERVAL_S,
        *,
        status_fn: Callable[[], dict | None] | None = None,
        owns_cycle_fn: Callable[[], bool] | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_status: tuple[str, str] | None = None
        self._status_fn = status_fn or (lambda: None)
        self._owns_cycle_fn = owns_cycle_fn or (lambda: False)
        self._log = log or logging.getLogger("voice_typer.internal_plugin.bridge")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        # Keep the last verdict across stop/start: a plugin switch must not
        # re-log an unchanged connected state (Item 4).
        # Daemon: best-effort keepalive must not hold process exit; stop() signals the loop.
        self._thread = threading.Thread(target=self._run, daemon=True, name="plugin-keepalive")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _note_status(self, status: dict | None) -> None:
        # C-LOG-3: a routine keepalive is not an event; log transitions only.
        current = (
            (status or {}).get("browser") or "unknown",
            (status or {}).get("page") or "unknown",
        )
        if current == self._last_status:
            return
        self._last_status = current
        self._log.debug("[PLUGIN] bridge status (browser=%s, page=%s)", *current)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            if self._owns_cycle_fn():
                continue
            self._note_status(self._status_fn())
