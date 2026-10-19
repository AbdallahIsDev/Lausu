"""Toggle/start flow for recording: decision, recorder wiring, start worker.

Split out of ``voice_typer.server.recording_lifecycle`` (one concern per
file). The facade keeps the composed class, the pinned pipeline bodies
and every monkeypatch seam; this module owns the moved bodies. The
facade-owned join-timeout constant is read through the lazy ``_facade()``
proxy at call time.
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


class RecordingLifecycleStartMixin:
    """Toggle decision and start-side flow (wiring, ownership, start worker)."""

    if TYPE_CHECKING:
        def _publish_permission_denied_refusal(self, app, state: str = "denied") -> None: ...

    def _toggle_impl(self, controller) -> None:
        """Inner toggle implementation, called under _toggle_lock."""
        app = controller._app
        # The cycle counter is NOT incremented here. Pre-fix, every

        active = app.models.active_transcriber()
        model_loaded = active is not None and active.is_loaded
        # ``_busy_event`` is inverted (SET == idle); log the natural
        busy = not app._busy_event.is_set()
        log.info(
            "[HOTKEY FIRED] toggle_dictation called (recording=%s, busy=%s, model_loaded=%s | thread=%s | cycle=%s)",
            app.recorder.recording,
            busy,
            model_loaded,
            threading.current_thread().name,
            app._cycle_id,
        )
        if not app._busy_event.is_set():  # busy
            log.warning("[HOTKEY BLOCKED] Busy transcribing, ignoring toggle (cycle=%s)", app._cycle_id)
            self._surface_busy_refusal(app)
            return

        # Record-while-loading: an in-flight loader is no reason to
        # refuse the hotkey. Recording starts immediately; the
        # DictationStart worker joins the load via
        # ensure_active_engine_loaded(), and the stop-side transcribe
        # path holds the audio until the model is ready.
        loader = app.models._model_load_thread
        loader_alive = loader is not None and loader.is_alive()
        if loader_alive:
            log.info(
                "[HOTKEY FIRED] Model still loading -- recording now, load continues in background (cycle=%s)",
                app._cycle_id,
            )

        if active is None and not loader_alive:
            # Permission pre-check doubles as the model-load gate: a
            # denied hotkey press refuses here, before the load below
            # and before the _start_impl gate. Granted/unknown probes
            # cost one InputStream open here plus one in _start_impl's
            # recorder.start(); acceptable for a hotkey press.
            try:
                from voice_typer.server import permissions as _perm_pre

                _perm_pre.verify_microphone_accessible()
            except Exception as pre_exc:
                from voice_typer.server.asr_errors import MicrophonePermissionDeniedError

                if isinstance(pre_exc, MicrophonePermissionDeniedError):
                    _deny_state = getattr(pre_exc, "state", "denied")
                    log.warning(
                        "[HOTKEY FIRED] Refusing hotkey press: mic permission "
                        "%s (no model load kicked, cycle=%s)",
                        _deny_state,
                        app._cycle_id,
                    )
                    self._publish_permission_denied_refusal(
                        controller._app, getattr(pre_exc, "state", None) or "denied"
                    )
                    return
                raise
            # No engine and no live loader: kick a background load, then
            # record anyway instead of queueing a pending dictation.
            log.info(
                "[HOTKEY FIRED] No active transcriber -- kicking background load + recording now (cycle=%s)",
                app._cycle_id,
            )
            try:
                app.models.start_background_load()
            except Exception:
                log.debug(
                    "[HOTKEY FIRED] load kick failed, DictationStart worker retries (cycle=%s)",
                    app._cycle_id,
                    exc_info=True,
                )

        # Commit to a real start/stop. NOW increment the cycle counter
        app._cycle_counter += 1
        app._cycle_id = f"#{app._cycle_counter}"

        if app.recorder.recording:
            # Call ``app._stop_dictation`` (which delegates to
            app._stop_dictation()
        else:
            app._start_dictation()

    def _surface_busy_refusal(self, app) -> None:
        """Visible feedback for a hotkey press during transcription.

        The toggle is refused by design (single-flight, C-CONC-1) but
        the refusal must not be silent: the bubble label flips to
        "Still transcribing..." and the tray status line matches.
        Exception-shielded: feedback must never break the toggle path.
        """
        try:
            app.tray.set_state(
                AppState.TRANSCRIBING,
                _facade().i18n.t("state.recording_controller.still_transcribing"),
            )
        except Exception:
            log.debug("[HOTKEY BLOCKED] tray still-transcribing feedback failed", exc_info=True)
        try:
            app._waveform_bubble.set_state("still_transcribing")
        except Exception:
            log.debug("[HOTKEY BLOCKED] bubble still-transcribing feedback failed", exc_info=True)

    def _wire_recorder_start_callbacks(self, controller, app) -> None:
        """Wire recorder callbacks + pre-start cleanup before open."""
        app.recorder.on_silence_warning = controller.on_silence_warning
        app.recorder.on_silence_auto_stop = controller.on_silence_auto_stop
        app.recorder.on_max_duration_auto_stop = controller.on_max_duration_auto_stop
        # Wire the microphone-permission-revoked callback so the
        with contextlib.suppress(Exception):
            app.recorder.on_microphone_permission_revoked = controller.on_microphone_permission_revoked

        # Waveform bubble: feed RMS levels from the audio callback
        app.recorder.on_rms_level = controller.on_recorder_rms

        # Reset audio-quality analyzer accumulators so per-chunk
        try:
            app._audio_quality.reset()
        except Exception:
            log.debug("[AUDIO_QUALITY] reset on start failed", exc_info=True)

        controller._stop_level_monitor_for_recorder_start()

    def _notify_mic_watcher_of_active_device(self, app) -> None:
        """Tell the mic watcher which mic_id we're recording from."""
        with contextlib.suppress(Exception):
            mic_watcher = getattr(getattr(app.recorder, "_devices", None), "_mic_watcher", None)
            if mic_watcher is not None:
                # The resolved device index (or None for default) is
                resolved = getattr(app.recorder, "_effective_device", None)
                if resolved is None:
                    resolved = app.recorder._devices._resolve_device()
                mic_watcher.set_active_mic_id(resolved)

    def _claim_keyboard_ownership_for_recording(self, app) -> None:
        """Mark the recording subsystem as the keyboard owner."""
        try:
            keyboard_ownership().set_owner("recording", reason=f"recording started (cycle={app._cycle_id})")
        except Exception:
            log.debug(
                "[DICTATION] failed to set keyboard ownership on start",
                exc_info=True,
            )

    def _rearm_esc_cancel_if_enabled(self, app) -> None:
        """ESC-CANCEL-WATCHDOG: re-arm a dead/stale ESC backend on start."""
        try:
            if getattr(app.config, "esc_cancel_enabled", False):
                esc_backend = getattr(app.hotkeys, "_esc_backend", None)
                if esc_backend is None or not esc_backend.is_alive():
                    log.warning(
                        "[DICTATION] ESC cancel backend missing/dead at recording start (backend=%r), re-registering",
                        type(esc_backend).__name__ if esc_backend else "None",
                    )
                    app.hotkeys.register_esc()
        except Exception:
            log.warning(
                "[DICTATION] failed to re-arm ESC cancel hotkey on start",
                exc_info=True,
            )

    def _publish_recording_started_event(self) -> None:
        """Emit ``recording_started`` push so the renderer can refresh UI."""
        try:
            event_bus.publish({"type": "recording_started"})
        except Exception:
            log.warning(
                "[SOUND] failed to push recording_started event",
                exc_info=True,
            )

    def _spawn_dictation_start_worker(self, controller, app) -> None:
        """Spawn the DictationStart daemon worker + publish adaptive join timeout.

        Load / reload the active engine AFTER ``recorder.start()`` so
        the recorder buffers audio while the model reloads (5-30s
        on idle-unload). Pre-fix this ran before ``recorder.start()``
        and the first 5-30s of speech was lost. The transcription
        thread (started in ``_stop_impl``) transcribes the buffered
        audio once the model is ready. If the model fails to load,
        the worker discards the recorder and surfaces an error.

        The model load + post-load steps (active_transcriber check,
        fallback_to_whisper, _start_streaming_session_if_enabled)
        run on a DAEMON WORKER THREAD so the F2 hotkey backend's
        single dispatch thread is NOT blocked for 5-30s on the
        idle-unload reload path. Pre-fix, the lock was released
        for the duration of ``ensure_active_engine_loaded()`` so
        concurrent stop/cancel could proceed, but the F2 thread
        itself still blocked for 5-30s: meaning:
          - The F2 hotkey backend's dispatch thread was occupied
            and could not process a second F2 press (e.g. to stop
            the recording the user just started).
          - On hotkey backends with a single dispatch thread
            (pynput), ALL hotkeys were blocked for 5-30s —
            including ESC cancel.
        The F2 thread now spawns the worker and returns after a
        bounded ``join(timeout=0.1)``: fast enough for tests
        with mocked models (the worker completes in <1ms), slow
        enough to not block the dispatch thread in production
        (5-30s idle-unload reload). The worker is a daemon so it
        doesn't block process exit.

        The worker runs WITHOUT ``_toggle_lock``: the public entry
        (``toggle`` / ``start`` via ``_run_public_entry``) releases
        the lock BEFORE the bounded join, so neither the worker NOR
        the join holds it. The worker doesn't need the lock
        because:
        1. ``ensure_active_engine_loaded()`` has its own internal
           lock (``_lazy_init_lock`` in ``ModelManager``).
        2. The post-load re-check reads atomic state
           (``recorder.recording``, ``_busy_event.is_set()``).
        3. ``_start_streaming_session_if_enabled()`` uses
           ``_streaming_session_lock`` for its own serialization.
        The ``_busy_event`` is NOT cleared by ``_start_impl``
        (``_stop_impl`` clears it), so a concurrent ``stop()``
        that acquires the lock after the public entry releases it
        would see ``busy_event.is_set() == True`` (not busy) and
        proceed, the desired behavior (the user explicitly
        stopped, so the buffered audio should be transcribed as
        soon as the model finishes loading).

        The worker signals ``_start_complete_event`` in its
        finally block so tests that need to assert model-loaded
        state can wait on the event.
        """
        start_complete_event = threading.Event()
        # Publish on the controller so tests can wait on it
        controller._start_complete_event = start_complete_event
        worker = threading.Thread(
            target=controller._lifecycle._start_dictation_worker_entry,
            args=(controller, app._cycle_id, start_complete_event),
            name="DictationStart",
            daemon=True,
        )
        # Store on controller so tests / watchdog can inspect / join.
        controller._start_worker_thread = worker
        worker.start()
        # Bounded wait for the worker to make progress. The timeout
        _pre_load_active = app.models.active_transcriber()
        _pre_load_model_loaded = _pre_load_active is not None and getattr(_pre_load_active, "is_loaded", False)
        _join_timeout = _facade()._DEFAULT_START_JOIN_TIMEOUT_S if _pre_load_model_loaded else 2.0
        # Publish the join timeout next to the worker thread so the
        controller._start_worker_join_timeout = _join_timeout

    def _teardown_failed_recorder_start(
        self,
        controller,
        app,
        *,
        restart_level_monitor: bool,
        discard_log_label: str,
    ) -> None:
        """Release the recorder/streaming state after a failed start."""
        controller._cancel_streaming_session()
        # If ``recorder.start()`` succeeded but a later step raised, the
        try:
            app.recorder.discard()
        except Exception:
            log.debug(
                "[DICTATION] recorder.discard() during %s raised (best-effort cleanup)",
                discard_log_label,
                exc_info=True,
            )
        # Force-reset the recording flag so the next ``start()`` call
        app.recorder.recording = False
        if restart_level_monitor:
            # Best-effort, mirroring the stop paths.
            controller._maybe_restart_level_monitor_for_always_visible_bubble(app)
