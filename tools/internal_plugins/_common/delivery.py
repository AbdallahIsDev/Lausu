"""Shared transcription delivery for the internal STT plugins.

Separator and first-letter case are DELIVERY concerns only: both go to the
clipboard copy and the paste keystroke, so text dictated into a field that
already has content reads correctly. History, crash recovery,
``_last_transcription`` and ``transcription_final`` keep the decoded text
byte-identical (C-TRANS-2). Sharing this helper keeps that split from drifting
between plugins.
"""

from __future__ import annotations

import logging
import time
from typing import Any


def deliver_transcription(
    app: Any,
    text: str,
    duration: float,
    model_label: str,
    log: logging.Logger,
) -> None:
    """Paste the padded text, store the decoded text, publish the events."""
    # Per-phase timings: delivery was seen taking 0.3s on one dictation and
    # 2.9-3.6s on others with identical text. One DEBUG line splits the four
    # phases so the next slow report is diagnosable from the log alone
    # (C-LOG-6); the INFO outcome line in session.py stays the durable record.
    t0 = time.perf_counter()
    paste_text = text
    try:
        from voice_typer.server.clipboard_target_safety import delivery_text_for_target

        paste_text = delivery_text_for_target(
            text,
            auto_capitalize=getattr(app.config, "auto_capitalize", True),
        )
    except Exception:
        log.debug("[PLUGIN] caret context unavailable, pasting without formatting", exc_info=True)
    t_caret = time.perf_counter()
    try:
        snapshot = app.clipboard.copy(paste_text)
        paste_seq = app.clipboard._clipboard_seq
        app.clipboard.paste(snapshot=snapshot, pasted_text=paste_text, pasted_seq=paste_seq)
    except Exception:
        log.exception("[PLUGIN] paste failed; text stays in clipboard")
    t_paste = time.perf_counter()
    try:
        row_id = app.history_db.add_transcription(
            text,
            duration=duration,
            model=model_label,
            device=getattr(app.config, "device", ""),
            language=getattr(app.config, "language", ""),
            kind="dictation",
            # No plugin-side timing signal reaches this helper today, so
            # processing_seconds stays NULL rather than being fabricated.
        )
        if row_id <= 0:
            log.error("[PLUGIN] history add returned %s", row_id)
        app._last_transcription = text
        from voice_typer.server import event_bus

        event_bus.publish({"type": "transcription_final", "data": {"text": text[:200]}})
        event_bus.publish({"type": "history_changed"})
    except Exception:
        log.exception("[PLUGIN] history store failed")
    t_history = time.perf_counter()
    log.debug(
        "[PLUGIN] delivery phases: caret_ms=%.0f copy_paste_ms=%.0f history_ms=%.0f total_ms=%.0f",
        (t_caret - t0) * 1000,
        (t_paste - t_caret) * 1000,
        (t_history - t_paste) * 1000,
        (t_history - t0) * 1000,
    )
