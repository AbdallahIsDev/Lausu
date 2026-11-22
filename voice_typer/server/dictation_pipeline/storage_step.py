"""History storage stage."""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Any

from voice_typer.server import i18n
from voice_typer.server.branding import APP_NAME
from voice_typer.server.cycle_guard import is_cycle_live

log = logging.getLogger(__name__)


class _StorageStepMixin:
    """Mixin: history DB + crash-recovery storage step."""

    # Set by ``DictationPipeline.__init__`` (``app: Any``). Declared on
    _app: Any
    # Same provision pattern: assigned by ``_OrchestratorMixin.__init__``
    _cycle_id: str
    _duration: float

    def _store_result(self, text: str, *, original_text: str | None = None) -> None:
        """Step 8: Store in history DB and crash recovery.

        ``original_text`` is the Stage A transcript kept alongside a Stage B
        translation (ADR-0030); ``text`` stays the canonical final version.
        """
        # C-CONC-2: a cancel landing after the stage guard's check must
        # still write nothing for this cycle.
        if not is_cycle_live(self._app, self._cycle_id):
            log.warning(
                "[DICTATION] skipping store of late transcription (cycle %s is stale or force-cancelled)",
                self._cycle_id,
            )
            return
        # gate the entire history-DB block on history_enabled.
        history_enabled = getattr(self._app.config, "history_enabled", True)
        if history_enabled:
            try:
                started_at = getattr(self, "_processing_started_at", None)
                processing_seconds = time.perf_counter() - float(started_at) if started_at is not None else None
                row_id = self._app.history_db.add_transcription(
                    text,
                    duration=self._duration,
                    model=self._app.config.model_size,
                    device=self._app.config.device,
                    kind="dictation",
                    # recording_duration_seconds is NOT duplicated: the
                    # existing ``duration`` column already holds it.
                    processing_seconds=processing_seconds,
                    original_text=original_text,
                )
                # add_transcription returns -1 when the writer
                if row_id <= 0:
                    raise RuntimeError(
                        "history_db.add_transcription returned a non-positive row_id "
                        f"({row_id}), writer is unavailable; transcription was NOT persisted"
                    )
                # NO blocking flush on the paste path, the history row
            except Exception:
                log.exception("[PIPELINE] History DB add failed")
                # a-review Finding 2: notify-once flag lives on ``self._app``
                if not getattr(self._app, "_history_fail_notified", False):
                    self._app._history_fail_notified = True
                    with contextlib.suppress(Exception):
                        self._app.tray.notify(
                            APP_NAME,
                            i18n.t("notify.dictation_pipeline.history_save_failed"),
                        )

        if self._app.config.crash_recovery_enabled:
            try:
                # Correlate this entry with the dictation cycle so a
                self._app._crash_recovery.add(text, pasted=False, cycle_id=self._cycle_id)
                # CRASH-SAFE-GAP-B: flush the crash recovery file immediately
                # 2s, not 0.5s: post-inference the disk is often still busy
                # (page cache churn), and a tight timeout warns falsely.
                self._app._crash_recovery.flush(timeout=2.0)
            except Exception:
                log.exception("[PIPELINE] Crash recovery add failed")
                # a-review Finding 2: notify-once flag lives on ``self._app``
                if not getattr(self._app, "_crash_recovery_fail_notified", False):
                    self._app._crash_recovery_fail_notified = True
                    with contextlib.suppress(Exception):
                        self._app.tray.notify(APP_NAME, i18n.t("notify.dictation_pipeline.crash_recovery_save_failed"))

        # Per-correction usage tracking: count this completed dictation
        try:
            self._app.correction_usage.record_dictation()
        except Exception:
            log.warning("[PIPELINE] Failed to record dictation usage", exc_info=True)

        # Save for repaste / undo
        self._app._last_transcription = text

        # Emit transcription_final so renderer can refresh without polling.
        try:
            from voice_typer.server import event_bus

            event_data: dict[str, Any] = {"text": text[:200]}
            quality = getattr(self, "_quality_summary", None)
            if isinstance(quality, dict):
                event_data["quality"] = quality
            event_bus.publish(
                {
                    "type": "transcription_final",
                    "data": event_data,
                }
            )
        except Exception:
            # Non-fatal: paste already succeeded; UI may show stale history.
            log.debug(
                "[PIPELINE] could not publish transcription_final event",
                exc_info=True,
            )

        if self._app.config.log_transcriptions:
            # Previously the first 200 characters of the

            # We now log a non-reversible 12-char SHA-256 prefix of
            import hashlib

            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
            log.info("[TRANSCRIBE] Transcription: hash=%s len=%d", text_hash, len(text))
        else:
            log.info("[TRANSCRIBE] Transcription: %d chars", len(text))
