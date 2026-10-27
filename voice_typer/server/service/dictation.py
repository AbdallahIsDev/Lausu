"""Dictation domain mixin for LausuService."""

import logging
from typing import TYPE_CHECKING

from voice_typer.server._secrets import redact_secret, redact_url
from voice_typer.server.service._base import ServiceMixinBase

if TYPE_CHECKING:
    # ``ForceCancelResult`` is a TypedDict defined in
    from voice_typer.server.service import ForceCancelResult

log = logging.getLogger(__name__)


class DictationMixin(ServiceMixinBase):
    """Dictation-domain service methods."""

    def toggle_dictation(self) -> None:
        """Start or stop dictation."""
        self._app.toggle_dictation()

    def undo_last(self) -> None:
        """Undo the last transcription via backspace keystrokes."""
        self._app.undo_last()

    def repaste_last(self) -> None:
        """Re-paste the last transcription."""
        self._app.repaste_last()

    def force_cancel_transcription(self) -> "ForceCancelResult":
        """Force-cancel a stuck transcription.

        Covers BOTH lanes: the dictation pipeline (``force_recover``) and any
        running media jobs. Media decodes no longer listen to the engine-wide
        abort flag — each job polls its own ``cancel_event`` — so a media job
        would survive the dictation-side recovery alone.

        Returns ``{"success": bool, "message": str}``.
        """
        try:
            self._app.recording.force_recover(force=True)
            self._cancel_media_jobs()
            return {"success": True, "message": "Transcription cancelled."}
        except Exception as exc:
            log.warning("[SERVICE] force_cancel_transcription failed: %s", exc)
            return {"success": False, "message": redact_secret(redact_url(str(exc)))}

    @staticmethod
    def _cancel_media_jobs() -> None:
        """Cancel every running media job (best-effort, never fatal)."""
        try:
            from voice_typer.server.media_ingest.jobs import get_job_manager

            cancelled = get_job_manager().cancel()
            if cancelled:
                log.info("[SERVICE] force-cancel stopped %d media job(s)", len(cancelled))
        except Exception:  # noqa: BLE001, media is optional on this path
            log.debug("[SERVICE] media force-cancel failed", exc_info=True)
