"""Tests for the empty-transcription / silent-suppression fix."""

from __future__ import annotations

import logging
import threading
import time
from unittest.mock import MagicMock

from voice_typer.server.dictation_pipeline import DictationPipeline


class _TestApp:
    """Minimal app stub for unit-testing DictationPipeline methods."""

    def __init__(self) -> None:
        self.tray = MagicMock()
        self.tray.notify = MagicMock()
        self.config = MagicMock()
        self.config.bubble_behavior = "show_on_record"
        self._waveform_bubble = MagicMock()
        self._busy_event = MagicMock()
        self._schedule_timer = MagicMock()
        self.models = MagicMock()
        self.recording = MagicMock()
        # Recorder mock for the finally block in run()
        self.recorder = MagicMock()
        self.recorder.recording = False
        self._lock = MagicMock()
        self._lock.__enter__ = MagicMock(return_value=self._lock)
        self._lock.__exit__ = MagicMock(return_value=False)

    # Auto-mock unknown attributes (like MagicMock) but DO NOT
    def __getattr__(self, name: str) -> MagicMock:
        if name in {
            "_vocab_fail_notified",
            "_template_fail_notified",
            "_history_fail_notified",
            "_crash_recovery_fail_notified",
        }:
            raise AttributeError(name)
        mock = MagicMock()
        object.__setattr__(self, name, mock)
        return mock


def _new_pipeline(app: _TestApp) -> DictationPipeline:
    """Build a fresh DictationPipeline tied to ``app``."""
    pipeline = DictationPipeline.__new__(DictationPipeline)
    pipeline._app = app
    pipeline._duration = 1.0
    pipeline._cycle_id = "test-cycle"
    pipeline._audio = None
    pipeline._audio_stats = None
    pipeline._recorded_rms = 0.0
    pipeline._device_info = ""
    return pipeline


class TestHallucinationRejectionReasonSurfaced:
    """The user must be told WHY the text vanished, not "no speech"."""

    def test_rejected_hallucination_reports_its_own_message(self):
        app = _TestApp()
        pipeline = _new_pipeline(app)
        pipeline._duration = 2.0
        pipeline._recorded_rms = 0.001  # near-silent
        pipeline._rejection_reason = "low-audio hallucination"

        pipeline._handle_empty_transcription()

        statuses = [c.args[1] for c in app.tray.set_state.call_args_list]
        assert any("Ignored likely nonsense" in s for s in statuses), (
            f"a rejected hallucination must not be reported as silence; got {statuses!r}"
        )
        assert "No speech detected" not in statuses

    def test_rejected_hallucination_stays_quiet_on_short_silent_clip(self):
        """Hotkey tap + nothing said: no popup, same as the silence case."""
        app = _TestApp()
        pipeline = _new_pipeline(app)
        pipeline._duration = 2.0
        pipeline._recorded_rms = 0.001
        pipeline._rejection_reason = "low-audio hallucination"

        pipeline._handle_empty_transcription()

        app.tray.notify.assert_not_called()

    def test_genuine_silence_still_reports_no_speech(self):
        """No rejection reason → unchanged pre-existing behavior."""
        app = _TestApp()
        pipeline = _new_pipeline(app)
        pipeline._duration = 2.0
        pipeline._recorded_rms = 0.001
        pipeline._rejection_reason = None

        pipeline._handle_empty_transcription()

        statuses = [c.args[1] for c in app.tray.set_state.call_args_list]
        assert "No speech detected" in statuses

    def test_magicmock_engine_attribute_is_not_trusted(self):
        """A MagicMock auto-creates attributes; only a real str counts."""
        app = _TestApp()
        pipeline = _new_pipeline(app)
        pipeline._duration = 2.0
        pipeline._recorded_rms = 0.001
        engine = MagicMock()  # engine.last_rejection_reason is a Mock, not a str
        pipeline._active_engine_for_test = engine

        # Simulate the capture step's isinstance guard.
        reason = getattr(engine, "last_rejection_reason", None)
        captured = reason if isinstance(reason, str) and reason else None
        pipeline._rejection_reason = captured

        pipeline._handle_empty_transcription()

        statuses = [c.args[1] for c in app.tray.set_state.call_args_list]
        assert "No speech detected" in statuses, "a Mock attribute must not be treated as a reason"

    def test_loud_recording_with_rejection_notifies(self):
        """Longer/louder clip that was discarded still surfaces loudly."""
        app = _TestApp()
        pipeline = _new_pipeline(app)
        pipeline._duration = 30.0
        pipeline._recorded_rms = 0.02
        pipeline._rejection_reason = "low-audio hallucination"

        pipeline._handle_empty_transcription()

        statuses = [c.args[1] for c in app.tray.set_state.call_args_list]
        assert any("Ignored likely nonsense" in s for s in statuses)


