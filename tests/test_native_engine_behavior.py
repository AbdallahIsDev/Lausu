"""Behaviour parity for the ctypes ASR path (fake native library, no model).

These tests replace the legacy Python-engine suites: language handling, the
shared decode ladder, chunking/word merging, cancellation, error mapping,
device fallback and the hallucination gate all run through the shipped
``GgufTranscriptionEngine`` / ``GgufRunner`` bodies.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from voice_typer.worker.asr_runner import GgufTranscriptionEngine, RunnerError

from tests.fixtures.fake_native_engine import FakeLibrary, install_runner, make_engine


class TestLanguageHandling:
    def test_auto_sentinel_is_none(self):
        engine = GgufTranscriptionEngine(model_path="model.gguf", language="")
        assert engine.language is None

    def test_explicit_code_is_preserved(self):
        from types import SimpleNamespace

        config = SimpleNamespace(language="ar")
        engine = GgufTranscriptionEngine(model_path="model.gguf", language="ar", config=config)
        assert engine.language is None  # pinned per-model by gguf_model_path_for_key
        assert engine.config is config
        assert engine.config.language == "ar"

    def test_auto_reaches_native_runner_as_none(self, monkeypatch, caplog):
        fake = FakeLibrary(language=b"")
        engine, _ = make_engine(monkeypatch, language=None, fake=fake)
        with (
            caplog.at_level("INFO", logger="voice_typer.worker.asr_runner"),
            caplog.at_level("INFO", logger="voice_typer.server.transcription"),
        ):
            assert engine.transcribe(np.zeros(1600, dtype=np.float32)) == fake.text
        assert not any("configured; not detected" in r.getMessage() for r in caplog.records)

    def test_configured_language_is_not_reported_as_detected(self, monkeypatch, caplog):
        fake = FakeLibrary(language=b"")
        engine, _ = make_engine(monkeypatch, language="en", fake=fake)
        with caplog.at_level("INFO", logger="voice_typer.worker.asr_runner"):
            engine.transcribe(np.zeros(1600, dtype=np.float32))
        assert any("language=en (configured; not detected)" in r.getMessage() for r in caplog.records)


class TestDecodeLadderAndChunking:
    def test_full_temperature_ladder_reaches_the_model(self, monkeypatch):
        engine, _ = make_engine(monkeypatch)
        model = MagicMock()
        model.transcribe.return_value = ([], SimpleNamespace(language="en"))
        engine._model = model
        engine.transcribe(np.zeros(1600, dtype=np.float32))
        kwargs = model.transcribe.call_args.kwargs
        assert kwargs["temperature"] == (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        assert kwargs["vad_filter"] is False

    def test_word_timestamps_carry_offset_and_decode_as_one_call(self, monkeypatch):
        from voice_typer.server.streaming import WordTiming

        engine, _ = make_engine(monkeypatch)
        word0 = SimpleNamespace(word=" hello", start=0.1, end=0.4)
        word1 = SimpleNamespace(word=" there", start=0.5, end=0.9)
        segment = SimpleNamespace(start=0.0, end=1.0, text=" hello there", words=[word0, word1])
        model = MagicMock()
        model.transcribe.return_value = ([segment], SimpleNamespace(language="en"))
        engine._model = model

        timings = engine.transcribe_words(np.zeros(1600, dtype=np.float32), offset_seconds=2.0)
        assert timings == [
            WordTiming(word="hello", start_seconds=2.1, end_seconds=2.4),
            WordTiming(word="there", start_seconds=2.5, end_seconds=2.9),
        ]
        assert model.transcribe.call_args.kwargs["word_timestamps"] is True
        assert model.transcribe.call_args.kwargs["without_timestamps"] is False

    def test_abort_stops_the_word_loop(self, monkeypatch):
        engine, _ = make_engine(monkeypatch)
        words = [SimpleNamespace(word=f" w{i}", start=0.0, end=0.5) for i in range(5)]

        def fake_transcribe(*_args, **_kwargs):
            def segments():
                for index, word in enumerate(words):
                    if index == 2:
                        engine.request_abort()
                    yield SimpleNamespace(start=0.0, end=1.0, text=word.word, words=[word])

            return segments(), SimpleNamespace(language="en")

        model = MagicMock()
        model.transcribe.side_effect = fake_transcribe
        engine._model = model
        assert [w.word for w in engine.transcribe_words(np.zeros(1600, dtype=np.float32))] == ["w0", "w1"]


class TestCancellationAndErrors:
    def test_abort_event_is_a_threading_event_and_is_scopeable(self, monkeypatch):
        engine, _ = make_engine(monkeypatch)
        assert isinstance(engine._abort_event, threading.Event)
        engine.request_abort()
        assert engine._abort_event.is_set()
        engine.clear_abort()
        assert not engine._abort_event.is_set()

    def test_abort_before_run_maps_to_clear_error(self, monkeypatch):
        abort = threading.Event()
        abort.set()
        fake = FakeLibrary()
        install_runner(monkeypatch, fake)
        from voice_typer.worker.asr_runner import GgufRunner

        with pytest.raises(RunnerError):
            GgufRunner("model.gguf").transcribe(np.zeros(1600, dtype=np.float32), abort_event=abort)
        assert fake.run_count == 0

    def test_native_status_maps_to_clear_error(self, monkeypatch):
        from voice_typer.worker.asr_runner import GgufRunner

        fake = FakeLibrary(status=13)
        from tests.fixtures.fake_native_engine import loader_for

        with pytest.raises(RunnerError, match="stopped"):
            GgufRunner("model.gguf", loader=loader_for(fake)).transcribe(np.zeros(1600, dtype=np.float32))

    def test_gpu_error_classifier_still_works(self):
        from voice_typer.server.asr_utils import is_cuda_error

        assert is_cuda_error(RuntimeError("CUDA error: out of memory"))
        assert not is_cuda_error(ValueError("bad config"))


class TestDeviceSelection:
    def test_known_gpu_backend_is_requested(self, monkeypatch):
        captured: list[int] = []
        fake = FakeLibrary()
        orig_open = fake.transcribe_open

        def capture(path, params, session, out):
            captured.append(params._obj.backend)
            return orig_open(path, params, session, out)

        fake.transcribe_open = capture
        from voice_typer.worker.asr_runner import GgufRunner

        from tests.fixtures.fake_native_engine import loader_for

        GgufRunner("model.gguf", loader=loader_for(fake)).transcribe(np.zeros(1600, dtype=np.float32), backend="cuda")
        assert captured == [5]

    def test_unknown_backend_falls_back_to_auto(self, monkeypatch):
        fake = FakeLibrary()
        from voice_typer.worker.asr_runner import GgufRunner

        from tests.fixtures.fake_native_engine import loader_for

        result = GgufRunner("model.gguf", loader=loader_for(fake)).transcribe(
            np.zeros(1600, dtype=np.float32), backend="not-a-backend"
        )
        assert result.text == fake.text
        assert fake.run_count == 1


class TestHallucinationGate:
    def test_gate_is_invoked_and_stamps_rejection(self, monkeypatch):
        engine, _ = make_engine(monkeypatch)
        config = SimpleNamespace(hallucination_filter_mode="strict", log_transcriptions=False)
        engine.config = config
        rejected = engine.reject_low_audio_hallucination(
            result="thanks for watching",
            rms=0.001,
            peak=0.01,
            silence_pct=99.0,
            duration=3.0,
            first_segment_start=0.0,
            last_segment_end=1.0,
        )
        assert rejected
        assert engine.last_rejection_reason == "low-audio hallucination"

    def test_confidence_fields_are_not_fabricated(self, monkeypatch):
        engine, _ = make_engine(monkeypatch)
        text = engine.transcribe(np.zeros(1600, dtype=np.float32))
        assert text
        assert engine.last_quality_summary is None or all(
            value is not None for value in engine.last_quality_summary.values()
        )
