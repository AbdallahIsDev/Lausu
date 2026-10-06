"""PartialTranscriptionBroadcaster: coalescing publisher for live
``transcription_partial`` events.

Split from ``voice_typer.server.streaming`` (create-first); the facade
re-exports the class. The SEC-026 bubble-mirror note stays with the code.

"""

from __future__ import annotations

import contextlib
import logging
import math
import threading
import time

# Same logger object as the pre-split facade (see streaming_assembler).
log = logging.getLogger("voice_typer.server.streaming")

class PartialTranscriptionBroadcaster:
    """Coalescing publisher for live ``transcription_partial`` events.

    During a hidden streaming session the assembler commits words as
    overlapping windows complete (every ``step_seconds``, well under
    1 Hz by construction). The broadcaster turns that committed text
    into ``transcription_partial`` push events WITHOUT blocking the
    streaming worker thread on event-bus fan-out, mirroring the level
    monitor's mic-level push pattern:

    * **latest-value-wins**, ``push(text)`` stores the text in a
      single pending slot; a newer push overwrites an older one.
      The worker drains the slot, so bursts collapse to one publish.
    * **throttled**, at most one publish per
      ``min_interval_seconds`` (default 0.25 s → ≤4 Hz), measured on
      an injectable monotonic clock so tests are deterministic.
    * **unchanged-text suppression**, identical consecutive texts
      are dropped (the committed prefix only grows when a window
      completes).
    * **empty-text suppression**, whitespace-only texts are dropped.

    The worker thread is started lazily on the first eligible push and
    stopped from :meth:`StreamingTranscriptionSession._run`'s ``finally``
    (and again, idempotently, from ``finalize()``), so a cancelled or
    finalized session never leaks a thread. ``flush()`` synchronously
    publishes any pending text bypassing the throttle, called from
    ``finalize()`` so the last partial lands before the final result.
    """

    _WORKER_POLL_SECONDS = 0.25

    def __init__(
        self,
        cycle_id: str = "",
        min_interval_seconds: float = 0.25,
        clock=time.monotonic,
    ):
        self._cycle_id = cycle_id
        self._min_interval_seconds = min_interval_seconds
        self._clock = clock
        self._lock = threading.Lock()
        # latest-value-wins slot: None = nothing pending.
        self._pending_text: str | None = None
        self._last_published_text: str = ""
        # -inf so the FIRST eligible publish is never throttled.
        self._last_publish_ts = -math.inf
        self._wake_event = threading.Event()
        self._stopped = False
        self._thread: threading.Thread | None = None

    def push(self, text: str) -> None:
        """Coalesce *text* into the pending slot and wake the worker.

        Cheap (lock + string compare), safe to call from the streaming
        worker thread after every processed window. Empty and unchanged
        texts never touch the pending slot.
        """
        stripped = (text or "").strip()
        if not stripped:
            return
        with self._lock:
            if stripped == self._last_published_text:
                return
            if self._stopped:
                return
            self._pending_text = stripped
        self._ensure_worker_running()
        self._wake_event.set()

    def flush(self) -> None:
        """Synchronously publish any pending text, bypassing the throttle.

        Called from ``finalize()`` (any thread). Idempotent; safe after
        :meth:`stop`.
        """
        self._publish_eligible(force=True)

    def stop(self) -> None:
        """Signal the worker thread to exit and join it (best-effort).

        Idempotent. After :meth:`stop`, further :meth:`push` calls are
        no-ops but :meth:`flush` still works (it publishes inline).
        """
        with self._lock:
            self._stopped = True
        self._wake_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            with contextlib.suppress(RuntimeError):
                thread.join(timeout=1.0)
            self._thread = None

    def _ensure_worker_running(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._lock:
            if self._stopped or (self._thread is not None and self._thread.is_alive()):
                return
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="StreamingPartialPublisher",
                daemon=True,
            )
            self._thread.start()

    def _worker_loop(self) -> None:
        while True:
            self._wake_event.wait(timeout=self._WORKER_POLL_SECONDS)
            if self._stopped:
                return
            self._wake_event.clear()
            self._publish_eligible()

    def _publish_eligible(self, force: bool = False) -> None:
        """Drain the pending slot and publish it if the throttle allows.

        One step of the worker loop; also the synchronous body of
        :meth:`flush` (with ``force=True``). Exposed with a leading
        underscore so tests can drive single deterministic steps
        against a fake clock instead of racing the worker thread.
        """
        with self._lock:
            text = self._pending_text
            self._pending_text = None
        if text is None or not text.strip():
            return
        now = self._clock()
        if not force and (now - self._last_publish_ts) < self._min_interval_seconds:
            # Too soon, put the text back (a later drain publishes the
            with self._lock:
                if self._pending_text is None:
                    self._pending_text = text
            return
        with self._lock:
            self._last_publish_ts = now
            self._last_published_text = text
        payload: dict[str, str | bool] = {
            "text": text,
            "cycle_id": self._cycle_id,
        }
        try:
            from voice_typer.server import event_bus

            event_bus.publish(
                {"type": "transcription_partial", "data": payload},
            )
        except Exception:
            log.debug(
                "[STREAMING] Failed to publish transcription_partial event",
                exc_info=True,
            )
            return
        # (SEC-026, no python bridge inside the sandboxed bubble
        if force or self._stopped:
            return
        try:
            from voice_typer.server import event_bus

            event_bus.publish(
                {
                    "type": "bubble_set_state",
                    "data": {"state": "recording", "transcript": text},
                },
            )
        except Exception:
            log.debug(
                "[STREAMING] Failed to mirror partial transcript to bubble",
                exc_info=True,
            )
