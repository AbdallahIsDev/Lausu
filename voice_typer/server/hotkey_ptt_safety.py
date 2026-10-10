"""Press-to-talk safety timer for the hotkey dispatcher.

Split out of ``voice_typer.server.hotkey_dispatcher`` (one concern per
file). The facade keeps the class, the public names and every
monkeypatch seam; this module owns the moved bodies only.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import Any

from voice_typer.server.branding import APP_NAME
from voice_typer.server.i18n import t as i18n_t

log = logging.getLogger("voice_typer.server.hotkey_dispatcher")


def _facade():
    """The facade module, read at call time so patches on it are honored."""
    from voice_typer.server import hotkey_dispatcher as module

    return module


class HotkeyPttSafetyMixin:
    """Press-to-talk safety timer for ``HotkeyDispatcher``.

    Host-state contract: the declarations below are attributes
    the facade ``__init__`` (or a sibling mixin) owns.
    """

    _PTT_SAFETY_TIMEOUT_SECONDS: float
    _app: Any
    _ptt_safety_timer: threading.Timer | None


    def _start_ptt_safety_timer(self) -> None:
        """Arm the 60s PTT safety timer. Called from
        ``_create_and_start_main_backend`` when PTT mode is active.

        The timer is stored on ``self._ptt_safety_timer`` and canceled by
        ``_cancel_ptt_safety_timer`` (called from ``stop_all`` and on the
        normal key-up stop). If the timer fires, it calls
        ``_on_ptt_safety_timeout`` which auto-stops dictation and surfaces
        a tray notification.
        """
        # cancel any existing timer (e.g. from a previous registration)
        self._cancel_ptt_safety_timer()
        try:
            timer = threading.Timer(
                self._PTT_SAFETY_TIMEOUT_SECONDS,
                self._on_ptt_safety_timeout,
            )
            timer.daemon = True
            timer.name = "PTT-Safety-Timeout"
            self._ptt_safety_timer = timer
            timer.start()
            _facade()._LIVE_PTT_TIMER_DISPATCHERS.add(self)
            log.debug(
                "[HOTKEY] PTT safety timer armed (%.0fs)",
                self._PTT_SAFETY_TIMEOUT_SECONDS,
            )
        except Exception:
            log.debug("[HOTKEY] Failed to arm PTT safety timer", exc_info=True)

    def _cancel_ptt_safety_timer(self) -> None:
        """Cancel the PTT safety timer if armed. Safe to call when no
        timer is active (no-op)."""
        timer = getattr(self, "_ptt_safety_timer", None)
        if timer is not None:
            timer.cancel()
            self._ptt_safety_timer = None
        # Test-harness registry: no live timer remains on this
        _facade()._LIVE_PTT_TIMER_DISPATCHERS.discard(self)

    def _on_ptt_safety_timeout(self) -> None:
        """fired by the PTT safety timer when a recording has
        run for 60s without a stop event. Auto-stops dictation and
        surfaces a tray notification so the user knows the release was
        missed.

        This is a safety net, not a replacement for normal key-up
        detection. The normal stop path (``set_on_release`` callback)
        cancels this timer; if the timer fires, it means the release
        event was lost.
        """
        log.warning(
            "[HOTKEY] PTT release event missed, auto-stopping recording after %.0fs safety timeout",
            self._PTT_SAFETY_TIMEOUT_SECONDS,
        )
        try:
            with contextlib.suppress(Exception):
                self._app._stop_dictation()
            with contextlib.suppress(Exception):
                self._app.tray.notify_safety(
                    APP_NAME,
                    i18n_t("notify.hotkey_dispatcher.ptt_release_missed"),
                )
        except Exception:
            log.exception("[HOTKEY] PTT safety timeout handler failed")
