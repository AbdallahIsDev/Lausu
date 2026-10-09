"""VolumeController facade over platform backends."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

# import the canonical smart-duck poll-interval default and the
from voice_typer.server.volume_ducker import _DEFAULT_SMART_DUCK_POLL_MS, DEFAULT_DUCK_LEVEL

if TYPE_CHECKING:
    # TYPE_CHECKING-only import so the back-reference type-checks without
    from voice_typer.server.app import LausuApp

log = logging.getLogger(__name__)


class VolumeController:
    """§5.3: extracted from ``LausuApp``. The app passes itself
    The VolumeDucker is constructed in ``LausuApp.__init__`` (NOT
    """

    def __init__(self, app: LausuApp | Any) -> None:
        self._app = app

    def _on_volume_crash_restore(self, state: Any) -> None:
        """Callback invoked when a stale duck crash-recovery file is found.

        Deliberately silent (user decision): no OS notification, the
        restore is routine self-healing, not something the user must
        act on. The outcome stays observable in the log file.
        """
        try:
            pct = int(state.linear * 100)
        except Exception:
            pct = -1
        log.info("[VOLUME] System volume was restored after a crash (to %d%%).", pct)

    def _duck_volume(self) -> None:
        """Duck system volume at the start of dictation."""
        app = self._app
        if not getattr(app.config, "volume_duck_enabled", True):
            return
        try:
            # smart duck is always on when ducking is enabled.
            app._volume_ducker.set_smart_duck_enabled(True)
            # poll interval comes from config (backend floors it).
            app._volume_ducker.set_smart_duck_poll_interval(
                getattr(app.config, "volume_duck_smart_poll_interval_ms", _DEFAULT_SMART_DUCK_POLL_MS)
            )
            if app._volume_ducker.initialize():
                app._volume_ducker.duck(
                    level=getattr(app.config, "volume_duck_level", DEFAULT_DUCK_LEVEL),
                    fade_ms=getattr(app.config, "volume_duck_fade_ms", 200),
                    # per-session removed, always master-volume duck.
                    per_session=False,
                )
        except Exception:
            log.debug("[VOLUME] duck failed", exc_info=True)

    def _restore_volume(self, fade_ms: int | None = None) -> None:
        """Restore system volume at the end of dictation."""
        app = self._app
        if not getattr(app.config, "volume_duck_enabled", True):
            return
        try:
            if fade_ms is None:
                fade_ms = getattr(app.config, "volume_duck_fade_ms", 200)
            app._volume_ducker.restore(
                fade_ms=fade_ms,
                # per-session removed, always master-volume restore.
                per_session=False,
            )
        except Exception:
            log.debug("[VOLUME] restore failed", exc_info=True)
