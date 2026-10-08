"""Audio worker loop and its start/stop lifecycle bodies.

Split out of :mod:`.capture` by a create-first split: the
:class:`AudioCallbackDispatcher` facade composes :class:`_AudioWorkerMixin`,
so the audio worker thread loop (``audio_worker_loop``) and its two lifecycle
bodies (``start_audio_worker_body`` / ``stop_audio_worker_body``) live here,
while ``capture`` keeps the RT callback dispatch and the IPC event worker.

``_DRAIN_STOP_CHECK_INTERVAL`` stays owned by the ``capture`` facade and is
read here at call time, so tests patching the facade's module state keep
taking effect (C-ARCH-2 owning-module seam).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from voice_typer.server.log_rate_limit import log_rate_limited

# All submodules use the package-level logger so log records propagate.
log = logging.getLogger("voice_typer.server.recording")


class _AudioWorkerMixin:
    """Audio worker thread concerns of :class:`capture.AudioCallbackDispatcher`.

    The facade composes this mixin; every body receives the owning
    ``recorder`` as a parameter, so no host state is declared.
    """

    def audio_worker_loop(
        self,
        recorder: Any,
        stop_event: Any = None,
        wake_event: Any = None,
    ) -> None:
        """Audio worker thread main loop (the thread target used by
        :meth:`start_audio_worker_body`).

        Consumes chunks from the SPSC ring buffer and runs the heavy
        processing pipeline (filter chain, VAD, resample, state machine,
        callbacks). This thread is the SINGLE consumer, the audio
        callback is the single producer, so no locks are needed for the
        ring buffer access (collections.deque append/popleft are atomic
        under CPython's GIL for SPSC).

        Shutdown: exits when ``_worker_stop_event`` is set. The loop
        drains the ring buffer fully before exiting so ``stop()``
        doesn't lose in-flight audio (unless ``drain=False`` was passed
        to ``_stop_audio_worker``, in which case the ring buffer was
        already cleared by the caller).

        Before entering the main drain loop, this worker drains
        ``recorder._preroll_buffer`` in reverse, runs each chunk
        through ``recorder._audio_processor.process_chunk`` (best-effort
        filter chain), and ``appendleft`` to ``recorder._buffer`` —
        the same work ``_prepend_preroll_to_buffer`` used to do
        synchronously on the start() thread. Moving the prepend here
        unblocks start() (which previously blocked 465ms-4.65s on the
        prepend) while preserving chronological order: pre-roll chunks
        land at the front of ``_buffer`` BEFORE any live chunk (live
        chunks only reach ``_buffer`` via ``_process_audio_chunk`` in
        the main drain loop below). The ring buffer (sized for 2.0s of
        headroom) absorbs the prepend duration, live audio chunks
        queued by the callback during the prepend are drained
        immediately after the prepend finishes.
        """
        # Call-time facade read so a patched ``capture._DRAIN_STOP_CHECK_INTERVAL``
        # still takes effect (C-ARCH-2 owning-module seam).
        from .capture import _DRAIN_STOP_CHECK_INTERVAL

        # Prefer explicit ``stop_event`` / ``wake_event`` (captured
        _stop = stop_event if stop_event is not None else recorder._worker_stop_event
        _wake = wake_event if wake_event is not None else recorder._worker_wake_event
        # Moved off the start() thread to avoid blocking the hotkey
        try:
            recorder._session_state.prepend_preroll_to_buffer(recorder)
        except Exception:
            log.warning(
                "[RECORDING] Pre-roll prepend failed on audio worker thread",
                exc_info=True,
            )

        while True:
            # Wait for work or stop signal. The 50ms timeout ensures we
            if not _stop.is_set():
                _wake.wait(timeout=0.05)
            _wake.clear()

            # Drain all available chunks. Each chunk is processed by
            _drain_count = 0
            while True:
                try:
                    chunk_data = recorder._ring_buffer.popleft()
                except IndexError:
                    break
                try:
                    recorder._process_audio_chunk(*chunk_data)
                except Exception:
                    # Log and continue, a single bad chunk must NOT kill
                    log_rate_limited(
                        log,
                        logging.ERROR,
                        "[RECORDING] Audio worker thread error processing chunk",
                        exc_info=True,
                    )
                _drain_count += 1
                if _drain_count % _DRAIN_STOP_CHECK_INTERVAL == 0:
                    if _stop.is_set():
                        return  # bail out early when stop signaled
                    time.sleep(0)  # yield GIL to reduce CPU burn

            # Check for shutdown. We drain the ring buffer fully before
            if _stop.is_set():
                return


    def start_audio_worker_body(self, recorder: Any) -> None:
        """Body of :meth:`Recorder._start_audio_worker` (inside the
                ``_worker_lifecycle_lock`` block).

        Extracted from :mod:`.recorder`. The lock
                acquisition lives on the kept hybrid
                ``Recorder._start_audio_worker`` wrapper (pinned by
                ``tests/test_recorder_worker_lifecycle.py::test_start_audio_worker_holds_lock``);
                this method is the body inside the lock. Idempotent: if the
                worker is already running, returns early.

                Called by ``Recorder._start_audio_worker`` (from
                ``recording_lifecycle.start_recording``) AFTER the PortAudio stream is
                successfully opened and ``_recording_event`` is set
                (the callback needs the event set before it will push
                to the ring buffer). The pre-roll filter-chain prepend
                is NO LONGER done synchronously on the start() thread —
                the worker thread performs the prepend as a "phase 0"
                at the top of ``audio_worker_loop`` before entering the
                main drain loop. The worker thread is a daemon so it
                never blocks process exit.

                THREAD-REGISTRY: when a registry was provided to ``__init__``,
                the worker thread is registered so ``shutdown_all()`` can
                signal and join it during ``LausuApp.quit()``. The
                registry entry is removed by :meth:`stop_audio_worker_body`
                after the join completes (or times out) so a subsequent
                ``start()`` re-registers cleanly without triggering the
                "Re-registering name" warning.

        the entire read-check-create-start sequence is wrapped
                in ``_worker_lifecycle_lock`` (acquired by the caller on
                ``Recorder._start_audio_worker``) so concurrent
                ``start()`` / ``stop()`` / ``discard()`` callers cannot race
                on ``_worker_thread`` (both readers seeing ``None``, the
                starter creating+assigning a fresh worker, the stopper
                returning early and leaving that worker untracked).
        """
        from .recorder import (
            _AUDIO_WORKER_JOIN_TIMEOUT_S,
            _AUDIO_WORKER_THREAD_NAME,
        )

        # the caller holds ``_worker_lifecycle_lock`` across the
        if recorder._worker_thread is not None and recorder._worker_thread.is_alive():
            return
        # Reset stop event (in case a previous stop() left it set)
        recorder._worker_stop_event.clear()
        recorder._worker_wake_event.clear()
        # Clear the ring buffer of any stale chunks from a previous session.
        for _payload in recorder._ring_buffer:
            _arr = _payload[0] if isinstance(_payload, tuple) else _payload
            if hasattr(_arr, "fill") and hasattr(_arr, "shape"):
                _arr.fill(0)
        recorder._ring_buffer.clear()
        recorder._worker_thread = threading.Thread(
            target=self.audio_worker_loop,
            # Pass the CURRENT stop / wake events as explicit
            args=(recorder, recorder._worker_stop_event, recorder._worker_wake_event),
            name=_AUDIO_WORKER_THREAD_NAME,
            daemon=True,
        )
        # Thread-ownership tag (test-leak-guard support): attach the
        recorder._worker_thread._vt_owner_recorder = recorder
        recorder._worker_thread.start()
        # THREAD-REGISTRY: register the freshly-started worker so the
        if recorder._thread_registry is not None:
            recorder._thread_registry.register(
                name=_AUDIO_WORKER_THREAD_NAME,
                thread=recorder._worker_thread,
                stop_event=recorder._worker_stop_event,
                join_timeout=_AUDIO_WORKER_JOIN_TIMEOUT_S,
            )


    def stop_audio_worker_body(self, recorder: Any, *, timeout: float, drain: bool = True) -> None:
        """Body of :meth:`Recorder._stop_audio_worker` (inside the
                ``_worker_lifecycle_lock`` block).

        Extracted from :mod:`.recorder`. The lock
                acquisition lives on the kept hybrid
                ``Recorder._stop_audio_worker`` wrapper (pinned by
                ``tests/test_recorder_worker_lifecycle.py::test_stop_audio_worker_holds_lock``
                and
                ``tests/test_recorder_worker_lifecycle.py::test_stop_audio_worker_does_not_hold_self_lock_across_join``);
                this method is the body inside the lock.

                Parameters
                ----------
                timeout : float
                    Maximum seconds to wait for the worker to exit.
                drain : bool
                    If True (default, used by ``stop()``), the worker drains the
                    ring buffer fully before exiting so no in-flight audio is
                    lost. If False (used by ``discard()``), the ring buffer is
                    cleared first so the worker exits immediately after its
                    current chunk.

                Safe to call when the worker is not running (no-op).

                THREAD-REGISTRY: unregisters the worker after the join so a
                subsequent :meth:`start_audio_worker_body` re-registers cleanly.

        the entire read-check-clear-join-unregister sequence is
                wrapped in ``_worker_lifecycle_lock`` (acquired by the caller
                on ``Recorder._stop_audio_worker``) (NOT ``self._lock``) so
                concurrent ``stop()`` / ``discard()`` callers cannot both read
                ``_worker_thread is None`` and both return early leaving a
                fresh worker untracked. ``self._lock`` is intentionally NOT
                held across ``thread.join()``: the worker thread acquires
                ``self._lock`` inside ``_process_audio_chunk`` for the buffer
                append, so holding it across ``join()`` would deadlock. This
        body does NOT acquire ``self._lock`` (the negative source check
                in ``tests/test_capture_worker_lifecycle.py`` forbids the
                lock literal in this body).
        """
        from .recorder import _AUDIO_WORKER_THREAD_NAME

        # the caller holds ``_worker_lifecycle_lock`` across the
        if recorder._worker_thread is None:
            # Still reset the stop event so the next start() is clean.
            recorder._worker_stop_event.clear()
            return
        if not drain:
            # discard() path: clear the ring buffer so the worker has
            for _payload in recorder._ring_buffer:
                _arr = _payload[0] if isinstance(_payload, tuple) else _payload
                if hasattr(_arr, "fill") and hasattr(_arr, "shape"):
                    _arr.fill(0)
            recorder._ring_buffer.clear()
        # Signal the worker to stop.
        recorder._worker_stop_event.set()
        # Wake the worker in case it's blocked on the wait event.
        recorder._worker_wake_event.set()
        # Join with timeout. If the worker doesn't exit in time (e.g.,
        recorder._worker_thread.join(timeout=timeout)
        if recorder._worker_thread.is_alive():
            log.warning(
                "[RECORDING] Audio worker thread did not exit within %.1fs "
                "(it will exit as a daemon on next iteration)",
                timeout,
            )
        else:
            log.debug("[RECORDING] Audio worker thread exited cleanly")
        # THREAD-REGISTRY: remove the entry so a subsequent start()
        if recorder._thread_registry is not None:
            recorder._thread_registry.unregister(_AUDIO_WORKER_THREAD_NAME)
        # Only clear the stop/wake events and null the thread reference if
        if not recorder._worker_thread.is_alive():
            recorder._worker_stop_event.clear()
            recorder._worker_wake_event.clear()
            recorder._worker_thread = None

