"""Download queue control: enqueue, positions, pause/resume, cancel."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from voice_typer.server.service._download_helpers import DownloadOutcome

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class DownloadQueueMixin:

    """Download queue control: enqueue, positions, pause/resume, cancel.

    Host-state contract: the declarations below are attributes the
    composed ``ModelMixin`` (or a sibling mixin) owns.

    The TYPE_CHECKING stubs name methods the composite provides.
    """

    _active_download_id: Any
    _download_cancel_events: Any
    _download_cancel_lock: Any
    _download_queue: list[str]

    if TYPE_CHECKING:
        def download_model(self, model_name: str) -> dict[str, object]: ...


    def cancel_model_download(self, model_name: str | None = None) -> dict:
        """Cancel a model download, the active transfer and/or a queued
        request.

        With ``model_name`` (cancel-anywhere): if that model is waiting
        in the pending download queue, it is REMOVED from the queue
        without touching the active transfer (the queue advances and
        remaining positions are re-pushed as ``download_progress``
        events). If the named model is the ACTIVE download, the active
        cancel path below runs. A name that is neither queued nor
        active is a no-op.

        Without ``model_name`` (the legacy IPC shape): cancels the
         ACTIVE transfer only, queued items stay queued and drain when
        the active transfer exits (the queue's whole point is that the
        next request auto-starts).

        sets the cancellation event so the download_model
        polling loop stops waiting and returns a "cancelled" result.

         signals the active download's per-download
        Event (looked up in ``self._download_cancel_events`` under the
        lock). Without the per-download lookup, two concurrent
        ``download_model`` calls would each overwrite a shared attribute
        and only one would actually get cancelled.

         the legacy single-instance
        ``self._download_cancel_event`` fallback branch has been REMOVED.
        All cancel signals now flow through the per-download dict.

        ALSO signals the transfer gate (:func:`asr_setup.request_download_abort`)
        so the HuggingFace transfer threads unwind at the next chunk
        boundary, pre-fix, cancel only stopped the progress REPORTER
        and the daemon transfer thread kept downloading in the
        background.
        """
        if model_name is not None:
            removed_position = self._remove_queued_download(model_name)
            if removed_position is not None:
                log.info(
                    "[SERVICE] Queued download of '%s' (position %d) removed by user",
                    model_name,
                    removed_position,
                )
                return {"cancelled": True, "model": model_name, "removed_from_queue": True}
            if not self._is_active_download_model(model_name):
                log.debug(
                    "[SERVICE] cancel_model_download(%r): model is neither queued nor active",
                    model_name,
                )
                return {"cancelled": False}
            # Named the ACTIVE model, fall through to the active-cancel
        cancelled_any = False
        # Per-download dict path, signal the
        with self._download_cancel_lock:
            active_id = self._active_download_id
            active_event = self._download_cancel_events.get(active_id) if active_id is not None else None
        if active_event is not None:
            active_event.set()
            cancelled_any = True
        # ALSO signal the transfer gate whenever a gateable download is
        try:
            from voice_typer.server.asr_setup import (
                is_download_active,
                request_download_abort,
            )

            if is_download_active() and request_download_abort():
                cancelled_any = True
        except Exception:
            log.debug(
                "[SERVICE] transfer-gate abort signal failed",
                exc_info=True,
            )
        if cancelled_any:
            log.info("[SERVICE] Model download cancellation requested")
            return {"cancelled": True}
        return {"cancelled": False}

    def get_download_queue(self) -> dict[str, object]:
        """Snapshot of the pending download FIFO queue (front first).

        Read-only: returns the queued model NAMES in drain order under
        the cancel lock. The renderer calls this once on mount to
        hydrate its queue chips (``useModelDownloadQueue``); live
        updates keep flowing through ``download_progress`` events with
        ``queue_position``. An empty list is the normal idle state.
        """
        with self._download_cancel_lock:
            return {"queue": list(self._download_queue)}

    def _enqueue_download(self, model_name: str) -> DownloadOutcome:
        """Queue a download request behind the active gateable transfer.

        Called by the single-flight guards in
        ``_download_whisper_family`` / ``_download_parakeet`` when a
        second download request arrives while a gateable transfer is in
        flight (possibly paused). The queue is the missing UX layer on
        top of the single-flight gate: transfers stay serialized (the
        shared pause/abort events are module-level and MUST NOT be
        recycled under a live transfer), but the request is no longer
        refused with an error, it waits its turn and auto-starts when
        the active transfer exits.

        Holds model NAMES only (unbounded by design, short strings;
        the UI caps display, not storage). Duplicate enqueues are
        idempotent: the model keeps its existing position and the
        queued event is re-pushed so the renderer state refreshes.

        Re-click of the CURRENTLY-DOWNLOADING model does NOT queue: the
        transfer is already in flight, so the already-active outcome is
        returned instead (queueing the model behind itself would drain
        later as a cache-hit no-op transfer once the live one exits).

        Returns the queued outcome (success, the request was accepted)
        and pushes a ``download_progress`` event carrying the new
        ``queue_position`` field so the renderer can render the queued
        state from the existing event stream.
        """
        from voice_typer.server import event_bus
        from voice_typer.server.service._download_helpers import push_progress

        if self._is_active_download_model(model_name):
            # The requested model IS the active download, answer with
            log.info(
                "[SERVICE] Download of '%s' requested while the same model is already downloading",
                model_name,
            )
            return {
                "success": True,
                "model": model_name,
                "download_already_active": True,
                "message": f"Download of {model_name} is already in progress.",
            }
        with self._download_cancel_lock:
            if model_name in self._download_queue:
                position = self._download_queue.index(model_name) + 1
                already_queued = True
            else:
                self._download_queue.append(model_name)
                position = len(self._download_queue)
                already_queued = False
        log.info(
            "[SERVICE] Download of '%s' %s (position %d), another gateable download is active",
            model_name,
            "already queued" if already_queued else "queued",
            position,
        )
        push_progress(
            event_bus,
            model_name,
            0,
            f"Download of {model_name} already queued" if already_queued else f"Download of {model_name} queued",
            queue_position=position,
        )
        return {
            "success": True,
            "queued": True,
            "model": model_name,
            "queue_position": position,
            "message": "Queued, it starts automatically when the current download finishes.",
        }

    def _remove_queued_download(self, model_name: str) -> int | None:
        """Remove ``model_name`` from the pending queue; return the
        1-based position it held (``None`` when it was not queued).

        After a removal the remaining items advance, their refreshed
        positions are re-pushed as ``download_progress`` events so the
        renderer's queue state stays accurate.
        """
        with self._download_cancel_lock:
            if model_name not in self._download_queue:
                return None
            position = self._download_queue.index(model_name) + 1
            self._download_queue.remove(model_name)
            remaining = list(self._download_queue)
        self._push_queue_positions(remaining)
        return position

    def _push_queue_positions(self, names: list[str] | None = None) -> None:
        """Re-push the current ``queue_position`` for the given (or all)
        queued models.

        Only models still present in the queue get an event (the caller
        may pass a pre-removal snapshot; entries already re-queued or
        removed are skipped).
        """
        from voice_typer.server import event_bus
        from voice_typer.server.service._download_helpers import push_progress

        with self._download_cancel_lock:
            snapshot = list(self._download_queue) if names is None else [n for n in names if n in self._download_queue]
        for index, name in enumerate(snapshot, start=1):
            push_progress(
                event_bus,
                name,
                0,
                f"Download of {name} queued",
                queue_position=index,
            )

    def _is_active_download_model(self, model_name: str) -> bool:
        """True when ``model_name`` is the model of the ACTIVE download.

        ``_active_download_id`` is ``f"{model_name}:{hex}"``, the
        registered id is prefixed with the model name, so a prefix
        match on the ``:`` boundary identifies the active model.
        """
        with self._download_cancel_lock:
            active_id: str | None = self._active_download_id
        if active_id is None:
            return False
        return active_id.split(":", 1)[0] == model_name

    def _start_next_queued_download(self) -> None:
        """Auto-start the next queued download once the gate is free.

        Called from the ``download_model`` dispatcher's ``finally`` (so
        every exit, success, failure, cancel, advances the queue) and
        safe to call at any time: while a gateable transfer is still
        active it does nothing (the live download's own exit path will
        drain later). The next download runs on its OWN daemon thread
        because no IPC executor is waiting on queued requests (the
        caller's promise already resolved with the queued outcome).

        Self-healing by construction: if a concurrent download arms the
        gate between the check and the pop, the spawned thread's
        ``download_model`` hits the single-flight guard and re-queues
        the model, the next drain cycle picks it up again.
        """
        from voice_typer.server.asr_setup import is_download_active

        if is_download_active():
            return
        with self._download_cancel_lock:
            if not self._download_queue:
                return
            model_name = self._download_queue.pop(0)
            remaining = list(self._download_queue)
        # Refresh the remaining positions (outside the lock, it pushes
        self._push_queue_positions(remaining)
        import threading

        t = threading.Thread(
            target=self._queued_download_runner,
            args=(model_name,),
            name=f"model-download-queue-{model_name}",
            daemon=True,
        )
        t.start()

    def _queued_download_runner(self, model_name: str) -> None:
        """Thread body for a drained queued download (never raises, an
        exception in a daemon thread would silently drop the request)."""
        try:
            self.download_model(model_name)
        except Exception:
            log.exception("[SERVICE] Queued download of '%s' failed", model_name)

    def pause_model_download(self) -> dict:
        """Pause an in-progress model download.

        delegates to :func:`asr_setup.set_download_paused`.
        The transfer gate (:func:`asr_setup.get_download_tqdm_class`) parks
        the HuggingFace transfer thread at the next chunk boundary, so
        bytes genuinely stop flowing (pre-fix the pause only froze the
        progress REPORTER while the transfer ran to completion in the
        background). The polling loop pushes the ``paused: True``
        transition event, which the renderer renders as its amber
        "paused" state.
        """
        from voice_typer.server.asr_setup import set_download_paused

        paused = set_download_paused(True)
        if paused:
            log.info("[SERVICE] Model download pause requested")
        return {"paused": paused}

    def resume_model_download(self) -> dict:
        """Resume a paused model download.

        clears the module-level pause flag set by
        :meth:`pause_model_download`. The transfer gate unblocks the
        parked transfer thread at its next chunk boundary and the
        download continues (huggingface_hub re-requests with a Range
        header if the idle HTTP connection died during the pause).

        Mirrors the pause path: the boolean from
        :func:`asr_setup.set_download_paused` is forwarded so a no-op
        resume (no live download) returns ``{"resumed": False}`` and
        the renderer can revert its optimistic flip.
        """
        from voice_typer.server.asr_setup import set_download_paused

        resumed = set_download_paused(False)
        if resumed:
            log.info("[SERVICE] Model download resume requested")
        return {"resumed": resumed}
