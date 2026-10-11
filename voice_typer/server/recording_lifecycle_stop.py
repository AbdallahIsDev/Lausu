"""Stop/cancel flow for recording: worker spawn and discard teardown.

Split out of ``voice_typer.server.recording_lifecycle`` (one concern per
file). The facade keeps the composed class, the pinned pipeline bodies
and every monkeypatch seam; this module owns the moved bodies. Facade
``i18n`` reads go through the lazy ``_facade()`` proxy at call time so
facade-level patches are honored.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import TYPE_CHECKING

from voice_typer.server import event_bus
from voice_typer.server.keyboard_ownership import keyboard_ownership
from voice_typer.server.tray_types import AppState

log = logging.getLogger("voice_typer.server.recording_lifecycle")


def _facade():
    """The facade module, read at call time so patches on it are honored."""
    from voice_typer.server import recording_lifecycle as module

    return module


class RecordingLifecycleStopMixin:
    """Stop-side pre-stop work and cancel/discard teardown."""

    if TYPE_CHECKING:
        def _stop_and_transcribe_worker_entry(self, controller, cycle_id: str) -> None: ...

    def _stop_impl(self, controller) -> None:
        """Inner stop implementation, called under _toggle_lock.

        The blocking ``recorder.stop()`` call (~2.4s worst case: 300ms
        stream-teardown poll + 2.0s audio-worker drain + 2.0s event-worker
        drain + np.concatenate + resample) is moved off the hotkey thread
        into a daemon worker. The hotkey thread does the synchronous
        pre-stop work (publish event, keyboard ownership, busy flag, tray,
        bubble), then spawns the worker as ``controller._transcription_thread``
        and returns after a bounded ``join(timeout=0.1)``. The
        ``_toggle_lock`` is held only for the synchronous pre-stop work +
        thread spawn (microseconds), not the 2.4s teardown. The
        ``_busy_event`` (cleared synchronously below) prevents concurrent
        ``stop()`` / ``toggle()`` calls from proceeding while the
        stop+transcribe worker is running.
        """
        app = controller._app
        if not app.recorder.recording:
            log.info("[DICTATION] _stop_dictation: not recording, no-op")
            return
        # (``_busy_event`` cleared = busy=True), this is a duplicate
        if not app._busy_event.is_set():  # busy = True
            log.debug(
                "[DICTATION] _stop_dictation: stop already in progress (busy=True) | no-op (cycle=%s)",
                app._cycle_id,
            )
            return
        # Emit ``recording_stopped`` push event. Log push failures (see
        try:
            event_bus.publish({"type": "recording_stopped"})
        except Exception:
            log.warning(
                "[SOUND] failed to push recording_stopped event",
                exc_info=True,
            )

        # Recording is stopping, release keyboard ownership back to
        try:
            keyboard_ownership().set_owner("normal", reason=f"recording stopped (cycle={app._cycle_id})")
        except Exception:
            log.debug(
                "[DICTATION] failed to reset keyboard ownership on stop",
                exc_info=True,
            )

        # Cancel any stale pending timers
        app._cancel_pending_timers()

        log.info("[DICTATION] Stopping recording... (cycle=%s)", app._cycle_id)

        # legacy ``_busy_event.clear()``: the inverted primitive stays
        app._busyness.set_busy()

        # Detach the RMS callback so the audio path cannot keep pushing
        app.recorder.on_rms_level = None
        # Push a final zero-level event so the renderer resets its
        app._waveform_bubble.reset_level()
        # NEW-BUBBLE-TRANSCRIBING: Instead of hiding the bubble
        # Engine cold at stop → "loading" pill (the transcribe hold
        # flips it to transcribing on ready); the probe must never
        # break stop, defaulting to today's "transcribing".
        try:
            _models = getattr(app, "models", None)
            _active = _models.active_transcriber() if _models is not None else None
            _engine_ready = bool(getattr(_active, "is_loaded", False))
        except Exception:
            log.debug("[DICTATION] engine-readiness probe failed, assuming transcribing", exc_info=True)
            _engine_ready = True
        app._waveform_bubble.set_state("transcribing" if _engine_ready else "loading")

        _captured_cycle_id = app._cycle_id

        # Spawn a daemon worker thread that performs ``recorder.stop()``

        # Write ``controller._transcription_thread`` under
        with controller._watchdog_lock:
            controller._transcription_thread = threading.Thread(
                target=self._stop_and_transcribe_worker_entry,
                args=(controller, _captured_cycle_id),
                name="Transcription",
                daemon=True,
            )
            controller._transcription_thread.start()

        # Bounded wait for the worker to make progress. In tests where
        with contextlib.suppress(Exception):
            controller._transcription_thread.join(timeout=0.1)

    def _cancel_impl(self, controller) -> None:
        """Inner cancel implementation, called under _toggle_lock."""
        app = controller._app

        # ESC: If no recording is active, the ESC cancel is a no-op. The
        try:
            if keyboard_ownership().is_hotkey_capture_active():
                log.debug(
                    "[CANCEL] ESC ignored, frontend hotkey capture active (cycle=%s)",
                    app._cycle_id,
                )
                return
        except Exception:
            log.debug("[CANCEL] keyboard ownership check failed", exc_info=True)

        if not app.recorder.recording:
            # ``_busy_event.is_set() == False``), we immediately mark
            with controller._watchdog_lock:
                t_thread = controller._transcription_thread
            if (
                t_thread is not None and t_thread.is_alive() and not app._busy_event.is_set()  # busy = True
            ):
                log.info(
                    "[CANCEL] ESC during transcription phase (cycle=%s), marking cancelled + force-recovering",
                    app._cycle_id,
                )
                cycle_id = getattr(app, "_cycle_id", None)
                if cycle_id is not None:
                    # Use the bounded-registry helper so the set cannot
                    controller._mark_cycle_cancelled(cycle_id)
                    log.info(
                        "[CANCEL] cycle %s marked cancelled, late transcription will not be pasted",
                        cycle_id,
                    )
                # ``_force_recover_from_stuck_transcription`` now also
                try:
                    controller._force_recover_from_stuck_transcription(force=True)
                except Exception:
                    log.exception(
                        "[CANCEL] _force_recover_from_stuck_transcription raised during cancel (cycle=%s)",
                        app._cycle_id,
                    )
                return
            log.debug("[CANCEL] Cancel pressed but no recording active (cycle=%s), no-op", app._cycle_id)
            return

        log.info("[CANCEL] Cancelling current dictation (cycle=%s)", app._cycle_id)

        # Release keyboard ownership back to "normal" so subsequent
        try:
            keyboard_ownership().set_owner("normal", reason=f"recording cancelled (cycle={app._cycle_id})")
        except Exception:
            log.debug(
                "[CANCEL] failed to reset keyboard ownership on cancel",
                exc_info=True,
            )
        # Show CANCELLING state immediately.
        try:
            app.tray.set_state(AppState.CANCELLING, _facade().i18n.t("state.recording_controller.cancelling"))
        except Exception:
            log.debug("[CANCEL] could not set CANCELLING state", exc_info=True)
        try:
            app._waveform_bubble.set_state("cancelling")
        except Exception:
            log.debug("[CANCEL] could not set bubble cancelling state", exc_info=True)
        app._cancel_pending_timers()

        if app.recorder.recording:
            try:
                # Detach RMS callback and stop background audio first
                app.recorder.on_rms_level = None
                # Push a final zero-level event to reset the bubble visualizer
                app._waveform_bubble.reset_level()
                app.recorder.discard()
                log.info("[CANCEL] Recording discarded (cycle=%s)", app._cycle_id)
                # Clear the active-mic-id on the watcher so it stops
                with contextlib.suppress(Exception):
                    mic_watcher = getattr(getattr(app.recorder, "_devices", None), "_mic_watcher", None)
                    if mic_watcher is not None:
                        mic_watcher.set_active_mic_id(None)
                # Immediately secure-clear the audio buffers from memory
                app.recorder._secure_clear_session_caches()
            except Exception as e:
                # Don't abort the cancel path, fall through to ensure
                log.exception(
                    "[CANCEL] Failed to discard recording (cycle=%s): %s",
                    app._cycle_id,
                    e,
                )

        # Always run these, even if discard failed.
        try:
            controller._cancel_streaming_session()
        except Exception:
            log.exception("[CANCEL] Failed to cancel streaming session")

        # Restore system volume on cancel
        try:
            app._restore_volume()
        except Exception:
            log.exception("[CANCEL] Failed to restore volume")

        # Hide bubble unless always_visible mode (in which case set to
        try:
            if app.config.bubble_behavior != "always_visible":
                app._waveform_bubble.hide()
            else:
                app._waveform_bubble.set_state("idle")
        except Exception:
            log.exception("[CANCEL] Failed to hide/set idle bubble")

        # Tray state + busy flag MUST be cleared so the user can press
        app.tray.set_state(AppState.IDLE, _facade().i18n.t("state.recording_controller.cancelled"))
        app._busyness.set_idle()  # coordinator-routed
