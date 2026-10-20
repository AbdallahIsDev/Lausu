"""Recording lifecycle, extracted from ``RecordingController``.

Owns the toggle / start / stop / cancel state machine and the
stop+transcribe worker entry point. The actual recording flag, busy
event, transcription thread handle, and toggle lock all live on
``RecordingController`` (shared state): this helper operates on them
through a back-reference.

Collaborator pattern
--------------------
:class:`RecordingLifecycle` is constructed by
``RecordingController.__init__`` with NO arguments (stateless). Each
method takes a back-reference to the owning ``RecordingController``
(``controller``) and reads/writes ``controller._app``,
``controller._toggle_lock``, ``controller._transcription_thread``,
``controller._busy_event``, etc.

The public lifecycle methods (``toggle`` / ``start`` / ``stop`` /
``cancel``) acquire ``controller._toggle_lock`` (an RLock) and then
call their own ``_toggle_impl`` / ``_start_impl`` / ``_stop_impl`` /
``_cancel_impl`` directly. There is no hop back through the
controller: production flow is
``lifecycle.toggle → lifecycle._toggle_impl``.

The moved bodies live in the split mixins composed below (start flow /
stop-cancel / permissions); this module keeps the class, the constants,
the pipeline bodies pinned by source-text tests, and every monkeypatch
seam (``i18n``).

Originally lines 469–1500 of ``recording_controller.py``.
"""

from __future__ import annotations

import contextlib
import logging
import math
import numbers
import threading

from voice_typer.server import i18n
from voice_typer.server.branding import APP_NAME
from voice_typer.server.duration import format_duration
from voice_typer.server.recording_lifecycle_permissions import (  # noqa: F401  # facade attrs: tests import the moved helpers from here
    RecordingLifecyclePermissionsMixin,
    _notify_consent_gate,
    _notify_permission_denied_with_settings,
    _open_os_microphone_settings,
    _publish_consent_required_event,
    _recording_start_failure_message,
)
from voice_typer.server.recording_lifecycle_start import RecordingLifecycleStartMixin
from voice_typer.server.recording_lifecycle_stop import RecordingLifecycleStopMixin
from voice_typer.server.tray_types import AppState

log = logging.getLogger(__name__)


#: Stable ``consent_field`` id the backend publishes for the voice-
VOICE_BIOMETRIC_CONSENT_FIELD = "voice_biometric_consent"


#: Default bounded-join timeout for the DictationStart worker when the
_DEFAULT_START_JOIN_TIMEOUT_S = 0.1


#: The exact RuntimeError message raised by the recording pipeline when
_NO_INPUT_DEVICE_MARKER = "No input device could be opened"


#: How long the bubble stays on the permission_revoked variant before
#: auto-reverting (idle in always_visible, hide in show_on_record) -
#: matches the tray's ERROR beat so the surfaces settle together.
_PERMISSION_REVOKED_BUBBLE_SECONDS = 5.0


#: Too-short boundary: sub-threshold clips pass the short-audio gate only
#: with speech-like energy; >= this duration is unchanged historical behavior.
MIN_DURATION_S = 0.5

#: Speech-energy floor for sub-``MIN_DURATION_S`` clips. Matches the
#: VAD-unavailable fallback (vad.py: ``rms > 0.01``) and the hallucination
#: Tier-1 near-silence boundary (``rms < 0.01`` reads as no speech).
MIN_SHORT_RMS = 0.01

#: Silence ceiling for sub-``MIN_DURATION_S`` clips: at/above this the clip is
#: a tap or near-silence, not a word. Same 95.0 tier as the hallucination
#: near-silence check (``silence_pct >= 95.0``).
MAX_SHORT_SILENCE_PCT = 95.0


def _short_clip_silence_pct(recorder) -> float | None:
    """Silence percentage from the recorder's stop-time stats, or None when
    the stats are unavailable (mock recorders / non-tuple shapes)."""
    stats = getattr(recorder, "_last_audio_stats", None)
    if isinstance(stats, tuple) and len(stats) == 3:
        try:
            return float(stats[2])
        except (TypeError, ValueError):
            return None
    return None


