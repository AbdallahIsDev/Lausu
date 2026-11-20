"""Per-model spoken-language capability: tables, predicate, registry wiring.

The registry's ``supported_languages`` used to be ``None`` ("all languages")
for every model, so a pinned language a model cannot decode was handed to
the engine anyway: Parakeet Ultra has no Arabic, and hinting it Arabic got
the take deleted by its English-only junk guard. These tests pin the real
lists and the "None = all" convention that keeps Whisper ungated.
"""

from __future__ import annotations

import pytest
from voice_typer.server.model_language_support import (
    PARAKEET_LANGUAGES,
    QWEN3_LANGUAGES,
    supports_language,
)
from voice_typer.server.model_registry import get_model_metadata


class TestParakeetLanguages:
    """Parakeet Ultra's published 25-language list."""

    def test_parakeet_declares_its_own_list(self):
        meta = get_model_metadata("parakeet")
        assert meta is not None
        assert meta.supported_languages == list(PARAKEET_LANGUAGES), (
            "parakeet must declare its own 25-language list, not None (= all languages)"
        )

    def test_parakeet_list_has_25_entries(self):
        assert len(PARAKEET_LANGUAGES) == 25, (
            f"parakeet-tdt-0.6b-v3 publishes 25 languages, got {len(PARAKEET_LANGUAGES)}"
        )

    @pytest.mark.parametrize("language", ["ar", "ja", "zh", "hi", "ko", "tr"])
    def test_parakeet_does_not_claim_arabic_and_other_non_eu_languages(self, language: str):
        assert language not in PARAKEET_LANGUAGES, (
            f"{language!r} is not in Parakeet's published European language list; "
            "claiming it would send undecodable audio to the engine"
        )

    @pytest.mark.parametrize("language", ["en", "de", "fr", "es", "nl", "pl"])
    def test_parakeet_supports_common_european_languages(self, language: str):
        assert language in PARAKEET_LANGUAGES


class TestQwenLanguages:
    """Qwen3-ASR's published 30-language list (Arabic included)."""

    def test_qwen_variants_declare_the_same_list(self):
        expected = list(QWEN3_LANGUAGES)
        for name in ("qwen3-1.7b", "qwen3-0.6b"):
            meta = get_model_metadata(name)
            assert meta is not None, f"{name} missing from registry"
            assert meta.supported_languages == expected, f"{name} must declare the Qwen3-ASR language list"

    def test_qwen_list_supports_arabic(self):
        assert "ar" in QWEN3_LANGUAGES, "Qwen3-ASR lists Arabic; the gate must not refuse it"
        assert len(QWEN3_LANGUAGES) == 30, f"Qwen3-ASR publishes 30 languages, got {len(QWEN3_LANGUAGES)}"


class TestWhisperStaysUngated:
    """``None`` still means "every language the decode accepts"."""

    @pytest.mark.parametrize("name", ["tiny", "large-v3", "large-v3-turbo"])
    def test_whisper_declares_no_language_restriction(self, name: str):
        meta = get_model_metadata(name)
        assert meta is not None
        assert meta.supported_languages is None, (
            f"{name} is multilingual Whisper (99 languages), expected supported_languages=None"
        )


class TestSupportsLanguage:
    """The predicate the start gate calls."""

    def test_none_means_every_language(self):
        assert supports_language(None, "ar") is True
        assert supports_language(None, "en") is True

    def test_auto_passes_against_a_restricted_list(self):
        assert supports_language(list(PARAKEET_LANGUAGES), "") is True, (
            "Auto (language='') asks the model to detect the language itself, so it can never be a mismatch"
        )

    def test_listed_language_passes(self):
        assert supports_language(list(PARAKEET_LANGUAGES), "en") is True

    def test_unlisted_language_is_refused(self):
        assert supports_language(list(PARAKEET_LANGUAGES), "ar") is False

    def test_accepts_tuple_supported(self):
        assert supports_language(PARAKEET_LANGUAGES, "de") is True
        assert supports_language(PARAKEET_LANGUAGES, "ar") is False

    def test_empty_list_refuses_every_pinned_language(self):
        assert supports_language([], "en") is False
        assert supports_language([], "") is True
