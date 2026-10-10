"""Qwen and Parakeet backend downloaders (non-Whisper families)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from voice_typer.server.branding import APP_NAME
from voice_typer.server.service._download_helpers import DownloadOutcome

from ._constants import _PARAKEET_REASON_MESSAGES

if TYPE_CHECKING:
    from voice_typer.server.app import LausuApp

log = logging.getLogger(__name__)


class QwenParakeetDownloadMixin:

    """Qwen and Parakeet backend downloaders (non-Whisper families).

    Host-state contract: the declarations below are attributes the
    composed ``ModelMixin`` (or a sibling mixin) owns.

    The TYPE_CHECKING stubs name methods the composite provides.
    """

    _app: LausuApp

    if TYPE_CHECKING:
        def _enqueue_download(self, model_name: str) -> DownloadOutcome: ...
        def _require_huggingface_consent(self, model_name: str) -> DownloadOutcome | None: ...


    def _download_qwen(self, model_name: str) -> DownloadOutcome:
        """Qwen branch of :meth:`download_model`.

        extracted from the original ``elif model_name == "qwen"``
        branch of the monolithic ``download_model``.  Qwen uses a local
        file path (no HuggingFace call) so the  consent gate does
        not apply.  Returns a :data:`DownloadOutcome` with the same
        runtime shape the original branch produced.
        """
        import os

        from voice_typer.server import event_bus
        from voice_typer.server.service._download_helpers import (
            notify as _notify,
            push_progress as _push_progress,
        )

        log.info("[SERVICE] Download requested for '%s' (Qwen backend)", model_name)
        qwen_path = getattr(self._app.config, "qwen_model_path", None)
        if qwen_path and os.path.isdir(qwen_path):
            _push_progress(event_bus, model_name, 100, "Qwen model already cached")
            return {"success": True, "model": model_name, "message": "Qwen model already cached"}
        _notify(self._app.tray, model_name, APP_NAME, "Qwen model path not configured")
        return {
            "success": False,
            "model": model_name,
            "error": "Qwen model path not configured. Set qwen_model_path in Settings.",
        }

    def _download_parakeet(self, model_name: str) -> DownloadOutcome:
        """Parakeet branch of :meth:`download_model`.

        extracted from the original ``elif model_name ==
        "parakeet"`` branch of the monolithic ``download_model``.
        Handles the  HuggingFace consent gate and the
        structured-error unpack of ``download_parakeet_weights``.
        Returns a :data:`DownloadOutcome` with the same runtime shape
        the original branch produced.
        """
        # SINGLE-FLIGHT GUARD (same rationale as the whisper branch —
        from voice_typer.server.asr_setup import is_download_active

        if is_download_active():
            return self._enqueue_download(model_name)
        from voice_typer.server import event_bus
        from voice_typer.server.service._download_helpers import (
            notify as _notify,
            push_progress as _push_progress,
        )

        # HuggingFace consent gate.  Parakeet weights
        consent_err = self._require_huggingface_consent(model_name)
        if consent_err is not None:
            return consent_err
        log.info(
            "[SERVICE] Download requested for '%s' (Parakeet backend, ~2.5 GB)",
            model_name,
        )
        _push_progress(event_bus, model_name, 0, "Starting Parakeet download (~2.5 GB)...")
        from voice_typer.server.asr_setup import (
            download_parakeet_weights,
            reset_download_pause_state,
        )

        # Parakeet's transfer gate reads the same shared pause/abort
        reset_download_pause_state()

        # The unpack is defensive: some legacy / test fakes
        def _parakeet_progress(message: str) -> None:
            # Map the function's textual progress messages to
            _push_progress(event_bus, model_name, 50, message)

        _push_progress(event_bus, model_name, 50, "Downloading Parakeet weights from HuggingFace...")
        try:
            dpw_result = download_parakeet_weights(
                config=self._app.config,
                progress_callback=_parakeet_progress,
            )
        finally:
            # Release the gate's pause/abort events on EVERY exit —
            from voice_typer.server.asr_setup import clear_download_pause_state

            clear_download_pause_state()
        # Defensive unpack: handle both the documented 3-tuple
        if isinstance(dpw_result, tuple):
            success, reason, _exc_info = dpw_result
        else:
            success = bool(dpw_result)
            reason = "" if success else "unknown"
        if not success:
            msg = _PARAKEET_REASON_MESSAGES.get(reason, f"Download failed: {reason}")
            log.error(
                "[SERVICE] Parakeet download failed (reason=%s): %s",
                reason,
                msg,
            )
            _push_progress(event_bus, model_name, 0, msg)
            _notify(self._app.tray, model_name, APP_NAME, f"Failed to download {model_name}: {msg}")
            return {
                "success": False,
                "error": msg,
                "reason": reason,
                "model": model_name,
            }
        log.info("[SERVICE] Parakeet download complete")
        _push_progress(event_bus, model_name, 100, "Parakeet download complete")
        # invalidate the tray models submenu cache.
        try:
            from voice_typer.server.tray_models import (
                invalidate_model_availability_cache,
            )

            invalidate_model_availability_cache()
        except Exception:
            log.debug(
                "[SERVICE] failed to invalidate tray model cache",
                exc_info=True,
            )
        _notify(self._app.tray, model_name, APP_NAME, "Parakeet model downloaded successfully")
        return {"success": True, "model": model_name}
