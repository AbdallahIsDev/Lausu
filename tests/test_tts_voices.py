"""Per-engine TTS voice + language catalogues: real speakers, one wire form."""

from __future__ import annotations

import pytest
from voice_typer.server.tts.voices import (
    ALL_LANGUAGES,
    ALL_VOICES,
    AUDIO8_VOICES,
    ENGINE_VOICES,
    MAGPIE_LANGUAGES,
    MAGPIE_VOICES,
    default_voice,
    languages_for,
    normalize_language,
    normalize_voice,
    voice_gender,
    voice_ids,
    voices_for,
    wire_voice,
)


def test_magpie_advertises_five_named_speakers_with_gender() -> None:
    ids = voice_ids("magpie")
    assert ids == ("Aria", "Sofia", "Jason", "Leo", "John")
    genders = {voice.id: voice.gender for voice in MAGPIE_VOICES}
    assert genders["Aria"] == "female"
    assert genders["Sofia"] == "female"
    assert genders["Jason"] == "male"
    assert genders["Leo"] == "male"
    assert genders["John"] == "male"


def test_audio8_has_a_single_builtin_voice() -> None:
    assert voice_ids("audio8") == ("default",)
    assert AUDIO8_VOICES[0].label == "Default"


def test_every_engine_has_a_default_that_is_advertised() -> None:
    for engine in ENGINE_VOICES:
        assert default_voice(engine) in voice_ids(engine)


def test_normalize_keeps_an_advertised_voice() -> None:
    assert normalize_voice("magpie", "Jason") == "Jason"


def test_normalize_replaces_a_foreign_voice_with_the_engine_default() -> None:
    # A Magpie name on Audio8 (or a stale id) must never reach the runtime.
    assert normalize_voice("audio8", "Jason") == "default"
    assert normalize_voice("magpie", "not-a-voice") == "Aria"
    assert normalize_voice("magpie", None) == "Aria"


def test_unknown_engine_has_no_voices_and_no_default() -> None:
    assert voices_for("nope") == ()
    assert normalize_voice("nope", "Aria") == ""
    assert wire_voice("nope", "Aria") == ""


def test_wire_voice_is_the_model_speaker_index() -> None:
    """The runtime scrambles NAMES; the model's speaker_map indices do not lie.

    ``voice="Sofia"`` reaches the runtime log as ``speaker=1``, and the pack's
    ``speakers.json`` makes index 1 Jason — the reported "Sofia sounds male".
    Sending the index (``voice="4"`` -> ``speaker=4``) selects Sofia.
    """
    assert wire_voice("magpie", "Aria") == "0"
    assert wire_voice("magpie", "Jason") == "1"
    assert wire_voice("magpie", "John") == "2"
    assert wire_voice("magpie", "Leo") == "3"
    assert wire_voice("magpie", "Sofia") == "4"
    # A regression to the display name would silently speak another speaker.
    for voice in MAGPIE_VOICES:
        assert voice.wire != voice.id, voice
    # An unadvertised name falls back to the engine default, never raw input.
    assert wire_voice("magpie", "Klingon") == "0"


def test_wire_voice_is_empty_for_an_engine_without_a_selector() -> None:
    # Audio8 clones only; forwarding any voice name makes its runtime 500.
    assert wire_voice("audio8", "default") == ""


def test_voice_gender_reports_the_catalogue_value() -> None:
    assert voice_gender("magpie", "Sofia") == "female"
    assert voice_gender("magpie", "Leo") == "male"
    assert voice_gender("audio8", "default") == ""


def test_magpie_languages_match_the_runtime_inventory() -> None:
    """Twelve codes, read from the installed runtime's `/v1/models`."""
    assert MAGPIE_LANGUAGES == (
        "en-US",
        "es-ES",
        "de-DE",
        "fr-FR",
        "it-IT",
        "vi-VN",
        "hi-IN",
        "ar-AE",
        "ar-SA",
        "ar-MSA",
        "ko-KR",
        "pt-BR",
    )
    assert len(MAGPIE_LANGUAGES) == 12
    assert "hi-IN" in languages_for("magpie")
    # ja/zh need build flags that default OFF, so this build cannot render them.
    assert "ja-JP" not in MAGPIE_LANGUAGES
    assert "zh-CN" not in MAGPIE_LANGUAGES


def test_normalize_language_keeps_an_advertised_code() -> None:
    assert normalize_language("magpie", "ar-MSA") == "ar-MSA"
    assert normalize_language("magpie", "hi-IN") == "hi-IN"


def test_normalize_language_falls_back_on_junk_and_unknown_engine() -> None:
    assert normalize_language("magpie", "xx-XX") == "en-US"
    assert normalize_language("magpie", None) == "en-US"
    assert normalize_language("nope", "en-US") == ""


def test_union_catalogues_cover_every_engine() -> None:
    assert frozenset({"default", "Aria", "Sofia", "Jason", "Leo", "John"}) == ALL_VOICES
    assert frozenset(MAGPIE_LANGUAGES) | {"en-US"} == ALL_LANGUAGES
    # Every advertised voice has a stable label.
    for engine, voices in ENGINE_VOICES.items():
        for voice in voices:
            assert voice.label, (engine, voice.id)


@pytest.mark.parametrize("engine", ["audio8", "magpie"])
def test_languages_are_engine_specific(engine: str) -> None:
    codes = languages_for(engine)
    assert codes, engine
    assert all("-" in code for code in codes)
