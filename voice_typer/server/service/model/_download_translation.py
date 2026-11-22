"""ADR-0030 translation-model download branch of ``download_model``.

The translator lives outside MODEL_REGISTRY, so it cannot use the ASR
engine-family downloaders. It reuses the same IPC command, consent gate,
single-flight guard and progress events; the artifact goes to the shared
HF hub cache via :mod:`voice_typer.server.translation.download`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from voice_typer.server.branding import APP_NAME
from voice_typer.server.service._download_helpers import DownloadOutcome

if TYPE_CHECKING:
    from voice_typer.server.app import LausuApp


class TranslationDownloadMixin:
    _app: LausuApp

    if TYPE_CHECKING:
        def _enqueue_download(self, model_name: str) -> DownloadOutcome: ...
        def _require_huggingface_consent(self, model_name: str) -> DownloadOutcome | None: ...

    def _download_translation(self, model_name: str) -> DownloadOutcome:
        """Download Index-Translate Q4_K_M from its HF repo into the hub cache."""
        from voice_typer.server import event_bus
        from voice_typer.server.asr_setup import is_download_active
        from voice_typer.server.service._download_helpers import notify, push_progress
        from voice_typer.server.translation.catalogue import INDEX_TRANSLATE_Q4
        from voice_typer.server.translation.download import download_translation_weights

        if is_download_active():
            return self._enqueue_download(model_name)

        consent_err = self._require_huggingface_consent(model_name)
        if consent_err is not None:
            return consent_err

        push_progress(event_bus, model_name, 0, f"Starting {INDEX_TRANSLATE_Q4.label} download...")
        success, reason, _exc_info = download_translation_weights(
            INDEX_TRANSLATE_Q4,
            config=getattr(self._app, "config", None),
            progress_callback=lambda msg: push_progress(event_bus, model_name, 50, msg),
        )
        if not success:
            message = f"Translation model download failed: {reason}"
            push_progress(event_bus, model_name, 0, message)
            notify(self._app.tray, model_name, APP_NAME, message)
            return {"success": False, "error": reason, "model": model_name}

        push_progress(event_bus, model_name, 100, "Translation model download complete")
        notify(self._app.tray, model_name, APP_NAME, "Translation model downloaded successfully")
        return {"success": True, "model": model_name}
