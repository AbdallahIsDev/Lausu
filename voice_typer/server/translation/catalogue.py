"""Separate catalogue for the app's one text-translation model.

ADR-0030 keeps ASR models and the text translator in different registries.
Nothing in here is added to ``MODEL_REGISTRY``: that registry now means
"one resident ASR model" and its size is pinned by tests.

The Q4_K_M artefact was measured locally on 2026-11-19 at
1,312,164,352 bytes. It is NOT downloaded or shipped by this change; the
runtime resolves it from an explicit config path or the LAUSU_TRANSLATION_MODEL
environment override.
"""

from __future__ import annotations

from dataclasses import dataclass

TRANSLATION_MODEL_ID = "index-translate-2b-q4-k-m"
# Exact filename from the HF repo (verified against SHA256SUMS.txt): the
# lowercase alias was a dev-only Ollama blob name and must not be used for
# the HF-cache download path.
TRANSLATION_MODEL_FILENAME = "Index-Translate-2B.Q4_K_M.gguf"
TRANSLATION_MODEL_SIZE_BYTES = 1_312_164_352
TRANSLATION_MODEL_SHA256 = "044b313d29342bd3b2c77cbb64023ca0d209bd9b3247763f9d162767ef2d746a"
TRANSLATION_MODEL_REPO_ID = "IndexTeam/Index-Translate-2B-GGUF"
TRANSLATION_MODEL_LICENSE = "Apache-2.0"

# ADR-0021 scope lock: the 8 core locales. "" means "same as spoken" and
# never triggers the translator. Keep this in step with the renderer's
# LANGUAGE_OPTIONS ordering; the app has no claim outside these 8.
TRANSLATION_TARGETS: dict[str, str] = {
    "en": "English",
    "zh": "Chinese",
    "hi": "Hindi",
    "es": "Spanish",
    "ar": "Arabic",
    "fr": "French",
    "ru": "Russian",
    "de": "German",
}

ALLOWED_TRANSLATION_MODELS: frozenset[str] = frozenset({TRANSLATION_MODEL_ID, ""})
ALLOWED_TRANSLATION_TARGETS: frozenset[str] = frozenset({*TRANSLATION_TARGETS, ""})


@dataclass(frozen=True)
class TranslationModelSpec:
    """Static facts about the one translation model build we support."""

    id: str
    label: str
    filename: str
    size_bytes: int
    sha256: str
    repo_id: str
    license: str

    @property
    def size_gb(self) -> float:
        return round(self.size_bytes / 1_000_000_000, 2)


INDEX_TRANSLATE_Q4 = TranslationModelSpec(
    id=TRANSLATION_MODEL_ID,
    label="Index-Translate-2B Q4_K_M",
    filename=TRANSLATION_MODEL_FILENAME,
    size_bytes=TRANSLATION_MODEL_SIZE_BYTES,
    sha256=TRANSLATION_MODEL_SHA256,
    repo_id=TRANSLATION_MODEL_REPO_ID,
    license=TRANSLATION_MODEL_LICENSE,
)

TRANSLATION_MODELS: dict[str, TranslationModelSpec] = {INDEX_TRANSLATE_Q4.id: INDEX_TRANSLATE_Q4}


def normalize_language_code(value: str) -> str:
    """Normalize ``en-US`` / ``AR`` to the core ``en`` / ``ar`` code."""
    code = (value or "").strip().lower().replace("_", "-")
    return code.split("-", 1)[0] if code else ""


def resolve_spec(model_id: str) -> TranslationModelSpec:
    """Return the model spec; an empty id selects the sole shipped model."""
    key = model_id or TRANSLATION_MODEL_ID
    try:
        return TRANSLATION_MODELS[key]
    except KeyError as exc:
        raise ValueError(f"unknown translation model: {model_id!r}") from exc
