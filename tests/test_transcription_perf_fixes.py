"""Performance fix regression tests for the model-management + transcription paths.

Source-text pins were migrated to behavioral probes per
``docs/adr/source-text-test-migration.md``.
"""

from __future__ import annotations

import sys
import threading
from unittest.mock import MagicMock

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _mock_faster_whisper(monkeypatch):
    """Mock faster_whisper + ctranslate2 so no real model is loaded."""
    mock_fw = MagicMock()
    monkeypatch.setitem(sys.modules, "faster_whisper", mock_fw)
    monkeypatch.setitem(sys.modules, "faster_whisper.WhisperModel", MagicMock())
    mock_ct2 = MagicMock()
    mock_ct2.get_cuda_device_count.return_value = 1
    monkeypatch.setitem(sys.modules, "ctranslate2", mock_ct2)


class TestInferenceCounterReleasesLockDuringInference:
    """The model lock MUST NOT be held during the ctranslate2"""

    def test_init_creates_active_inference_counter(self):
        """``__init__`` must initialise ``_active_inference = 0``."""
        from voice_typer.worker.whisper import TranscriptionEngine

        engine = TranscriptionEngine(model_size="small.en", device="cpu")
        assert engine._active_inference == 0, (
            "TranscriptionEngine.__init__ must initialise _active_inference = 0 so unload() can wait on the cond."
        )

    def test_init_creates_inference_cond_wrapping_lock(self):
        """``_inference_cond`` must be a Condition wrapping ``_lock``."""
        from voice_typer.worker.whisper import TranscriptionEngine

        engine = TranscriptionEngine(model_size="small.en", device="cpu")
        assert isinstance(engine._inference_cond, threading.Condition), "_inference_cond must be a threading.Condition."
        # The Condition's lock must be the engine's _lock so wait()
        assert engine._inference_cond._lock is engine._lock, (
            "_inference_cond must wrap self._lock so wait()/notify() coordinate with the lock acquired in transcribe()."
        )

    def test_transcribe_increments_counter_under_lock(self):
        """``transcribe()`` must increment ``_active_inference`` under"""
        from voice_typer.worker.whisper import TranscriptionEngine

        engine = TranscriptionEngine(model_size="small.en", device="cpu")
        engine._device = "cpu"
        engine._compute_type = "int8"
        mock_model = MagicMock()
        captured_counter = []

        def transcribe_side_effect(*args, **kwargs):
            # Capture the counter value DURING model.transcribe() —
            captured_counter.append(engine._active_inference)
            return ([MagicMock(text="hello")], MagicMock())

        mock_model.transcribe.side_effect = transcribe_side_effect
        engine._model = mock_model

        result = engine.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "hello"
        # Counter was 1 during the call.
        assert captured_counter == [1], (
            f"_active_inference must be 1 during model.transcribe() "
            f"(got {captured_counter}). The lock must be released BEFORE "
            f"the segment loop, but the counter must remain incremented "
            f"so unload() waits."
        )
        # Counter is 0 after the call (finally block decremented).
        assert engine._active_inference == 0

    def test_transcribe_with_fallback_increments_counter(self):
        """``transcribe_with_fallback()`` must also use the counter"""
        from voice_typer.worker.whisper import TranscriptionEngine

        engine = TranscriptionEngine(model_size="small.en", device="cpu")
        engine._device = "cpu"
        engine._compute_type = "int8"
        mock_model = MagicMock()
        captured_counter = []

        def transcribe_side_effect(*args, **kwargs):
            captured_counter.append(engine._active_inference)
            return ([MagicMock(text="hello")], MagicMock())

        mock_model.transcribe.side_effect = transcribe_side_effect
        engine._model = mock_model

        result = engine.transcribe_with_fallback(np.zeros(16000, dtype=np.float32))
        assert result == "hello"
        assert captured_counter == [1], (
            f"transcribe_with_fallback must increment _active_inference "
            f"to 1 during model.transcribe() (got {captured_counter})."
        )
        assert engine._active_inference == 0

    def test_transcribe_words_increments_counter(self):
        """``transcribe_words()`` must also use the counter pattern."""
        from voice_typer.worker.whisper import TranscriptionEngine

        engine = TranscriptionEngine(model_size="small.en", device="cpu")
        engine._device = "cpu"
        engine._compute_type = "int8"
        mock_model = MagicMock()
        captured_counter = []
        segment = MagicMock()
        segment.words = [MagicMock(word=" hello", start=0.0, end=0.5)]

        def transcribe_side_effect(*args, **kwargs):
            captured_counter.append(engine._active_inference)
            return ([segment], MagicMock())

        mock_model.transcribe.side_effect = transcribe_side_effect
        engine._model = mock_model

        result = engine.transcribe_words(np.zeros(16000, dtype=np.float32))
        assert len(result) >= 1
        assert captured_counter == [1], (
            f"transcribe_words must increment _active_inference "
            f"to 1 during model.transcribe() (got {captured_counter})."
        )
        assert engine._active_inference == 0

    def test_lock_not_held_during_model_transcribe(self):
        """The lock MUST NOT be held during ``model.transcribe()``."""
        from voice_typer.worker.whisper import TranscriptionEngine

        engine = TranscriptionEngine(model_size="small.en", device="cpu")
        engine._device = "cpu"
        engine._compute_type = "int8"
        mock_model = MagicMock()
        lock_held_during_call = []

        def transcribe_side_effect(*args, **kwargs):
            acquired = engine._lock.acquire(blocking=False)
            lock_held_during_call.append(not acquired)
            if acquired:
                engine._lock.release()
            return ([MagicMock(text="hello")], MagicMock())

        mock_model.transcribe.side_effect = transcribe_side_effect
        engine._model = mock_model

        engine.transcribe_with_fallback(np.zeros(16000, dtype=np.float32))
        assert lock_held_during_call == [False], (
            f"_lock must NOT be held during model.transcribe() "
            f"(held={lock_held_during_call}). The lock should be released "
            f"before the segment loop so unload() can acquire the cond."
        )


