"""Per-engine voice + language catalogues (one source for backend, IPC and UI).

Voice selection has exactly ONE wire form, and it is a SPEAKER INDEX, not a
name. ``nemo-speech 0.3.0`` resolves a name through its own speaker table and
that table is out of order: the runtime logs ``voice="Sofia"`` as ``speaker=1``
while the pack's ``*.nemo.speakers.json`` (the model's ``speaker_map``) puts
Jason at index 1, so picking Sofia spoke Jason — a male voice. A numeric string
is taken as the index instead (``voice="4"`` reaches the runtime log as
``speaker=4``), so every voice ships the index its name has in the model's own
map. ``wire_voice()`` is the only place that decides what reaches the runtime.

Audio8 has no preset speakers (it clones from a reference recording), so it
advertises one non-selectable entry and no wire value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Gender = Literal["female", "male", ""]


@dataclass(frozen=True)
class TtsVoice:
    """One selectable voice for one engine.

    ``wire`` is the exact value the runtime's speech endpoint receives — the
    speaker index for Magpie, empty for an engine with no voice selector (nothing
    is sent then).
    """

    id: str
    label: str
    gender: Gender = ""
    wire: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "gender": self.gender}


#: Language codes the Magpie runtime advertises for this build, read verbatim
#: from ``GET /v1/models`` on the installed binary (``nemo-speech 0.3.0``).
#: Japanese/Mandarin are absent by design: both need ``NEMO_SPEECH_TTS_WITH_JA``
#: / ``_ZH`` build options that default to OFF, and the runtime answers
#: ``400 native Magpie tokenizer is not available for language_code 'ja-JP'``.
MAGPIE_LANGUAGES: tuple[str, ...] = (
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

#: The runtime's five baked English speakers. ``wire`` is each speaker's index
#: in the pack's own ``speaker_map`` — Aria 0, Jason 1, John 2, Leo 3, Sofia 4,
#: verified by rendering with ``--speaker N`` and with ``--voice "N"`` (byte
#: identical) and by the runtime logging ``voice="4"`` as ``speaker=4``.
#: Sending the NAME instead reorders them (Sofia -> 1 = Jason), which is why the
#: index is the wire form.
MAGPIE_VOICES: tuple[TtsVoice, ...] = (
    TtsVoice(id="Aria", label="Aria", gender="female", wire="0"),
    TtsVoice(id="Sofia", label="Sofia", gender="female", wire="4"),
    TtsVoice(id="Jason", label="Jason", gender="male", wire="1"),
    TtsVoice(id="Leo", label="Leo", gender="male", wire="3"),
    TtsVoice(id="John", label="John", gender="male", wire="2"),
)

AUDIO8_VOICES: tuple[TtsVoice, ...] = (TtsVoice(id="default", label="Default"),)

ENGINE_VOICES: dict[str, tuple[TtsVoice, ...]] = {
    "audio8": AUDIO8_VOICES,
    "magpie": MAGPIE_VOICES,
}

ENGINE_LANGUAGES: dict[str, tuple[str, ...]] = {
    "audio8": ("en-US",),
    "magpie": MAGPIE_LANGUAGES,
}

DEFAULT_VOICE_BY_ENGINE: dict[str, str] = {engine: voices[0].id for engine, voices in ENGINE_VOICES.items()}

#: Union catalogues for config validation (an unadvertised value must be
#: rejected at config-write time, never handed to a runtime).
ALL_VOICES: frozenset[str] = frozenset(voice.id for voices in ENGINE_VOICES.values() for voice in voices)
ALL_LANGUAGES: frozenset[str] = frozenset(code for codes in ENGINE_LANGUAGES.values() for code in codes)


def voices_for(engine: str) -> tuple[TtsVoice, ...]:
    """Voices ``engine`` actually advertises (empty for an unknown engine)."""
    return ENGINE_VOICES.get(engine, ())


def voice_ids(engine: str) -> tuple[str, ...]:
    return tuple(voice.id for voice in voices_for(engine))


def languages_for(engine: str) -> tuple[str, ...]:
    return ENGINE_LANGUAGES.get(engine, ())


def default_voice(engine: str) -> str:
    return DEFAULT_VOICE_BY_ENGINE.get(engine, "")


def normalize_voice(engine: str, voice: str | None) -> str:
    """Return an advertised id for ``engine``, falling back to its default."""
    if voice and voice in voice_ids(engine):
        return voice
    return default_voice(engine)


def wire_voice(engine: str, voice: str | None) -> str:
    """Return the runtime selector for ``voice`` (``""`` = send nothing).

    Magpie's selector is the model's speaker index, never the display name.
    """
    wanted = normalize_voice(engine, voice)
    for entry in voices_for(engine):
        if entry.id == wanted:
            return entry.wire
    return ""


def voice_gender(engine: str, voice: str | None) -> str:
    """Gender of an advertised voice, for log lines (``""`` when unknown)."""
    wanted = normalize_voice(engine, voice)
    for entry in voices_for(engine):
        if entry.id == wanted:
            return entry.gender
    return ""


def normalize_language(engine: str, language: str | None) -> str:
    """Return an advertised language code, or the engine's first code."""
    codes = languages_for(engine)
    if language and language in codes:
        return language
    return codes[0] if codes else ""


__all__ = [
    "ALL_LANGUAGES",
    "ALL_VOICES",
    "AUDIO8_VOICES",
    "DEFAULT_VOICE_BY_ENGINE",
    "ENGINE_LANGUAGES",
    "ENGINE_VOICES",
    "MAGPIE_LANGUAGES",
    "MAGPIE_VOICES",
    "TtsVoice",
    "default_voice",
    "languages_for",
    "normalize_language",
    "normalize_voice",
    "voice_gender",
    "voice_ids",
    "voices_for",
    "wire_voice",
]