class TestHandleEmptyTranscriptionRefinedSuppression:
    """The grace-period suppression must consider recorded_rms."""

    def test_short_recording_with_near_silence_suppresses_notification(self):
        """Original UX-SILENCE-GRACE case: brief hotkey tap, no real audio."""
        app = _TestApp()
        pipeline = _new_pipeline(app)
        pipeline._duration = 2.0  # < 15s grace
        pipeline._recorded_rms = 0.001  # < 0.005 threshold (near silence)

        pipeline._handle_empty_transcription()

        # No popup notification should fire.
        app.tray.notify.assert_not_called()
        # Tray status should reflect "no speech".
        statuses = [c.args[1] for c in app.tray.set_state.call_args_list]
        assert "No speech detected" in statuses, "Short near-silent recording should set tray to 'No speech detected'"

    def test_short_recording_with_real_audio_shows_empty_status(self):
        """HP-7 case: short recording, real audio, engine returned empty."""
        app = _TestApp()
        pipeline = _new_pipeline(app)
        pipeline._duration = 5.0  # < 15s grace
        pipeline._recorded_rms = 0.15  # >= 0.005 threshold (real audio)

        pipeline._handle_empty_transcription()

        # No popup notification, short clip is too ambiguous.
        app.tray.notify.assert_not_called()
        # But tray status must reflect the empty-transcription failure.
        statuses = [c.args[1] for c in app.tray.set_state.call_args_list]
        assert "Transcription returned empty" in statuses, (
            "Short recording with real audio should set tray to "
            "'Transcription returned empty' (HP-7 fix), got: " + str(statuses)
        )

    def test_long_recording_with_near_silence_notifies_check_microphone(self):
        """Long recording with no audio → notify user to check microphone."""
        app = _TestApp()
        pipeline = _new_pipeline(app)
        pipeline._duration = 20.0  # >= 15s grace
        pipeline._recorded_rms = 0.001  # < 0.005 threshold

        pipeline._handle_empty_transcription()

        # Popup notification should fire (microphone may not be capturing).
        app.tray.notify.assert_called_once()
        notification_text = app.tray.notify.call_args.args[1]
        assert "microphone" in notification_text.lower(), (
            "Long near-silent recording should notify user about microphone"
        )

    def test_long_recording_with_real_audio_notifies_empty_transcription(self):
        """Long recording with real audio but empty transcription → notify."""
        app = _TestApp()
        pipeline = _new_pipeline(app)
        pipeline._duration = 20.0  # >= 15s grace
        pipeline._recorded_rms = 0.15  # >= 0.005 threshold (real audio)

        pipeline._handle_empty_transcription()

        # Popup notification should fire.
        app.tray.notify.assert_called_once()
        notification_text = app.tray.notify.call_args.args[1]
        assert "no transcription was produced" in notification_text.lower(), (
            "Long recording with real audio should notify user that "
            "transcription returned empty, got: " + notification_text
        )
        # Tray status must reflect the empty-transcription failure.
        statuses = [c.args[1] for c in app.tray.set_state.call_args_list]
        assert "Transcription returned empty" in statuses


