"""Canonical vocabulary store constants (C-PERSIST-1 categories).

File names, the bundled-corrections path, the six category buckets, and
the SEC-011 resource limits. Moved verbatim out of
``voice_typer.server.vocabulary`` (which re-exports every name, so
``from voice_typer.server.vocabulary import CATEGORIES`` and the
``monkeypatch.setattr(vocabulary, "MAX_CORRECTIONS_ENTRIES", ...)`` test
hook keep working).
"""

from __future__ import annotations

from pathlib import Path

VOCAB_FILENAME = "vocabulary.json"
_LEGACY_VOCAB_FILENAME = "lausu-vocabulary.json"
# single source of truth for the bundled corrections file path.
BUNDLED_CORRECTIONS_PATH = Path(__file__).parent / "corrections.json"

# Persistence model (do NOT flatten or re-merge):
CATEGORIES = [
    "misspellings",
    "phrase_corrections",
    "extra_word_patterns",
    "technical_terms",
    "names",
    "products",
]


# Limits for corrections entries to prevent resource exhaustion
MAX_CORRECTIONS_ENTRIES = 5000
MAX_PATTERN_LENGTH = 200
MAX_REPLACEMENT_LENGTH = 500
