"""Deterministic prompt construction for the local text translator.

The prompt shape is the one used in the 2026-11-18/19 evaluation harness:
an optional terminology block, the model-card translation instruction, then
the source text. No model-as-judge, no few-shot examples, no extra prose.
"""

from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple

from voice_typer.server.translation.catalogue import TRANSLATION_TARGETS, normalize_language_code
from voice_typer.server.translation.preservation import unprotected_text

_PROMPT = (
    "Translate the following text into {lang}. Note that you should only output "
    "the translated result without any additional explanation:\n\n{src}"
)

_GLOSSARY_HEADER = "Reference the following translations:"
_PRESERVE_HEADER = (
    "Keep the bracketed markers below EXACTLY as written; they are protected "
    "URLs, emails, code or numbers, not text to translate:"
)
_BACKTICK_PIN = re.compile(r"^`(.+?)`\s+translates to\s+`(.+?)`$", re.IGNORECASE)
_SIMPLE_PIN = re.compile(r"^(.+?)\s*(?:=>|->)\s*(.+)$")
_ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")
_LATIN = re.compile(r"[a-zA-Z]")
_DEVANAGARI = re.compile(r"[\u0900-\u097f]")
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")
_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_MAX_GLOSSARY_TERMS = 24

# Script families whose alphabet maps to ONE of the eight core targets with
# certainty. Latin cannot: en/es/fr/de all share it, so Latin-only text is
# ambiguous unless a pinned speaking language confirms the target.
_SCRIPT_TO_LANGUAGE = {
    "arabic": "ar",
    "devanagari": "hi",
    "cyrillic": "ru",
    "han": "zh",
}
_SCRIPTS = {
    "arabic": _ARABIC,
    "devanagari": _DEVANAGARI,
    "cyrillic": _CYRILLIC,
    "han": _HAN,
    "latin": _LATIN,
}
# A script is "present" only above this share of letters; stray Latin letters
# inside an otherwise Arabic sentence (a brand name) must not read as mixed.
_MIXED_SCRIPT_MIN_SHARE = 0.10
# Below this many letters the script signal is too weak to skip on.
_MIN_DETECT_LETTERS = 3


class LanguageDetection(NamedTuple):
    """Result of script-based source-language detection."""

    code: str  # confident code, or "" when unknown/mixed/Latin
    mixed: bool
    confident: bool
    letters: int  # letter count after protected spans are removed


def parse_glossary(raw: str) -> list[tuple[str, str]]:
    """Parse ``source => target`` / ``source -> target`` / model-card pins.

    Blank lines and ``#`` comments are ignored. The cap keeps a pasted glossary
    from eating the model's context or turning the translation into lookup.
    """
    pins: list[tuple[str, str]] = []
    for line in (raw or "").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        match = _BACKTICK_PIN.match(text)
        if match:
            source, target = match.group(1), match.group(2)
        else:
            simple = _SIMPLE_PIN.match(text)
            if not simple:
                continue
            source, target = simple.group(1), simple.group(2)
        source = source.strip().strip("`").strip()
        target = target.strip().strip("`").strip()
        if source and target:
            pins.append((source, target))
        if len(pins) >= _MAX_GLOSSARY_TERMS:
            break
    return pins


def build_user_prompt(
    text: str,
    target_code: str,
    glossary_raw: str = "",
    markers: tuple[str, ...] = (),
) -> str:
    """Render the user message sent to llama-server.

    ``markers`` are the protected-span placeholders already substituted into
    *text*; listing them explicitly stops the model from rewriting a URL or
    a number. With no markers the output is byte-identical to the evaluated
    prompt shape.
    """
    target = TRANSLATION_TARGETS.get(normalize_language_code(target_code), target_code)
    blocks: list[str] = []
    pins = parse_glossary(glossary_raw)
    if pins:
        glossary_lines = "\n".join(f"`{source}` translates to `{target_text}`" for source, target_text in pins)
        blocks.append(f"{_GLOSSARY_HEADER}\n{glossary_lines}")
    if markers:
        blocks.append(f"{_PRESERVE_HEADER}\n" + " ".join(markers))
    blocks.append(_PROMPT.format(lang=target, src=text.strip()))
    return "\n\n".join(blocks)


def detect_source_language(text: str) -> LanguageDetection:
    """Detect the source language from the script of the written text.

    Only Arabic / Devanagari / Cyrillic / Han map to a single core language
    with certainty. Latin is shared by en/es/fr/de, so Latin-only text is
    reported as unknown (never a confident match). Protected spans are removed
    first so a URL or an email cannot inject a foreign script.
    """
    cleaned = unprotected_text(text)
    # Count letters only. The Arabic block also contains digits and
    # punctuation (، ؟ ٠-٩); counting those as "Arabic letters" can tip a
    # mostly-Latin sentence into a false mixed-script reading.
    counts = {
        name: sum(1 for ch in pattern.findall(cleaned) if unicodedata.category(ch).startswith("L"))
        for name, pattern in _SCRIPTS.items()
    }
    total = sum(counts.values())
    if total == 0:
        return LanguageDetection("", mixed=False, confident=False, letters=0)

    present = [
        name
        for name, count in counts.items()
        if count and (count / total) >= _MIXED_SCRIPT_MIN_SHARE
    ]
    if len(present) > 1:
        return LanguageDetection("", mixed=True, confident=True, letters=total)
    if not present:
        return LanguageDetection("", mixed=False, confident=False, letters=total)

    code = _SCRIPT_TO_LANGUAGE.get(present[0], "")
    return LanguageDetection(code, mixed=False, confident=bool(code), letters=total)


def needs_translation(text: str, target_code: str, spoken_code: str = "") -> bool:
    """Return True when the Stage A text must go through the text model.

    Skip ONLY when detection confidently says the source already equals the
    target. Everything else — mixed scripts, unknown/short text, a differing
    language, or Latin text with an unconfirmed target — is translated. A
    pinned speaking language may confirm an otherwise ambiguous Latin target,
    but only for text long enough to carry a reliable script signal.
    """
    target = normalize_language_code(target_code)
    if not target or not text.strip():
        return False

    detection = detect_source_language(text)
    if detection.mixed:
        return True
    if detection.confident and detection.code:
        return detection.code != target

    # Too short / ambiguous: never skip, even if a language is pinned.
    if detection.letters < _MIN_DETECT_LETTERS:
        return True

    # Latin-only text: a pinned speaking language that equals the target is a
    # confident same-language signal; otherwise send it to the model.
    spoken = normalize_language_code(spoken_code)
    return not (spoken in {"en", "es", "fr", "de"} and spoken == target)