class TestUnloadWaitsForInference:
    """``unload()`` must wait on ``_inference_cond`` for"""

    def test_unload_waits_for_active_inference_to_drain(self):
        """When ``_active_inference > 0``, ``unload()`` must block until"""
        from voice_typer.worker.whisper import TranscriptionEngine

        engine = TranscriptionEngine(model_size="small.en", device="cpu")
        engine._model = MagicMock()

        # Simulate an in-flight transcription: increment the counter
        with engine._inference_cond:
            engine._active_inference += 1

        # Spawn unload() in a thread, it should block on the cond wait.
        unload_done = threading.Event()
        unload_errors: list[BaseException] = []

        def unload_thread():
            try:
                engine.unload()
            except BaseException as exc:  # noqa: BLE001 - reported below, not swallowed
                unload_errors.append(exc)
            finally:
                unload_done.set()

        t = threading.Thread(target=unload_thread, daemon=True)
        t.start()

        assert not unload_done.wait(timeout=0.2), (
            "unload() must block on _inference_cond while "
            "_active_inference > 0 (rather than nulling the model "
            "mid-inference)."
        )
        # The model is still loaded.
        assert engine._model is not None

        # Now drain the counter, notify the cond. unload() should
        with engine._inference_cond:
            engine._active_inference -= 1
            engine._inference_cond.notify_all()

        # Generous deadline: unload() finishes with gc.collect() + GPU release, which
        # a loaded CI runner can stretch well past a couple of seconds.
        assert unload_done.wait(timeout=60.0), (
            "unload() must complete after _active_inference returns to 0 and the cond is notified."
        )
        assert unload_errors == [], unload_errors
        t.join(timeout=5.0)
        assert not t.is_alive(), "unload() must return once the model is released"
        # The model is now nulled.
        assert engine._model is None


