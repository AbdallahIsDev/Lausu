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


class TestParakeetEngineNormalizesLanguage:
    """Parakeet never decodes with the language, but it arms an English-only
    junk filter from it. Auto must therefore NOT look like pinned English."""

    def test_auto_sentinel_becomes_none(self):
        from voice_typer.server.parakeet_engine.engine import ParakeetEngine

        assert ParakeetEngine(language="").language is None

    @pytest.mark.parametrize("language", ["", None])
    def test_auto_never_arms_the_english_only_filter(self, language):
        from voice_typer.server.parakeet_engine._helpers import _is_likely_english
        from voice_typer.server.parakeet_engine.engine import ParakeetEngine

        engine = ParakeetEngine(language=language)
        # The junk-filter branch in ``_transcribe_segment`` is
        # ``self.language == "en"``; Arabic text proves the difference.
        assert engine.language != "en"
        assert _is_likely_english("مرحبا بالعالم") is False, "fixture sanity: Arabic is not English"

    def test_pinned_english_still_arms_the_filter(self):
        from voice_typer.server.parakeet_engine.engine import ParakeetEngine

        assert ParakeetEngine(language="en").language == "en"

    def test_pinned_arabic_is_preserved(self):
        from voice_typer.server.parakeet_engine.engine import ParakeetEngine

        assert ParakeetEngine(language="ar").language == "ar"


class TestWorkerProxyEnginesNormalizeLanguage:
    """The pack-worker proxies used to coerce Auto to ``"en"``."""

    @pytest.mark.parametrize("language", ["", None])
    def test_parakeet_proxy_auto_is_none(self, language):
        from voice_typer.server.worker_proxy_asr import WorkerParakeetProxyEngine

        assert WorkerParakeetProxyEngine(language=language, client=MagicMock())._language is None

    @pytest.mark.parametrize("language", ["", None])
    def test_qwen_proxy_auto_is_none(self, language):
        from voice_typer.server.worker_proxy_asr import WorkerQwenProxyEngine

        assert WorkerQwenProxyEngine(language=language, client=MagicMock())._language is None

    @pytest.mark.parametrize("code", ["en", "ar"])
    def test_pinned_code_is_preserved(self, code):
        from voice_typer.server.worker_proxy_asr import WorkerParakeetProxyEngine

        assert WorkerParakeetProxyEngine(language=code, client=MagicMock())._language == code


class TestWorkerLoadersSendAutoAsNone:
    """The model-load requests must not pin English for an Auto config."""

    @staticmethod
    def _client(monkeypatch):
        from voice_typer.server import worker_client

        client = MagicMock()
        client.port = 5555
        future = MagicMock()
        future.result.return_value = {"loaded": False, "error": "test", "device_info": ""}
        client.request_load_whisper_model.return_value = future
        client.request_load_parakeet_model.return_value = future
        client.request_load_qwen_model.return_value = future
        monkeypatch.setattr(worker_client, "get_shared_client", lambda: client)
        return client

    def test_whisper_loader_sends_none_for_auto(self, monkeypatch):
        from voice_typer.server.system_whisper import try_load_worker_whisper

        client = self._client(monkeypatch)
        try_load_worker_whisper(SimpleNamespace(language="", model_size="tiny", device="cpu"))
        assert client.request_load_whisper_model.call_args.args[2] is None

    def test_parakeet_loader_sends_none_for_auto(self, monkeypatch):
        from voice_typer.server.worker_proxy_asr import try_load_worker_parakeet

        client = self._client(monkeypatch)
        try_load_worker_parakeet(SimpleNamespace(language="", device="cpu"))
        assert client.request_load_parakeet_model.call_args.args[1] is None

    def test_qwen_loader_sends_none_for_auto(self, monkeypatch):
        from voice_typer.server.worker_proxy_asr import try_load_worker_qwen

        client = self._client(monkeypatch)
        try_load_worker_qwen(SimpleNamespace(language="", device="cpu", qwen_model_path="/tmp/q"))
        assert client.request_load_qwen_model.call_args.args[2] is None

    def test_pinned_code_reaches_the_loader(self, monkeypatch):
        from voice_typer.server.system_whisper import try_load_worker_whisper

        client = self._client(monkeypatch)
        try_load_worker_whisper(SimpleNamespace(language="ar", model_size="tiny", device="cpu"))
        assert client.request_load_whisper_model.call_args.args[2] == "ar"
