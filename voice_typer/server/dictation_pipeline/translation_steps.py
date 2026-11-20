"""Dictation-pipeline step that runs ADR-0021 Stage B.

Translation is deliberately a separate stage after the empty check and before
cleanup so Stage A text is what the translator sees (never a pasted backend
translation) and an empty transcript never starts the text model.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


class _TranslationStepMixin:
    """Hosts ``_translate`` for the composed :class:`DictationPipeline`."""

    _app: Any

    def _translate(self, text: str) -> str:
        app = getattr(self, "_app", None)
        config = getattr(app, "config", None)
        if config is None or not bool(getattr(config, "translation_enabled", False)):
            return text
        try:
            from voice_typer.server.translation.service import translate_text

            target = str(getattr(config, "translation_target_language", "") or "")
            spoken = str(getattr(config, "language", "") or "")
            return translate_text(text, config, target, spoken)
        except Exception:
            # Translation is an enhancement; a broken model never blocks paste.
            log.exception("[TRANSLATE] stage failed; keeping untranslated text")
            return text