def _short_clip_rms(recorder) -> float | None:
    """Stop-time RMS as a usable float, or None when missing/unusable.

    Mock-like values are rejected deliberately: ``float(MagicMock())`` is
    1.0 and would silently pass the energy floor; NaN would fail open
    (``nan < MIN_SHORT_RMS`` is False)."""
    value = getattr(recorder, "last_rms", None)
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _short_clip_has_speech_energy(recorded_rms: float, silence_pct: float | None) -> bool:
    """Short-audio gate rule: proceed only with speech-like energy.

    Deliberate inclusivity: RMS at exactly ``MIN_SHORT_RMS`` passes (the
    hallucination tier treats ``rms < 0.01`` as near-silence, so its
    complement starts at 0.01); silence at exactly ``MAX_SHORT_SILENCE_PCT``
    fails (same ``>= 95.0`` near-silence comparison). Missing silence stats
    (None) fall back to the energy test alone.
    """
    if recorded_rms < MIN_SHORT_RMS:
        return False
    return silence_pct is None or silence_pct < MAX_SHORT_SILENCE_PCT


class RecordingLifecycle(
    RecordingLifecycleStartMixin, RecordingLifecycleStopMixin, RecordingLifecyclePermissionsMixin
):
    """Toggle / start / stop / cancel state machine for recording."""

    def __init__(self) -> None:
        # Stateless helper, all recording state lives on the controller.
        self._public_entry_depth = threading.local()

    def _run_public_entry(self, controller, impl_method) -> None:
        """Run a public lifecycle entry (``toggle`` / ``start``)."""
        app = controller._app
        # Shutdown gate: a press arriving after ``_shutting_down_event`` is
        # set must not start a new cycle while teardown is still running
        # (hotkey backends stop only in the parallel phase). Strict ``is
        # True`` keeps unit stubs (MagicMock ``is_set()``) off the gate.
        shutting_down = getattr(app, "_shutting_down_event", None)
        if shutting_down is not None and shutting_down.is_set() is True:
            log.warning(
                "[HOTKEY BLOCKED] shutdown in progress, refusing dictation entry (cycle=%s)",
                getattr(app, "_cycle_id", None),
            )
            return
        outermost = not getattr(self._public_entry_depth, "active", False)
        if outermost:
            self._public_entry_depth.active = True
        prior_start_worker = getattr(controller, "_start_worker_thread", None)
        try:
            with controller._toggle_lock:
                impl_method()
        finally:
            if outermost:
                self._public_entry_depth.active = False
        if not outermost:
            return
        worker = getattr(controller, "_start_worker_thread", None)
        if worker is None or worker is prior_start_worker:
            return
        join_timeout = getattr(controller, "_start_worker_join_timeout", _DEFAULT_START_JOIN_TIMEOUT_S)
        with contextlib.suppress(Exception):
            worker.join(timeout=join_timeout)

    def toggle(self, controller) -> None:
        """Toggle recording on/off.

        RACE-025: Serializes concurrent toggle calls from different threads
        (hotkey thread + tray thread) to prevent TOCTOU where two near-
        simultaneous F2 presses both pass the _busy_event check.

        The lock is acquired exactly once (via ``_run_public_entry``)
        around the toggle decision. When the decision starts a dictation,
        the bounded join of the DictationStart worker happens AFTER the
        lock is released so a concurrent ``stop()`` / ``cancel()"
        (auto-stop timer, ESC hotkey) never waits behind the join.
        """
        self._run_public_entry(controller, lambda: self._toggle_impl(controller))

    def start(self, controller) -> None:
        """Start a recording session."""
        self._run_public_entry(controller, lambda: self._start_impl(controller))

    def _start_impl(self, controller) -> None:
        """Inner start implementation, called under _toggle_lock."""
        app = controller._app
        # Reset the published join timeout to the default BEFORE any of
        controller._start_worker_join_timeout = _DEFAULT_START_JOIN_TIMEOUT_S
        if app.recorder.recording:
            log.info("[DICTATION] _start_dictation: already recording, no-op")
            return

        if not self._gate_voice_biometric_consent(app):
            return

        try:
            from voice_typer.server import permissions as _perm_gate

            _perm_gate.verify_microphone_accessible()
        except Exception as gate_exc:
            from voice_typer.server.asr_errors import MicrophonePermissionDeniedError

            if isinstance(gate_exc, MicrophonePermissionDeniedError):
                _gate_state = getattr(gate_exc, "state", "denied")
                log.warning("[DICTATION] Refusing hotkey start: mic permission %s", _gate_state)
                self._publish_permission_denied_refusal(app, getattr(gate_exc, "state", None) or "denied")
                return
            raise

        # Cancel any stale pending timers from previous sessions
        app._cancel_pending_timers()

        # If a model change was deferred during the previous recording,
        try:
            app.models.apply_pending_model_change()
        except Exception:
            log.exception("[DICTATION] Failed to apply pending model change; continuing")

        # The model load is deferred until AFTER recorder.start() and runs on a
        # daemon worker, so the mic captures speech during the 5-30s reload
        # instead of losing the first words. See _start_dictation_worker_entry.

        log.info("[DICTATION] Starting recording... (cycle=%s)", app._cycle_id)
        # INSTANT-FEEDBACK: surface tray + bubble + start cue BEFORE the
        # blocking recorder.start() so a cold PortAudio open never delays
        # the visible/audible ack. Teardown on failure hides them again.
        self._publish_instant_start_feedback(controller, app)
        try:
            self._wire_recorder_start_callbacks(controller, app)

            app.recorder.start()
            self._notify_mic_watcher_of_active_device(app)
            # System-volume ducking moved OFF this thread: it now runs at
            log.info("[DICTATION] Recording started OK (cycle=%s)", app._cycle_id)
            self._claim_keyboard_ownership_for_recording(app)
            self._rearm_esc_cancel_if_enabled(app)
            self._spawn_dictation_start_worker(controller, app)
        except Exception as e:
            self._hide_instant_start_feedback(app)
            log.exception("[DICTATION] Failed to start recording: %s", e)
            self._teardown_failed_recorder_start(
                controller,
                app,
                restart_level_monitor=True,
                discard_log_label="start-failure teardown",
            )
            self._publish_start_failure_notification(app, e)

    def _publish_instant_start_feedback(self, controller, app) -> None:
        """Show tray + bubble recording state before recorder.start()."""
        try:
            app.tray.set_state(AppState.RECORDING, i18n.t("state.recording_controller.recording"))
        except Exception:
            log.debug("[DICTATION] instant tray feedback failed", exc_info=True)
        try:
            # Show the floating bubble once we know the stream is open,
            # unless the user hid it entirely ("hidden" behavior).
            if getattr(app.config, "bubble_behavior", "show_on_record") != "hidden":
                app._waveform_bubble.show()
                app._waveform_bubble.set_state("recording")
        except Exception:
            log.debug("[DICTATION] instant bubble feedback failed", exc_info=True)
        try:
            self._publish_recording_started_event()
        except Exception:
            log.debug("[DICTATION] instant sound feedback failed", exc_info=True)

    def _hide_instant_start_feedback(self, app) -> None:
        """Hide the optimistic start UI after a failed recorder.start()."""
        try:
            if getattr(app.config, "bubble_behavior", "show_on_record") == "always_visible":
                app._waveform_bubble.set_state("idle")
            else:
                app._waveform_bubble.hide()
        except Exception:
            log.debug("[DICTATION] instant bubble rollback failed", exc_info=True)

    def _start_dictation_worker_entry(
        self,
        controller,
        cycle_id: str,
        complete_event: threading.Event,
    ) -> None:
        """Daemon worker-thread entry point for the model-load + post-load
        phase of ``_start_impl``.

        Mirrors the ``_stop_and_transcribe_worker_entry`` pattern: the F2
        hotkey thread does the synchronous pre-start work (consent check,
        timer cancel, ``recorder.start()``, tray state, bubble show) inside
        ``_start_impl``, then spawns THIS worker and returns after a
        bounded join performed by the public entry (``toggle`` / ``start``
        via ``_run_public_entry``). OUTSIDE ``_toggle_lock``. The worker
        ducks the system volume first (still after ``recorder.start()``,
        so the first buffered chunks capture with the speakers already
        fading down) and then performs the potentially-slow model load
        (5-30s on idle-unload reload) and the post-load steps
        (active_transcriber check, Whisper fallback, streaming-session
        setup).

        Rationale: pre-fix, the F2 dispatch thread blocked for 5-30s
        inside ``ensure_active_engine_loaded()`` on the idle-unload
        reload path. With a single-dispatch-thread hotkey backend
        (pynput), this blocked ALL hotkeys: including ESC cancel, for
        the entire reload window. Moving the load to a daemon worker
        frees the dispatch thread to process subsequent hotkey events
        (e.g. a second F2 to stop the recording whose model is still
        loading).

        The worker runs WITHOUT ``_toggle_lock``. The public entry
        (``toggle`` / ``start`` via ``_run_public_entry``) releases the
        lock before its bounded join, so neither the worker nor the join
        holds it. The worker doesn't need the lock because:
        1. ``ensure_active_engine_loaded()`` has its own internal
           ``_lazy_init_lock`` in ``ModelManager``.
        2. The post-load re-check reads atomic state
           (``recorder.recording``, ``_busy_event.is_set()``).
        3. ``_start_streaming_session_if_enabled()`` uses
           ``_streaming_session_lock`` for its own serialization.

        The worker signals ``complete_event`` in its ``finally`` block so
        tests that assert model-loaded state can wait on the event.

        Parameters
        ----------
        controller:
            The owning :class:`RecordingController` (back-reference).
        cycle_id:
            The cycle ID captured at ``_start_impl`` entry (e.g.
            ``"#42"``). Used for log correlation.
        complete_event:
            A :class:`threading.Event` that the worker signals in its
            ``finally`` block. The F2 thread stores this on the
            controller as ``controller._start_complete_event`` so tests
            can wait on it.
        """
        app = controller._app
        # Duck system volume HERE, not on the hotkey thread: a duck costs
        if app.recorder.recording:
            app._duck_volume()
            # Compensate the off-lock ordering: a concurrent ``cancel()``
            if not app.recorder.recording:
                app._restore_volume()
        try:
            # Load / reload the active engine. This is the potentially
            app.models.ensure_active_engine_loaded()

            # ``_busy_event`` (busy=True), so we check BOTH conditions.
            if not app.recorder.recording or not app._busy_event.is_set():
                log.info(
                    "[DICTATION] Recorder stopped or app became busy during "
                    "model load, aborting post-load steps (cycle=%s)",
                    cycle_id,
                )
                return

            active = app.models.active_transcriber()
            if active is None or not getattr(active, "is_loaded", False):
                # No engine loaded, try to load Whisper as a fallback.
                log.warning("[DICTATION] No loaded engine found, lazy-loading Whisper as fallback")
                app.models.fallback_to_whisper(notify_on_failure=True)
                active = app.models.active_transcriber()
                if active is None or not getattr(active, "is_loaded", False):
                    log.error("[DICTATION] Whisper fallback also failed, cannot record")
                    # The recorder is already running, discard it so we
                    try:
                        app.recorder.discard()
                    except Exception:
                        log.debug(
                            "[DICTATION] recorder.discard() during model-fail teardown raised (best-effort)",
                            exc_info=True,
                        )
                    app.recorder.recording = False
                    app.tray.set_state(
                        AppState.ERROR,
                        i18n.t("state.recording_controller.model_failed_retry"),
                    )
                    app._schedule_timer(
                        3.0,
                        lambda: app.tray.set_state(
                            AppState.ERROR,
                            i18n.t("state.recording_controller.model_failed_retry"),
                        ),
                    )
                    return

            # Streaming session requires an active transcriber, so it
            controller._start_streaming_session_if_enabled()
        except Exception as e:
            log.exception("[DICTATION] Start worker failed: %s", e)
            # Same teardown + typed-reason mapping as the ``_start_impl``
            self._teardown_failed_recorder_start(
                controller,
                app,
                restart_level_monitor=False,
                discard_log_label="start-worker teardown",
            )
            self._publish_start_failure_notification(app, e)
        finally:
            complete_event.set()

    def stop(self, controller) -> None:
        """Stop recording and transcribe in background."""
        with controller._toggle_lock:
            self._stop_impl(controller)

    def _stop_and_transcribe_worker_entry(self, controller, cycle_id: str) -> None:
        """Daemon worker-thread entry point, extracted from the former"""
        app = controller._app
        try:
            # ``recorder.stop()`` is the FIRST step. Pre-fix this ran
            audio = app.recorder.stop()
            # Clear the active-mic-id on the watcher so it stops
            with contextlib.suppress(Exception):
                mic_watcher = getattr(getattr(app.recorder, "_devices", None), "_mic_watcher", None)
                if mic_watcher is not None:
                    mic_watcher.set_active_mic_id(None)
        except Exception:
            log.exception("[DICTATION] Failed to stop recording (worker)")
            controller._cancel_streaming_session()
            app._restore_volume()
            # Best-effort restart of the level_monitor for the
            controller._maybe_restart_level_monitor_for_always_visible_bubble(app)
            app.tray.set_state(AppState.ERROR, i18n.t("state.recording_controller.stop_failed"))
            # Critical, bypass the notification toggle (dictation failed,
            app.tray.notify_safety(
                APP_NAME,
                i18n.t("notify.recording_controller.stop_failed"),
            )
            app._busyness.set_idle()  # busy = False (coordinator)
            app._schedule_timer(3.0, lambda: app.tray.set_state(AppState.IDLE))
            return

        self._run_stop_and_transcribe(controller, audio, cycle_id)

    def _run_stop_and_transcribe(self, controller, audio, cycle_id: str) -> None:
        """Transcription pipeline body, extracted from the former nested
        closure ``stop_and_transcribe_worker``.

        Takes the captured ``audio`` bytes (already resampled to
        ``config.sample_rate`` by ``recorder.stop()``) and the
        ``cycle_id`` (captured at stop time so a new dictation cycle
        starting before transcription completes does not corrupt log
        correlation) and runs the full post-stop pipeline:

        1. Log ring-buffer overflow stats.
        2. Restore system volume + restart the level_monitor for the
           always-visible bubble.
        3. Compute ``duration`` + ``recorded_rms``.
        4. Finalize the audio-quality report (revived
           AudioQualityAnalyzer).
        5. Short-audio gate (``MIN_DURATION_S``): sub-0.5s clips proceed
           only with speech-like energy; taps/near-silence discard.
        6. Set tray to TRANSCRIBING + reset watchdog counter.
        7. Pop + stash the streaming session so the pipeline's
           ``pop_streaming_session()`` can retrieve it and call
           ``session.finalize(audio)``: the streaming fast path.
        8. Start the persistent watchdog thread (RACE-013).
        9. Stash audio in ``controller._current_audio`` (privacy) then
           immediately capture-and-clear so the slot doesn't retain the
           bytes for the transcription duration.
        10. Run ``DictationPipeline.run(...)``.

        Unit-testable: call
        ``self._run_stop_and_transcribe(controller, fake_audio, cycle_id)``
        directly with a mock ``app.recorder`` / ``app.tray``
        / ``app.config`` to exercise the transcription body without
        spinning up a real recorder or hotkey thread.
        """
        app = controller._app

        # Surface ring-buffer overflow detected during the recording.
        dropped = getattr(app.recorder, "_dropped_ring_chunks", 0)
        if dropped:
            log.warning(
                "[DICTATION] Ring buffer overflow during recording: "
                "%d chunks dropped (cycle=%s). Audio worker could not "
                "keep up; transcription may be incomplete.",
                dropped,
                app._cycle_id,
            )

        # Restore system volume immediately, don't wait for transcription
        app._restore_volume()

        # Now that the Recorder's InputStream is closed, restart the
        controller._maybe_restart_level_monitor_for_always_visible_bubble(app)

        # Audio has already been resampled to config.sample_rate by Recorder.stop()
        duration = len(audio) / app.config.sample_rate if len(audio) > 0 else 0
        # Capture RMS before starting transcription (race-safe).
        recorded_rms = _short_clip_rms(app.recorder)
        rms_txt = f"{recorded_rms:.4f}" if recorded_rms is not None else "n/a"
        # Run the revived AudioQualityAnalyzer on the captured audio.
        if duration > 0:
            try:
                app._finalize_audio_quality_report(audio)
            except Exception:
                log.debug("[AUDIO_QUALITY] finalize failed", exc_info=True)
        log.info(
            "[DICTATION] Recording stopped%s of audio | recorded_rms=%s | busy=True (cycle=%s)",
            format_duration(duration),
            rms_txt,
            cycle_id,
        )

        if duration < MIN_DURATION_S:
            short_silence_pct = _short_clip_silence_pct(app.recorder)
            silence_txt = f"{short_silence_pct:.1f}%" if short_silence_pct is not None else "n/a"
            if recorded_rms is not None and _short_clip_has_speech_energy(recorded_rms, short_silence_pct):
                log.info(
                    "[DICTATION] Short recording kept (duration=%.2fs, recorded_rms=%s, "
                    "silence=%s): speech-like energy above the short-audio gate (cycle=%s)",
                    duration,
                    rms_txt,
                    silence_txt,
                    cycle_id,
                )
            else:
                log.info(
                    "[DICTATION] Audio too short, skipping transcription "
                    "(duration=%.2fs, recorded_rms=%s, silence=%s) (cycle=%s)",
                    duration,
                    rms_txt,
                    silence_txt,
                    cycle_id,
                )
                controller._cancel_streaming_session()
                if duration <= 0 and recorded_rms is not None and recorded_rms <= 0.0001:
                    self._publish_permission_denied_refusal(app, "denied")
                    app._busyness.set_idle()
                    return
                try:
                    if getattr(app.config, "bubble_behavior", "show_on_record") == "always_visible":
                        app._waveform_bubble.set_state("idle")
                    else:
                        app._waveform_bubble.hide()
                except Exception:
                    log.debug("[DICTATION] too-short bubble reset failed", exc_info=True)
                app.tray.set_state(AppState.IDLE, i18n.t("state.recording_controller.too_short"))
                app._busyness.set_idle()  # busy = False (coordinator)
                app._schedule_timer(2.0, lambda: app.tray.set_state(AppState.IDLE))
                return

        log.info(
            "[DICTATION] Starting transcription (stop+transcribe worker)... (cycle=%s)",
            cycle_id,
        )
        app.tray.set_state(AppState.TRANSCRIBING, i18n.t("state.recording_controller.transcribing"))

        # Reset watchdog counter for this transcription cycle.
        with controller._watchdog_lock:
            controller._watchdog_firings = 0

        # PERF- signal the streaming session to cancel BEFORE starting
        with controller._streaming_session_lock:
            # ``_stop_impl`` does NOT pop the session or signal cancel.
            controller._pending_finalize_session = controller._streaming_session

        # RACE-013: Start persistent watchdog thread using Event.wait(timeout=90).
        controller._start_watchdog_thread()

        # ``transcribe_thread`` extracted to ``DictationPipeline`` class.
        from voice_typer.server.dictation_pipeline import DictationPipeline

        # Privacy: hold audio bytes in a shared, clearable slot so
        controller._current_audio = audio
        # Capture into a local and clear the shared slot BEFORE calling
        audio_bytes = controller._current_audio
        controller._current_audio = None

        pipeline = DictationPipeline(app)
        # ``run()`` (sole caller always passed ``None``; RACE-013: no
        pipeline.run(
            audio=audio_bytes,
            duration=duration,
            recorded_rms=recorded_rms if recorded_rms is not None else 0.0,
            cycle_id=cycle_id,
        )
        # Now that the transcription pipeline has fully returned (the
        controller._discard_cancelled_cycle_id(cycle_id)

    def cancel(self, controller) -> None:
        """Feature: ESC to cancel -- cancel current recording/transcription."""
        with controller._toggle_lock:
            self._cancel_impl(controller)
