"""Auto-detect language: ``config.language == ""`` must reach the model as ``None``.

Settings → Post-Processing → Transcription Language → Auto-detect is stored as
an empty string. The native runner only runs language detection when it receives
``None``; ``""`` skips that branch and ``Tokenizer`` rejects it, so the empty
sentinel has to be normalized at every engine boundary.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np
import pytest
from voice_typer.server.asr_utils import asr_language_param
from voice_typer.worker.asr_runner import GgufTranscriptionEngine as TranscriptionEngine


class TestAsrLanguageParam:
    """The sentinel mapping itself (single source: ``asr_utils``)."""

    def test_empty_string_means_auto_detect(self):
        assert asr_language_param("") is None

    def test_whitespace_only_means_auto_detect(self):
        assert asr_language_param("   ") is None

    def test_absent_config_value_means_auto_detect(self):
        assert asr_language_param(None) is None

    @pytest.mark.parametrize("code", ["en", "ar", "zh", "yue", "haw"])
    def test_real_language_codes_pass_through(self, code):
        assert asr_language_param(code) == code

    def test_surrounding_whitespace_is_trimmed(self):
        assert asr_language_param(" ar ") == "ar"


class TestWorkerHopSendsNormalizedLanguage:
    """The worker hop announces auto as ``None``, never a coerced ``"en"``."""

    @pytest.mark.parametrize(
        ("configured", "expected"),
        [("", None), (None, None), ("en", "en"), ("ar", "ar")],
    )
    def test_config_maps_to_wire_value(self, configured, expected):
        config = SimpleNamespace(language=configured)
        assert asr_language_param(getattr(config, "language", None)) == expected

    def test_engine_rebuilt_from_auto_config_stays_none(self):
        # The worker builds its engine from ``config.language``, not from the
        # hop value, so an auto config must still yield a ``None`` engine.
        config = SimpleNamespace(language="")
        language = asr_language_param(getattr(config, "language", None))
        engine = TranscriptionEngine(model_path="model.gguf", language=language)
        assert engine.language is None


def _segment(text: str = "hello"):
    return SimpleNamespace(start=1.0, end=2.0, text=text, avg_logprob=-0.2, no_speech_prob=0.01)


def _info():
    return SimpleNamespace(language="en", language_probability=1.0)


def _decode(engine: TranscriptionEngine, *, seconds: float):
    from voice_typer.server.transcription_result import _decode_segments

    engine._abort_event = threading.Event()
    audio = np.full(int(seconds * 16000), 0.5, dtype=np.float32)
    return _decode_segments(engine, audio, True, seconds)