class TestTranscribeEmptyResultDiagnostic:
    """``_transcribe`` must log a consolidated warning when the engine"""

    def test_empty_batch_result_logs_warning(self, caplog):
        """When ``transcribe_with_fallback`` returns \"\" on the batch"""
        app = _TestApp()
        # No streaming session → forces the batch path.
        app.recording.pop_streaming_session.return_value = None

        active = MagicMock()
        active.transcribe_with_fallback.return_value = ""  # empty!
        active.device_info = "mock-device"
        app.models.active_transcriber.return_value = active

        pipeline = _new_pipeline(app)
        pipeline._duration = 5.0
        pipeline._recorded_rms = 0.15
        pipeline._audio_stats = (0.15, 0.5, 25.0)

        with caplog.at_level(logging.WARNING, logger="voice_typer.server.dictation_pipeline"):
            result = pipeline._transcribe()

        assert result == "", "Empty result should propagate unchanged"
        # The diagnostic warning must be logged.
        empty_warnings = [
            r for r in caplog.records if r.levelno == logging.WARNING and "Empty transcription result" in r.getMessage()
        ]
        assert empty_warnings, "Empty transcription must emit a warning log with diagnostic context"
        msg = empty_warnings[0].getMessage()
        # Must include the key signals.
        assert "duration=5.00" in msg, f"duration missing from: {msg}"
        assert "recorded_rms=0.1500" in msg, f"recorded_rms missing from: {msg}"
        assert "backend=" in msg, f"backend missing from: {msg}"
        assert "path=batch" in msg, f"path missing from: {msg}"

    def test_nonempty_result_does_not_log_empty_warning(self, caplog):
        """When transcription succeeds, no empty-result warning fires."""
        app = _TestApp()
        app.recording.pop_streaming_session.return_value = None

        active = MagicMock()
        active.transcribe_with_fallback.return_value = "hello world"
        active.device_info = "mock-device"
        app.models.active_transcriber.return_value = active

        pipeline = _new_pipeline(app)
        pipeline._duration = 5.0
        pipeline._recorded_rms = 0.15
        pipeline._audio_stats = (0.15, 0.5, 25.0)

        with caplog.at_level(logging.WARNING, logger="voice_typer.server.dictation_pipeline"):
            result = pipeline._transcribe()

        assert result == "hello world"
        empty_warnings = [r for r in caplog.records if "Empty transcription result" in r.getMessage()]
        assert not empty_warnings, "Non-empty transcription must NOT emit the empty-result warning"


class TestAsrRegistryUnloadedBackendDiagnostic:
    """``AsrBackendRegistry.get_active`` must log a warning when it"""

    def test_unloaded_backend_warning_logged(self, caplog):
        from voice_typer.server.asr_registry import AsrBackendRegistry

        class _Config:
            asr_backend = "whisper"

        registry = AsrBackendRegistry(_Config())
        # Register a backend with is_loaded=False so get_active() falls
        unloaded_backend = MagicMock()
        unloaded_backend.is_loaded = False
        registry.register("whisper", unloaded_backend)

        with caplog.at_level(logging.WARNING, logger="voice_typer.server.asr_registry"):
            result = registry.get_active()

        assert result is None, "Fail-loud: last-resort unloaded returns None, never serves unloaded"
        unload_warnings = [r for r in caplog.records if "no loaded backend available" in r.getMessage()]
        assert unload_warnings, "get_active() must log a warning when no loaded backend is available"

    def test_loaded_backend_no_warning(self, caplog):
        """When the active backend IS loaded, no warning fires."""
        from voice_typer.server.asr_registry import AsrBackendRegistry

        class _Config:
            asr_backend = "whisper"

        registry = AsrBackendRegistry(_Config())
        loaded_backend = MagicMock()
        loaded_backend.is_loaded = True
        registry.register("whisper", loaded_backend)

        with caplog.at_level(logging.WARNING, logger="voice_typer.server.asr_registry"):
            result = registry.get_active()

        assert result is loaded_backend
        unload_warnings = [r for r in caplog.records if "no loaded backend available" in r.getMessage()]
        assert not unload_warnings, "Loaded backend must NOT trigger the no-loaded-backend warning"


