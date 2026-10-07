"""Clipping / peak telemetry for :class:`AudioPipeline` (AUDIO-CLIP)."""

from __future__ import annotations

import contextlib
import logging
import queue
import time
from typing import Any

log = logging.getLogger("voice_typer.server.recording")


class AudioPipelineTelemetryMixin:
    """Clip/peak counters whose storage is owned by :class:`AudioPipeline`.

    The declarations below are the host-provided state contract: the
    values are initialised by ``AudioPipeline.__init__`` and reset by
    ``session_state.reset_session_state``.
    """

    _clip_count: int
    _peak: float
    _last_clip_log_time: float

    def detect_and_emit_clipping(self, recorder: Any, chunk_peak: float) -> None:
        """AUDIO-CLIP: track clipping + push a real-time IPC event.

        The historical ``Recorder._detect_and_emit_clipping`` pure
        delegator was removed: this ``AudioPipeline`` method is invoked
        directly by ``process_audio_chunk``. Extracted from
        ``process_audio_chunk`` for testability and readability. The
        ``audio_clip`` event is throttled to 1 Hz (same as the log) so
        the IPC channel isn't flooded. The event is enqueued on a
        non-blocking ``queue.Queue`` and drained by a dedicated event
        worker thread (see ``capture.AudioCallbackDispatcher``). This
        keeps the audio worker thread off the IPC transport - a slow
        TCP subscriber (or a blocked predecessor renderer) can no longer
        stall the worker and cause ring-buffer overflows / dropped
        audio. ``put_nowait`` + ``queue.Full`` suppression so a
        backed-up event worker can never block the audio thread.

        Side effects: increments ``self._clip_count`` (owned here),
        updates ``self._peak`` and ``self._last_clip_log_time``, may
        push an event to ``recorder._event_queue``.
        """
        if chunk_peak >= 0.99:
            # STATE-OWNERSHIP: clip/peak telemetry lives on THIS pipeline.
            self._clip_count += 1
            if chunk_peak > self._peak:
                self._peak = chunk_peak
            now = time.perf_counter()
            if now - self._last_clip_log_time >= 1.0:
                log.debug(
                    "[RECORDING] Clipping detected: peak=%.4f, count=%d chunks.",
                    chunk_peak,
                    self._clip_count,
                )
                self._last_clip_log_time = now
                with contextlib.suppress(queue.Full):
                    recorder._event_queue.put_nowait(
                        {
                            "type": "audio_clip",
                            "data": {
                                "peak": float(chunk_peak),
                                "count": int(self._clip_count),
                            },
                        }
                    )
