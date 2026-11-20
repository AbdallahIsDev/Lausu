"""Which spoken languages each speech model can actually transcribe.

Single source of truth for per-model language capability. The registry's
``supported_languages=None`` keeps meaning "every language the decode
accepts" (Whisper's 99). A model that publishes its own smaller list gets
an explicit tuple here, so a pinned language outside that list is refused
before any audio is captured instead of decoded into nonsense.
"""

from __future__ import annotations

# nvidia/parakeet-tdt-0.6b-v3, the base of Parakeet Ultra: 25 European
# languages, Arabic NOT among them (model card, "Supported Languages").
PARAKEET_LANGUAGES: tuple[str, ...] = (
    "bg",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "et",
    "fi",
    "fr",
    "de",
    "el",
    "hu",
    "it",
    "lv",
    "lt",
    "mt",
    "pl",
    "pt",
    "ro",
    "sk",
    "sl",
    "es",
    "sv",
    "ru",
    "uk",
)

# Qwen3-ASR 1.7B / 0.6B: the 30 languages the model card lists (Arabic
# included). Dialects are not separate codes here.
QWEN3_LANGUAGES: tuple[str, ...] = (
    "zh",
    "en",
    "yue",
    "ar",
    "de",
    "fr",
    "es",
    "pt",
    "id",
    "it",
    "ko",
    "ru",
    "th",
    "vi",
    "ja",
    "tr",
    "hi",
    "ms",
    "nl",
    "sv",
    "da",
    "fi",
    "pl",
    "cs",
    "fil",
    "fa",
    "el",
    "hu",
    "mk",
    "ro",
)


def supports_language(supported: list[str] | tuple[str, ...] | None, language: str) -> bool:
    """True when a model declaring ``supported`` may decode ``language``.

    ``""`` (Auto) always passes: Auto asks the model to detect the spoken
    language itself, so there is no pinned mismatch to refuse.
    """
    if not language:
        return True
    if supported is None:
        return True
    return language in supported


__all__ = ["PARAKEET_LANGUAGES", "QWEN3_LANGUAGES", "supports_language"]