class TestParakeetBatchSizeReadAtConstruction:
    """``_INFERENCE_BATCH_SIZE`` must be read from the env var at"""

    def test_instance_attribute_defaults_to_two_when_env_unset(self, monkeypatch):
        """The post-ONNX ``ParakeetEngine`` has NO class-level"""
        from voice_typer.server.parakeet_engine import ParakeetEngine

        # (1) No class-level attribute, the import-time freeze path
        assert "_INFERENCE_BATCH_SIZE" not in ParakeetEngine.__dict__, (
            "IN-5: ParakeetEngine must NOT define _INFERENCE_BATCH_SIZE "
            "as a class attribute, the value is read at construction "
            "time as an instance attribute (a class-level form would "
            "re-introduce the import-time freeze bug)."
        )

        # (2) Construction with the env var unset yields the documented
        monkeypatch.delenv("PARAKEET_BATCH_SIZE", raising=False)
        eng = ParakeetEngine()
        assert eng._INFERENCE_BATCH_SIZE == 2, (
            "IN-5: when PARAKEET_BATCH_SIZE is unset, the instance "
            "attribute must default to 2 (the ONNX-rewritten "
            "production default at parakeet_engine.py __init__)."
        )
        # The attribute is a plain int, not a callable / property / env-var
        assert isinstance(eng._INFERENCE_BATCH_SIZE, int)

    def test_init_reads_env_var_at_construction_time(self, monkeypatch):
        """``__init__`` must read ``PARAKEET_BATCH_SIZE`` from the env"""
        from voice_typer.server.parakeet_engine import ParakeetEngine

        # Construct with PARAKEET_BATCH_SIZE=3, exercises the real
        monkeypatch.setenv("PARAKEET_BATCH_SIZE", "3")
        eng1 = ParakeetEngine()
        assert eng1._INFERENCE_BATCH_SIZE == 3, (
            "IN-5: when PARAKEET_BATCH_SIZE=3 is set, the engine must read 3 at construction time."
        )

        # Change the env var and construct again, the new engine must
        monkeypatch.setenv("PARAKEET_BATCH_SIZE", "4")
        eng2 = ParakeetEngine()
        assert eng2._INFERENCE_BATCH_SIZE == 4, (
            "IN-5: changing PARAKEET_BATCH_SIZE between engine "
            "constructions must take effect (the pre-fix class-attribute "
            "form froze the value at import time)."
        )


