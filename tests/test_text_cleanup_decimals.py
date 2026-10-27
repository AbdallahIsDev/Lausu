"""Decimal punctuation/casing: ``1.7`` must survive cleanup intact.

The spacing pass padded EVERY dot (``1.7`` → ``1. 7``) and the casing pass
then treated that dot as a sentence end (``1. 7 Seconds``). The model
emitted the number correctly, so both rewrites are app bugs fixed at the
source instead of being patched up downstream.
"""

from __future__ import annotations

from voice_typer.server.text_cleanup import clean_transcribed_text
from voice_typer.server.text_cleanup._casing import _capitalize_sentences
from voice_typer.server.text_cleanup._spacing import _normalize_spacing


class TestDecimalSpacing:
    def test_decimal_is_not_split(self):
        assert _normalize_spacing("it took 1.7 seconds") == "it took 1.7 seconds"

    def test_version_number_survives(self):
        assert _normalize_spacing("version 1.0.2 shipped") == "version 1.0.2 shipped"

    def test_sentence_dot_still_gets_a_space(self):
        assert _normalize_spacing("done.next") == "done. next"

    def test_other_punctuation_still_gets_a_space(self):
        assert _normalize_spacing("a,b;c:d!e?f") == "a, b; c: d! e? f"


class TestDecimalCasing:
    def test_word_after_decimal_stays_lowercase(self):
        assert _capitalize_sentences("it took 1.7 seconds") == "It took 1.7 seconds"

    def test_version_suffix_is_not_a_sentence_start(self):
        assert _capitalize_sentences("version 1.0.2 shipped") == "Version 1.0.2 shipped"

    def test_real_sentence_dot_still_capitalizes(self):
        assert _capitalize_sentences("done. next item") == "Done. Next item"


class TestCleanupPipeline:
    def test_decimal_survives_the_whole_cleanup(self):
        cleaned = clean_transcribed_text(
            "version 1.0.2 shipped it took 1.7 seconds",
            auto_punctuation=False,
            skip_corrections=True,
        )
        assert cleaned == "Version 1.0.2 shipped it took 1.7 seconds"
        assert "1. 7" not in cleaned