class TestAsrRegistryUnloadedBackendSeverity:
    """An unloaded backend is only a WARNING when it is genuinely unexpected.

    ``get_active()`` runs on passive status polls as well as real transcription,
    so an unconditional WARN made every app launch (model still warming in the
    background) and every deliberate idle-unload look like a failure.
    """

    # ``voice_typer/server/asr/registry.py`` uses ``getLogger(__name__)``, so the
    # emitting logger is ``voice_typer.server.asr.registry``. Naming the facade
    # module instead leaves DEBUG filtered out by the parent logger's level.
    LOGGER = "voice_typer.server.asr.registry"

    @staticmethod
    def _registry_with_unloaded_whisper():
        from voice_typer.server.asr_registry import AsrBackendRegistry

        class _Config:
            asr_backend = "whisper"

        registry = AsrBackendRegistry(_Config())
        backend = MagicMock()
        backend.is_loaded = False
        registry.register("whisper", backend)
        return registry

    def test_expected_unload_logs_debug_not_warning(self, caplog):
        """Gate says the unload was deliberate -> quiet, no WARN."""
        registry = self._registry_with_unloaded_whisper()
        registry.set_last_resort_event_gate(lambda name: True)

        with caplog.at_level(logging.DEBUG, logger=self.LOGGER):
            result = registry.get_active()

        assert result is None, "Fail-loud contract is unchanged"
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert not warnings, (
            f"an expected (deliberately unloaded) backend must not warn: "
            f"{[r.getMessage() for r in warnings]}"
        )
        assert any("expected" in r.getMessage() for r in caplog.records), (
            "the expected-unload case should still be traceable at DEBUG"
        )

    def test_expected_unload_does_not_notify(self, caplog):
        """No tray notification for an expected unload (gate suppresses it)."""
        registry = self._registry_with_unloaded_whisper()
        seen: list[str] = []
        registry.add_last_resort_subscriber(seen.append)
        registry.set_last_resort_event_gate(lambda name: True)

        with caplog.at_level(logging.DEBUG, logger=self.LOGGER):
            registry.get_active()

        assert not seen, f"expected unload must not raise a notification, got {seen}"

    def test_unexpected_unload_still_warns(self, caplog):
        """No gate (a real, unexplained unload) must keep the loud warning."""
        registry = self._registry_with_unloaded_whisper()

        with caplog.at_level(logging.WARNING, logger=self.LOGGER):
            registry.get_active()

        assert any(
            "no loaded backend available" in r.getMessage() for r in caplog.records
        ), "an unexpected unload must still warn so a genuine failure stands out"

    def test_warning_does_not_claim_transcription_was_attempted(self, caplog):
        """The old wording claimed a dictation failed; the caller may be a poll."""
        registry = self._registry_with_unloaded_whisper()

        with caplog.at_level(logging.WARNING, logger=self.LOGGER):
            registry.get_active()

        messages = [r.getMessage() for r in caplog.records]
        assert not any("transcription not attempted" in m for m in messages), (
            "the message must not assert a transcription attempt that a passive "
            "status poll never made"
        )

    def test_raising_gate_fails_closed_and_warns(self, caplog):
        """A broken gate must not be able to hide a genuine alert."""
        registry = self._registry_with_unloaded_whisper()

        def boom(name):
            raise RuntimeError("gate exploded")

        registry.set_last_resort_event_gate(boom)

        with caplog.at_level(logging.WARNING, logger=self.LOGGER):
            registry.get_active()

        assert any(
            "no loaded backend available" in r.getMessage() for r in caplog.records
        ), "a raising gate must fail closed (keep the warning)"