class TestSetActiveBackendBlockingRechecksBusy:
    """``_set_active_backend_blocking`` must re-check"""

    def _make_mm_with_mock_backend(
        self,
        *,
        backend_name: str = "whisper",
        recording: bool = False,
        busy: bool = False,
    ):
        """Build a ModelManager with a mock app + real-ish registry."""
        from voice_typer.server.model_manager import ModelManager

        app = MagicMock(name="app")
        app.config.asr_backend = backend_name
        app.config.model_size = "tiny.en"
        app.config.device = "cpu"
        app.config.language = "en"
        app.config.beam_size = 1
        app.config.best_of = 1
        app.config.condition_on_previous_text = False
        app.config.model_idle_unload_minutes = 0
        app._shutting_down = False
        app._pending_dictation = False
        app._thread_registry = MagicMock()
        app._config_mutation_lock = threading.RLock()
        app.recorder.recording = recording
        busy_event = threading.Event()
        if not busy:
            busy_event.set()  # is_set() == True means NOT busy
        app._busy_event = busy_event
        app.config.save.return_value = True

        mm = ModelManager(app)

        engine = MagicMock(name="engine")
        engine.is_loaded = True
        engine.device_info = f"{backend_name}/cpu"

        mock_registry = MagicMock(name="registry")
        mock_registry.active_name = backend_name
        mock_registry.get_active.return_value = engine
        mock_registry.get.return_value = engine
        mock_registry.load_active.return_value = engine
        mock_registry.load_with_fallback.return_value = engine
        mock_registry.available_backends = [backend_name]
        mm._registry = mock_registry

        mm._ensure_engine = MagicMock()
        mm._evict_lru_model = MagicMock()

        return mm, app

    def test_blocking_rechecks_recording_inside_lock(self):
        """When ``recorder.recording`` is True at lock-acquire time,"""
        mm, app = self._make_mm_with_mock_backend(backend_name="whisper", recording=True, busy=False)
        # Pre-register a whisper engine so we can assert it was NOT unloaded.
        whisper_engine = MagicMock()
        whisper_engine.is_loaded = True
        mm._registry.get.return_value = whisper_engine
        mm.transcriber = whisper_engine

        mm._set_active_backend_blocking("qwen")

        # The request was deferred, _pending_backend_change is set.
        assert mm._pending_backend_change == "qwen", (
            "IN-7: _set_active_backend_blocking must re-check "
            "recorder.recording INSIDE the locks and defer (set "
            "_pending_backend_change) when recording is True."
        )
        # Config was persisted.
        assert app.config.asr_backend == "qwen"
        mm._registry.unload.assert_not_called()
        # No load was attempted.
        mm._registry.load_active.assert_not_called()

    def test_blocking_rechecks_busy_event_inside_lock(self):
        """When ``_busy_event.is_set()`` is False (busy) at"""
        mm, app = self._make_mm_with_mock_backend(backend_name="whisper", recording=False, busy=True)
        whisper_engine = MagicMock()
        whisper_engine.is_loaded = True
        mm._registry.get.return_value = whisper_engine
        mm.transcriber = whisper_engine

        mm._set_active_backend_blocking("parakeet")

        assert mm._pending_backend_change == "parakeet", (
            "IN-7: _set_active_backend_blocking must re-check _busy_event INSIDE the locks and defer when busy."
        )
        mm._registry.unload.assert_not_called()
        mm._registry.load_active.assert_not_called()

    def test_blocking_proceeds_when_not_busy(self):
        """full unload/load cycle runs (the re-check does NOT defer"""
        mm, app = self._make_mm_with_mock_backend(backend_name="whisper", recording=False, busy=False)
        whisper_engine = MagicMock()
        whisper_engine.is_loaded = True
        mm._registry.get.return_value = whisper_engine
        mm.transcriber = whisper_engine

        mm._set_active_backend_blocking("qwen")

        # NOT deferred.
        assert mm._pending_backend_change is None, (
            "IN-7: _set_active_backend_blocking must NOT defer when "
            "not recording and not busy, the full unload/load cycle "
            "should run."
        )
        # Config was set.
        assert app.config.asr_backend == "qwen"
        mm._registry.unload.assert_called()
        # Load was attempted.
        mm._registry.load_active.assert_called()

    def test_blocking_rechecks_recording_after_lock_acquire(self):
        """A recording starting at lock-acquire time must still defer the switch.

        The state flip happens as the lock is entered: a re-check that runs
        before the lock would see the stale (idle) value and tear down the
        model mid-recording.
        """
        mm, app = self._make_mm_with_mock_backend(backend_name="whisper", recording=False, busy=False)
        whisper_engine = MagicMock()
        whisper_engine.is_loaded = True
        mm._registry.get.return_value = whisper_engine
        mm.transcriber = whisper_engine
        real_lock = mm._model_change_lock

        class RecordingStartsAtLock:
            def __enter__(self):
                real_lock.acquire()
                app.recorder.recording = True
                return self

            def __exit__(self, *exc):
                real_lock.release()
                return False

        mm._model_change_lock = RecordingStartsAtLock()

        mm._set_active_backend_blocking("qwen")

        assert mm._pending_backend_change == "qwen", (
            "the recorder.recording re-check must run after _model_change_lock is acquired"
        )
        mm._registry.unload.assert_not_called()
        mm._registry.load_active.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
