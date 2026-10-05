"""Transcription stage for the dictation pipeline."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any  # noqa: F401  # re-exported for tests (transcribe_step.Any)

from voice_typer.server import i18n
from voice_typer.server._audio_constants import WHISPER_SAMPLE_RATE
from voice_typer.server.branding import APP_NAME
from voice_typer.server.cloud_engines import CloudEngine
from voice_typer.server.dictation_pipeline.helpers import (
    BackendNotLoadedError,
    _lookup_local_whisper,
)
from voice_typer.server.i18n import t as _i18n_t
from voice_typer.server.tray_types import AppState

if TYPE_CHECKING:
    # Type-only import to avoid the import cycle (the orchestrator is
    from voice_typer.server.app import LausuApp

    # Real class (helpers.py), imported for annotation only. The
    from voice_typer.server.dictation_pipeline.helpers import _AbortWatcher

# NOTE: ``_AbortWatcher`` is intentionally NOT imported at module level

log = logging.getLogger(__name__)


class _TranscribeStepMixin:
    """* :meth:`_check_resources_throttled`: throttled wrapper around
    * :meth:`_check_resources`: direct (unthrottled) probe; called
    """

    # Declared here so the standalone mixin type-checks (mypy cannot
    _app: LausuApp
    _cycle_id: str
    _audio: Any
    _audio_stats: tuple[float, float, float] | None
    _duration: float
    _recorded_rms: float
    _last_resources_check_ts: float
    _resources_check_interval: float
    # Hallucination-rejection reason from the last transcription, read by
    # ``_handle_empty_transcription``. ``None`` means "genuine silence".
    _rejection_reason: str | None

    def _hide_or_idle_bubble(self, log_label: str = "bubble hide/set idle") -> None:
        """Hide the waveform bubble or set it to idle (always_visible mode)."""
        try:
            if self._app.config.bubble_behavior == "always_visible":
                self._app._waveform_bubble.set_state("idle")
            else:
                self._app._waveform_bubble.hide()
        except Exception:
            log.debug("[PIPELINE] %s failed", log_label, exc_info=True)

    def _check_resources_throttled(self) -> None:
        """Throttled wrapper around _check_resources.
        Delegates to ``resource_probe.check_resources_throttled`` (extracted
        """
        from voice_typer.server.resource_probe import check_resources_throttled

        interval = getattr(self, "_resources_check_interval", 60.0)
        if not isinstance(interval, (int, float)):
            interval = 60.0
        instance_ts = getattr(self, "_last_resources_check_ts", 0.0)
        if not isinstance(instance_ts, (int, float)):
            instance_ts = 0.0
        app = getattr(self, "_app", None)
        shared_ts = getattr(app, "_shared_resources_check_ts", None) if app is not None else None
        last = float(shared_ts) if isinstance(shared_ts, (int, float)) else float(instance_ts)

        new_ts = check_resources_throttled(
            last,
            float(interval),
            logger=log,
        )
        self._last_resources_check_ts = new_ts
        try:
            if app is not None:
                app._shared_resources_check_ts = new_ts
        except Exception:
            log.debug("[PIPELINE] failed to persist shared resources-check timestamp", exc_info=True)

    def _check_resources(self) -> None:
        """Delegates to ``resource_probe.check_resources`` (DEFERRED extraction target).

        Probe failures are logged at DEBUG level by the delegated ``check_resources``.
        """
        from voice_typer.server.resource_probe import check_resources

        check_resources(logger=log)

    def _await_model_ready(self) -> Any | None:
        """Block until an in-flight model load finishes, then return the engine.

        Returns None when no load is running (the model is genuinely absent, so
        the caller raises ``BackendNotLoadedError``) or the wait times out. The
        recording stays buffered in memory for the duration, which is why this
        is safe: the hotkey thread and the UI are never blocked, only this
        transcription worker.
        """
        log.info(
            "[TRANSCRIBE] No engine loaded yet; holding the recording while the model finishes loading (cycle=%s)",
            self._cycle_id,
        )
        with contextlib.suppress(Exception):
            self._app.tray.set_state(
                AppState.LOADING,
                _i18n_t("state.recording_controller.awaiting_model"),
            )
        engine = self._app.models.wait_for_active_engine_loaded()
        if engine is None:
            return None

        # The wait can consume most of the watchdog window; reset it so the
        # transcription itself is judged on its own time, not the load time.
        with contextlib.suppress(Exception):
            self._app.recording._reset_watchdog()
        with contextlib.suppress(Exception):
            self._app.tray.set_state(
                AppState.TRANSCRIBING,
                _i18n_t("state.recording_controller.transcribing"),
            )
        return engine

    def _transcribe(self) -> str:
        """Step 1: Get transcription via streaming finalize or direct.

        Returns the transcript from the active streaming session (if one
        """
        #  capture the active transcriber ONCE, the
        active = self._app.models.active_transcriber()
        if active is None:
            # The engine may still be loading: the app is warming up at
            # startup, or this hotkey press kicked off an idle-unload reload.
            # Wait for it instead of discarding the audio, which the pipeline
            # zeroes in its finally block. No-ops when nothing is loading.
            active = self._await_model_ready()
        backend_was_loaded = bool(getattr(active, "is_loaded", False))

        # Clear any stale abort from a previous cycle before starting
        from voice_typer.server import dictation_pipeline as _dp_pkg

        _abort_watcher_cls = _dp_pkg._AbortWatcher
        abort_watcher: _AbortWatcher | None = None
        if active is not None and hasattr(active, "clear_abort"):
            with contextlib.suppress(Exception):
                active.clear_abort()
            if hasattr(active, "request_abort"):
                abort_watcher = _abort_watcher_cls(self._app, self._cycle_id, active)
                abort_watcher.start()

        # WHY: the worker device description is produced in the batch branch but consumed below.
        _worker_device_info: str | None = None
        try:
            #  sibling: pop_streaming_session() atomically owns the
            session = self._app.recording.pop_streaming_session()
            if session is not None:
                log.info("[STREAMING] Finalizing streaming transcript (cycle=%s)", self._cycle_id)
                # Annotated so the batch-branch Any return (from the
                try:
                    import numpy as _np

                    _audio_backup = self._audio.copy() if isinstance(self._audio, _np.ndarray) else self._audio
                except Exception:
                    log.debug("[STREAMING] audio backup before finalize failed", exc_info=True)
                    _audio_backup = None
                text: str = session.finalize(self._audio)
                if not text and active is not None and backend_was_loaded and _audio_backup is not None:
                    try:
                        _audio_len = len(_audio_backup)
                    except Exception:
                        log.debug("[STREAMING] len(audio backup) failed", exc_info=True)
                        _audio_len = 0
                    _audio_captured = self._recorded_rms >= 0.005
                    if _audio_len > 0 and _audio_captured:
                        log.info(
                            "[STREAMING] Empty streaming result on high-energy audio "
                            "(rms=%.4f) | retrying batch transcription (cycle=%s)",
                            self._recorded_rms,
                            self._cycle_id,
                        )
                        try:
                            _retry_local = None
                            if isinstance(active, CloudEngine):
                                _retry_local = _lookup_local_whisper(self._app)
                            _registry = self._app.models.registry
                            with _registry.busy_context(_registry.active_name):
                                text = active.transcribe_with_fallback(
                                    _audio_backup,
                                    audio_stats=self._audio_stats,
                                    local_engine=_retry_local,
                                )
                            self._quality_summary = getattr(active, "last_quality_summary", None)
                        except Exception:
                            log.debug(
                                "[STREAMING] Batch retry after empty streaming result failed",
                                exc_info=True,
                            )
                            text = ""
            else:
                # When ``active_transcriber()`` returned None AND
                if active is None:
                    raise BackendNotLoadedError(
                        "No ASR backend is registered, wait for the model "
                        "to finish loading, or open Settings to verify a "
                        "backend is available.",
                        engine_name="<none>",
                    )
                # pass the pre-computed audio stats so the

                # a-review Finding 8: previously this call was wrapped in a
                from voice_typer.server.worker_backed_asr import WorkerBackedAsr as _WorkerBackedAsr

                if isinstance(active, CloudEngine):
                    # When the active backend is a CloudEngine, look
                    local_engine = _lookup_local_whisper(self._app)
                    # Route through the registry's busy-flag wrapper so
                    registry = self._app.models.registry
                    with registry.busy_context(registry.active_name):
                        text = active.transcribe_with_fallback(
                            self._audio,
                            audio_stats=self._audio_stats,
                            local_engine=local_engine,
                        )
                        # Capture the engine's compact quality summary (mean /
                        self._quality_summary = getattr(active, "last_quality_summary", None)
                elif isinstance(active, _WorkerBackedAsr):
                    # C7: whisper runs in the pack worker; there is no
                    # in-process engine left to fall back to. A worker
                    # failure degrades the cycle (never silently empty).
                    # isinstance (not a worker_backed flag read): a plain
                    # MagicMock auto-creates any attribute, so a flag read
                    # would misroute mocked in-process engines here.
                    from voice_typer.server import worker_client as _worker_client_mod
                    from voice_typer.server.worker_backed_asr import WorkerTranscriptionError

                    # Route through the registry's busy-flag wrapper so
                    registry = self._app.models.registry
                    with registry.busy_context(registry.active_name):
                        try:
                            _rate = int(
                                getattr(self._app.config, "sample_rate", WHISPER_SAMPLE_RATE) or WHISPER_SAMPLE_RATE
                            )
                            _lang = str(getattr(self._app.config, "language", None) or "en")
                            text = active.transcribe_with_fallback(
                                self._audio,
                                audio_stats=self._audio_stats,
                                local_engine=None,
                                sample_rate=_rate,
                                language=_lang,
                            )
                            _worker_device_info = active.device_info
                            self._quality_summary = getattr(active, "last_quality_summary", None)
                        except _worker_client_mod.WorkerAbortedError:
                            # WHY: the cancelled-cycle path below owns ESC UX, no misleading message.
                            return ""
                        except WorkerTranscriptionError as _wexc:
                            raise BackendNotLoadedError(
                                "Offline transcription is unavailable (worker hop failed and no "
                                f"in-process engine remains): {_wexc}",
                                engine_name=type(active).__name__,
                            ) from _wexc
                else:
                    # Route through the registry's busy-flag wrapper so
                    registry = self._app.models.registry
                    with registry.busy_context(registry.active_name):
                        text = active.transcribe_with_fallback(
                            self._audio,
                            audio_stats=self._audio_stats,
                            local_engine=None,
                        )
                        # Capture the engine's compact quality summary (mean /
                        self._quality_summary = getattr(active, "last_quality_summary", None)
        finally:
            if abort_watcher is not None:
                with contextlib.suppress(Exception):
                    abort_watcher.stop()

        # PERF-015: refresh the LRU timestamp for the active backend
        with contextlib.suppress(Exception):
            self._app.models.touch_active_model()

        # reuse the captured ``active`` local for device_info
        # WHY: a worker result carries its own device description, prefer it over the local one.
        self._device_info = _worker_device_info or (
            active.device_info if active is not None and hasattr(active, "device_info") else "Parakeet ASR"
        )

        # Empty-transcription diagnostic: when the engine returns an
        if not text:
            backend_name = type(active).__name__ if active is not None else "<none>"
            # Capture the engine's hallucination-rejection reason while
            # ``active`` is in scope; ``_handle_empty_transcription`` runs
            # in a later stage with no engine reference.
            # WHY isinstance: a MagicMock engine auto-creates the attribute,
            # so require a real non-empty string before trusting it.
            _reason = getattr(active, "last_rejection_reason", None)
            self._rejection_reason = _reason if isinstance(_reason, str) and _reason else None
            stats_repr = (
                "rms={:.4f} peak={:.4f} silence_pct={:.1f}".format(*self._audio_stats)
                if self._audio_stats is not None
                else "<unavailable>"
            )
            log.warning(
                "[TRANSCRIBE] Empty transcription result (cycle=%s | "
                "duration=%.2fs, recorded_rms=%.4f, audio_stats=[%s] | "
                "backend=%s, backend_is_loaded=%s, path=%s), check empty transcription handler guidance",
                self._cycle_id,
                self._duration,
                self._recorded_rms,
                stats_repr,
                backend_name,
                backend_was_loaded,
                "streaming" if session is not None else "batch",
            )
            # if the backend was not loaded when we entered
            if not backend_was_loaded:
                raise BackendNotLoadedError(
                    "Active ASR backend is not loaded, "
                    "transcribe_with_fallback returned empty output. "
                    "Check that the model finished loading and that no "
                    "set_active_backend call unloaded it mid-cycle.",
                    engine_name=backend_name,
                )
        return text

    def _handle_empty_transcription(self) -> None:
        """Step 2: Handle case where no speech was detected."""
        # ESC-during-transcribe marks the cycle cancelled
        _recording = getattr(self._app, "recording", None)
        _cancelled_set = getattr(_recording, "_cancelled_cycle_ids", None)
        if _cancelled_set is not None:
            _cancelled_lock = getattr(_recording, "_cancelled_cycle_ids_lock", None)
            if _cancelled_lock is not None:
                with _cancelled_lock:
                    _is_cancelled = self._cycle_id in _cancelled_set
            else:
                _is_cancelled = self._cycle_id in _cancelled_set
            if _is_cancelled:
                log.info(
                    "[TRANSCRIBE] Cycle %s was ESC-cancelled, skipping "
                    "empty-transcription handling (no misleading "
                    "'no speech detected' message)",
                    self._cycle_id,
                )
                self._hide_or_idle_bubble("bubble hide/set idle on cancelled empty")
                return

        # WHY: captured during transcription (see the empty-result branch in
        # ``_transcribe``). Reporting "no speech detected" for a discarded
        # hallucination is misleading -- the model DID produce output, we
        # chose to drop it -- so the user gets the real reason instead.
        _rejected_reason = getattr(self, "_rejection_reason", None)

        log.info("[TRANSCRIBE] No speech detected (cycle=%s)", self._cycle_id)
        # Hide the bubble since there's nothing to
        self._hide_or_idle_bubble("bubble hide/set idle on empty")

        # UX-SILENCE-GRACE: Suppress the notification for short recordings (< 15s).
        _grace_period = 15.0
        # Same near-silence threshold used by the long-recording branch
        _silence_rms_threshold = 0.005
        _audio_was_captured = self._recorded_rms >= _silence_rms_threshold

        if _rejected_reason is not None:
            # A rejected hallucination on a short near-silent clip is the
            # overwhelmingly common case (hotkey tapped, nothing said), so
            # it keeps the grace-period behaviour of staying quiet -- only
            # the wording changes. Longer / louder clips still notify.
            if self._duration < _grace_period and not _audio_was_captured:
                log.info(
                    "[TRANSCRIBE] Short clip discarded as %s, suppressing notification (cycle=%s)",
                    _rejected_reason,
                    self._cycle_id,
                )
                self._app.tray.set_state(
                    AppState.IDLE,
                    _i18n_t("state.dictation_pipeline.rejected_hallucination"),
                )
                with contextlib.suppress(Exception):
                    from voice_typer.server import event_bus

                    event_bus.publish(
                        {
                            "type": "dictation_suppressed",
                            "data": {
                                "duration": self._duration,
                                "recorded_rms": self._recorded_rms,
                                "reason": "hallucination",
                            },
                        }
                    )
            else:
                log.info(
                    "[TRANSCRIBE] Discarded transcription as %s (duration=%.1fs, rms=%.4f, cycle=%s)",
                    _rejected_reason,
                    self._duration,
                    self._recorded_rms,
                    self._cycle_id,
                )
                self._app.tray.set_state(
                    AppState.IDLE,
                    _i18n_t("state.dictation_pipeline.rejected_hallucination"),
                )
        elif self._duration < _grace_period and not _audio_was_captured:
            # Short recording AND near-silence: the user almost certainly
            log.info(
                "[TRANSCRIBE] No speech detected but recording was only %.1fs "
                "(< %.0fs grace period) and near-silent (rms=%.4f), suppressing notification",
                self._duration,
                _grace_period,
                self._recorded_rms,
            )
            self._app.tray.set_state(AppState.IDLE, _i18n_t("state.dictation_pipeline.no_speech_detected"))
            #  (observability): publish a ``dictation_suppressed``
            with contextlib.suppress(Exception):
                from voice_typer.server import event_bus

                event_bus.publish(
                    {
                        "type": "dictation_suppressed",
                        "data": {
                            "duration": self._duration,
                            "recorded_rms": self._recorded_rms,
                            "reason": "short_silence",
                        },
                    }
                )
        elif self._duration < _grace_period and _audio_was_captured:
            # Short recording BUT real audio was captured: the engine
            log.warning(
                "[TRANSCRIBE] Short recording (%.1fs) with audio "
                "(rms=%.4f >= %.4f) produced empty transcription, "
                "engine returned no text (cycle=%s)",
                self._duration,
                self._recorded_rms,
                _silence_rms_threshold,
                self._cycle_id,
            )
            self._app.tray.set_state(
                AppState.IDLE,
                _i18n_t("state.dictation_pipeline.transcription_empty"),
            )
        elif self._recorded_rms < _silence_rms_threshold:
            self._app.tray.set_state(
                AppState.IDLE,
                _i18n_t("state.dictation_pipeline.no_speech_check_mic"),
            )
            self._app.tray.notify(APP_NAME, i18n.t("notify.dictation_pipeline.no_speech_detected"))
        else:
            # Long recording with real audio but the engine returned
            log.warning(
                "[TRANSCRIBE] Long recording (%.1fs) with audio "
                "(rms=%.4f) produced empty transcription, engine "
                "returned no text (cycle=%s)",
                self._duration,
                self._recorded_rms,
                self._cycle_id,
            )
            self._app.tray.set_state(
                AppState.IDLE,
                _i18n_t("state.dictation_pipeline.transcription_empty"),
            )
            self._app.tray.notify(APP_NAME, i18n.t("notify.dictation_pipeline.no_transcription_produced"))
        # busy = False) instead of the raw inverted _busy_event.
        self._app._busyness.set_idle()
        self._app._schedule_timer(2.0, lambda: self._app.tray.set_state(AppState.IDLE))