class TestWaitForActiveEngineLoaded:
    """The transcribe path must WAIT for an in-flight load, not give up.

    Dictation that ends while the model is still loading (app warm-up, or an
    idle-unload reload started by the hotkey press) used to discard the
    recording. ``_lazy_init_lock`` is the single serialization point for every
    engine load, so waiting on it recovers the engine.
    """

    @staticmethod
    def _manager(lock: threading.Lock, engine: object | None):
        from voice_typer.server.model_manager import ModelManager

        mgr = object.__new__(ModelManager)
        mgr._lazy_init_lock = lock
        mgr._registry = MagicMock()
        mgr._registry.get_active.return_value = engine
        return mgr

    def test_returns_immediately_when_already_loaded(self):
        engine = MagicMock()
        engine.is_loaded = True
        mgr = self._manager(threading.Lock(), engine)

        assert mgr.wait_for_active_engine_loaded(timeout=5.0) is engine
        # Never blocks: the lock was free and must still be free afterwards.
        assert mgr._lazy_init_lock.acquire(blocking=False)

    def test_returns_none_when_nothing_is_loading(self):
        """No load in flight -> None at once, so the caller still errors fast."""
        engine = MagicMock()
        engine.is_loaded = False
        mgr = self._manager(threading.Lock(), engine)

        assert mgr.wait_for_active_engine_loaded(timeout=5.0) is None

    def test_waits_for_in_flight_load_then_returns_engine(self):
        """The regression: the lock is held by a loader; the wait must block
        until it releases, then hand back the freshly loaded engine."""
        lock = threading.Lock()
        engine = MagicMock()
        engine.is_loaded = False
        mgr = self._manager(lock, engine)

        def _loader() -> None:
            # Mimic ensure_active_engine_loaded: hold the lock across the load.
            with lock:
                time.sleep(0.4)
                engine.is_loaded = True

        thread = threading.Thread(target=_loader, daemon=True)
        thread.start()
        time.sleep(0.05)  # let the loader take the lock
        assert not lock.acquire(blocking=False), "loader should hold the lock"

        start = time.monotonic()
        result = mgr.wait_for_active_engine_loaded(timeout=5.0)
        elapsed = time.monotonic() - start

        assert result is engine, "must return the engine once the load lands"
        assert elapsed >= 0.2, f"must actually block for the load, waited {elapsed:.2f}s"
        thread.join(timeout=5)

    def test_wait_timeout_is_bounded(self):
        """A permanently held lock must not hang the transcription worker."""
        lock = threading.Lock()
        engine = MagicMock()
        engine.is_loaded = False
        mgr = self._manager(lock, engine)

        assert lock.acquire(blocking=False)
        try:
            start = time.monotonic()
            assert mgr.wait_for_active_engine_loaded(timeout=0.2) is None
            assert time.monotonic() - start < 3.0
        finally:
            lock.release()


class TestCancelledCycleEmptyHandling:
    """An ESC-cancelled cycle that aborts before the first"""

    def _cancelled_app(self, cancelled: bool = True) -> _TestApp:
        app = _TestApp()
        # Simulate recording_lifecycle ESC path:
        if cancelled:
            app.recording._cancelled_cycle_ids = {"test-cycle"}
        else:
            app.recording._cancelled_cycle_ids = {"other-cycle"}
        app.recording._cancelled_cycle_ids_lock = threading.Lock()
        return app

    def test_cancelled_cycle_is_quiet(self):
        """Long recording with real audio (the notify branch) + cancelled"""
        app = self._cancelled_app(cancelled=True)
        pipeline = _new_pipeline(app)
        pipeline._duration = 20.0  # past the 15s grace, would notify
        pipeline._recorded_rms = 0.01  # real audio, would notify

        pipeline._handle_empty_transcription()

        app.tray.set_state.assert_not_called()
        app.tray.notify.assert_not_called()
        app._schedule_timer.assert_not_called()

    def test_active_cycle_keeps_existing_behavior(self):
        """A non-cancelled cycle with the same empty result keeps the"""
        app = self._cancelled_app(cancelled=False)
        pipeline = _new_pipeline(app)
        pipeline._duration = 20.0
        pipeline._recorded_rms = 0.01

        pipeline._handle_empty_transcription()

        app.tray.notify.assert_called_once()
