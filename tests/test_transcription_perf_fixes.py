"""Performance fix regression tests for the model-management + transcription paths.

Source-text pins were migrated to behavioral probes per
``docs/adr/source-text-test-migration.md``.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest


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
