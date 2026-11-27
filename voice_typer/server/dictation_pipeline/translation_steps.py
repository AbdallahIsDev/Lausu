"""Dictation-pipeline step that runs ADR-0021 Stage B.

Translation is deliberately a separate stage after the empty check and before
cleanup so Stage A text is what the translator sees (never a pasted backend
translation) and an empty transcript never starts the text model.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.translation import lifecycle as _lifecycle

log = logging.getLogger(__name__)


class _TranslationStepMixin:
    """Hosts ``_translate`` for the composed :class:`DictationPipeline`."""

    _app: Any

    def _translate(self, text: str) -> str:
        app = getattr(self, "_app", None)
        config = getattr(app, "config", None)
        if config is None or not bool(getattr(config, "translation_enabled", False)):
            return text
        # One shared wait for the optional kind; no warm thread here.
        if _lifecycle.is_applicable(config) and not _lifecycle.ensure_translation_loaded(
            config, timeout_s=_lifecycle.TRANSLATION_LOAD_WAIT_S
        ):
            log.warning("[TRANSLATE] load wait failed; keeping original text")
            from voice_typer.server.translation.service import notify_translation_failure

            notify_translation_failure(app)
            return text
        try:
            from voice_typer.server.translation.service import translate_text

            target = str(getattr(config, "translation_target_language", "") or "")
            spoken = str(getattr(config, "language", "") or "")
            return translate_text(text, config, target, spoken, app=app)
        except Exception:
            # Translation is an enhancement; a broken model never blocks paste.
            log.exception("[TRANSLATE] stage failed; keeping untranslated text")
            return text
