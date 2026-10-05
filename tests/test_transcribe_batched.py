"""Batched decode for long recordings (transcription_result._decode_segments)."""

from __future__ import annotations

import threading
import types
from unittest.mock import MagicMock

import numpy as np
import pytest
from voice_typer.server.transcription_result import (
    _BATCHED_BATCH_SIZE,
    _decode_segments,
    _offset_segment,
    _split_on_silence,
    transcribe_unlocked,
)


def _loud_audio(seconds: float, sr: int = 16000) -> np.ndarray:
    return np.full(int(seconds * sr), 0.5, dtype=np.float32)


def _make_engine(**overrides):
    from voice_typer.worker.whisper import TranscriptionEngine

    engine = TranscriptionEngine.__new__(TranscriptionEngine)
    engine.config = MagicMock()
    engine.config.vad_filter_enabled = True
    engine.config.log_transcriptions = False
    engine.config.hallucination_filter_mode = None
    engine.beam_size = 1
    engine.language = "en"
    engine.condition_on_previous_text = False
    engine._device = "cuda"
    engine._abort_event = threading.Event()
    engine.last_quality_summary = None
    for key, value in overrides.items():
        setattr(engine, key, value)
    return engine


def _fw_model():
    """A stub whose type claims the faster_whisper module (no mocks)."""
    cls = type("FakeFwModel", (), {})
    cls.__module__ = "faster_whisper.transcribe"
    return cls()


def _seg(text="hello", start=1.0, end=2.0):
    return types.SimpleNamespace(
        start=start, end=end, text=text, avg_logprob=-0.2, no_speech_prob=0.01
    )


def _info():
    return types.SimpleNamespace(language="en", language_probability=1.0)


class TestSplitOnSilence:
    def test_short_audio_is_one_piece(self):
        audio = _loud_audio(20)
        pieces = _split_on_silence(audio, 16000)
        assert len(pieces) == 1
        assert pieces[0][0] == 0.0
        assert pieces[0][1] is audio

    def test_pieces_cover_audio_contiguously(self):
        audio = _loud_audio(300)
        pieces = _split_on_silence(audio, 16000)
        assert len(pieces) == 3
        offsets = [off for off, _ in pieces]
        assert offsets[0] == 0.0
        total = sum(len(p) for _, p in pieces)
        assert total == len(audio)

    def test_boundary_lands_in_silence(self):
        audio = _loud_audio(250)
        audio[int(118 * 16000) : int(122 * 16000)] = 0.0
        pieces = _split_on_silence(audio, 16000)
        assert len(pieces) == 3
        cut_seconds = pieces[1][0]
        assert 108.0 <= cut_seconds <= 132.0
        cut_idx = int(cut_seconds * 16000)
        assert abs(audio[cut_idx]) < 0.01


class TestOffsetSegment:
    def test_shifts_start_and_end(self):
        out = _offset_segment(_seg(start=1.0, end=2.0), 120.0)
        assert out.start == pytest.approx(121.0)
        assert out.end == pytest.approx(122.0)
        assert out.text == "hello"


class TestDecodeSegments:
    def test_short_audio_stays_sequential(self, monkeypatch):
        engine = _make_engine()
        engine._model = MagicMock()
        engine._model.transcribe.return_value = (iter([_seg()]), _info())

        def _boom(*a, **k):
            raise AssertionError("batched pipeline must not be built for short audio")

        monkeypatch.setattr("faster_whisper.BatchedInferencePipeline", _boom)
        segments, info = _decode_segments(engine, _loud_audio(10), True, 10.0)
        assert [s.text for s in segments] == ["hello"]
        assert info.language == "en"
        engine._model.transcribe.assert_called_once()

    def test_cpu_stays_sequential(self, monkeypatch):
        engine = _make_engine(_device="cpu")
        engine._model = MagicMock()
        engine._model.transcribe.return_value = (iter([_seg()]), _info())

        def _boom(*a, **k):
            raise AssertionError("batched pipeline must not be built off CUDA")

        monkeypatch.setattr("faster_whisper.BatchedInferencePipeline", _boom)
        segments, _ = _decode_segments(engine, _loud_audio(61), True, 61.0)
        assert [s.text for s in segments] == ["hello"]
        engine._model.transcribe.assert_called_once()

    def test_condition_on_previous_text_stays_sequential(self):
        engine = _make_engine(condition_on_previous_text=True)
        engine._model = MagicMock()
        engine._model.transcribe.return_value = (iter([_seg()]), _info())
        segments, _ = _decode_segments(engine, _loud_audio(61), True, 61.0)
        assert [s.text for s in segments] == ["hello"]
        engine._model.transcribe.assert_called_once()

    def test_import_failure_falls_back_to_sequential(self, monkeypatch):
        engine = _make_engine()
        engine._model = MagicMock()
        engine._model.transcribe.return_value = (iter([_seg()]), _info())
        monkeypatch.delattr("faster_whisper.BatchedInferencePipeline", raising=False)
        segments, _ = _decode_segments(engine, _loud_audio(61), True, 61.0)
        assert [s.text for s in segments] == ["hello"]
        engine._model.transcribe.assert_called_once()

    def test_long_cuda_audio_uses_batched_pipeline(self, monkeypatch):
        engine = _make_engine()
        engine._model = _fw_model()
        seen = []

        class FakePipeline:
            def __init__(self, model):
                seen.append(model)

            def transcribe(self, audio, **kwargs):
                seen.append(kwargs)
                return ([_seg(text="chunk")], _info())

        monkeypatch.setattr("faster_whisper.BatchedInferencePipeline", FakePipeline)
        segments, info = _decode_segments(engine, _loud_audio(61), True, 61.0)
        assert [s.text for s in segments] == ["chunk"]
        assert info.language == "en"
        assert seen[1]["batch_size"] == _BATCHED_BATCH_SIZE
        assert seen[1]["beam_size"] == 1
        assert seen[1]["temperature"] == 0.0
        assert seen[1]["without_timestamps"] is True


class TestTranscribeUnlockedBatched:
    def test_offsets_across_super_chunks(self, monkeypatch):
        engine = _make_engine()
        engine._model = _fw_model()

        class FakePipeline:
            def __init__(self, model):
                pass

            def transcribe(self, audio, **kwargs):
                return ([_seg(text="w", start=1.0, end=2.0)], _info())

        monkeypatch.setattr("faster_whisper.BatchedInferencePipeline", FakePipeline)
        text = transcribe_unlocked(engine, _loud_audio(250))
        assert text == "w w w"
        assert engine.last_quality_summary is not None

    def test_abort_between_chunks_stops_early(self, monkeypatch):
        engine = _make_engine()
        engine._model = _fw_model()
        calls = []

        class FakePipeline:
            def __init__(self, model):
                pass

            def transcribe(self, audio, **kwargs):
                calls.append(len(audio))
                engine._abort_event.set()
                return ([_seg(text="w")], _info())

        monkeypatch.setattr("faster_whisper.BatchedInferencePipeline", FakePipeline)
        text = transcribe_unlocked(engine, _loud_audio(250))
        assert text == ""
        assert len(calls) == 1
