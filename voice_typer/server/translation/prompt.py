"""Deterministic prompt construction for the local text translator.

The prompt shape is the one used in the 2026-11-18/19 evaluation harness:
an optional terminology block, the model-card translation instruction, then
the source text. No model-as-judge, no few-shot examples, no extra prose.
"""

from __future__ import annotations

import re

from voice_typer.server.translation.catalogue import TRANSLATION_TARGETS, normalize_language_code

_PROMPT = (
    "Translate the following text into {lang}. Note that you should only output "
    "the translated result without any additional explanation:\n\n{src}"
)

_GLOSSARY_HEADER = "Reference the following translations:"
_BACKTICK_PIN = re.compile(r"^`(.+?)`\s+translates to\s+`(.+?)`$", re.IGNORECASE)
_SIMPLE_PIN = re.compile(r"^(.+?)\s*(?:=>|->)\s*(.+)$")
_SEPARATOR = re.compile(r"[\s.!?。！？]+")
_ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")
_LATIN = re.compile(r"[a-zA-Z]")
_MAX_GLOSSARY_TERMS = 24


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


def build_user_prompt(text: str, target_code: str, glossary_raw: str = "") -> str:
    """Render the user message sent to llama-server."""
    target = TRANSLATION_TARGETS.get(normalize_language_code(target_code), target_code)
    blocks: list[str] = []
    pins = parse_glossary(glossary_raw)
    if pins:
        glossary_lines = "\n".join(f"`{source}` translates to `{target_text}`" for source, target_text in pins)
        blocks.append(f"{_GLOSSARY_HEADER}\n{glossary_lines}")
    blocks.append(_PROMPT.format(lang=target, src=text.strip()))
    return "\n\n".join(blocks)


def split_for_translation(text: str, target_code: str) -> list[tuple[str, bool]]:
    """Return ``(chunk, should_translate)`` pairs, preserving separators.

    ADR-0021 §5.2 requires sentence-level routing when the output target is an
    already-present script. We only run the model on chunks that are not
    already in the target script; mixed chunks go through whole because inline
    code-switching cannot be split safely without a second model.
    """
    target = normalize_language_code(target_code)
    if not text:
        return []
    parts = re.split(r"((?<=[.!?。！？])\s+|\n+)", text)
    out: list[tuple[str, bool]] = []
    for part in parts:
        if not part:
            continue
        if _SEPARATOR.fullmatch(part):
            out.append((part, False))
            continue
        has_arabic = bool(_ARABIC.search(part))
        has_latin = bool(_LATIN.search(part))
        if target == "ar" and has_arabic and not has_latin or target == "en" and has_latin and not has_arabic:
            out.append((part, False))
        else:
            out.append((part, True))
    return out


def needs_translation(text: str, target_code: str, spoken_code: str = "") -> bool:
    """ADR-0021 §5.2 skip rule: short text and matching language pass through."""
    target = normalize_language_code(target_code)
    if not target or not text.strip():
        return False
    if target == normalize_language_code(spoken_code):
        return False
    words = text.split()
    if len(words) <= 2 and not any(char.isdigit() for char in text):
        return False
    return any(should for _chunk, should in split_for_translation(text, target))
