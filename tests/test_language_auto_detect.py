"""Auto-detect language: ``config.language == ""`` must reach the model as ``None``.

Settings → Post-Processing → Transcription Language → Auto-detect is stored as
an empty string. faster-whisper only runs language detection when it receives
``None``; ``""`` skips that branch and ``Tokenizer`` rejects it, so the empty
sentinel has to be normalized at every engine boundary.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from voice_typer.server.asr_utils import asr_language_param
from voice_typer.worker.whisper import TranscriptionEngine


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


class TestWhisperEngineNormalizesLanguage:
    def test_auto_sentinel_becomes_none(self):
        assert TranscriptionEngine(language="").language is None

    def test_explicit_code_is_preserved(self):
        assert TranscriptionEngine(language="ar").language == "ar"

    def test_default_stays_the_configured_locale(self):
        from voice_typer.server.i18n import DEFAULT_LOCALE

        assert TranscriptionEngine().language == DEFAULT_LOCALE

    def test_absent_language_is_none(self):
        assert TranscriptionEngine(language=None).language is None


class TestDecodeSegmentsPassesNormalizedLanguage:
    """The live dictation path hands ``None`` to faster-whisper for auto."""

    @staticmethod
    def _engine(language: str | None) -> TranscriptionEngine:
        engine = TranscriptionEngine(language=language)
        engine._model = MagicMock()
        engine._model.transcribe.return_value = (iter([_segment()]), _info())
        return engine

    @pytest.mark.parametrize("language", ["", None])
    def test_auto_detect_reaches_model_as_none(self, language):
        engine = self._engine(language)
        _decode(engine, seconds=10.0)
        assert engine._model.transcribe.call_args.kwargs["language"] is None

    @pytest.mark.parametrize("code", ["en", "ar"])
    def test_explicit_language_reaches_model_unchanged(self, code):
        engine = self._engine(code)
        _decode(engine, seconds=10.0)
        assert engine._model.transcribe.call_args.kwargs["language"] == code


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
        engine = TranscriptionEngine(language=asr_language_param(getattr(config, "language", None)))
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
