"""ADR-0030 translation-model download branch of ``download_model``.

The translator lives outside MODEL_REGISTRY, so it cannot use the ASR
engine-family downloaders. It reuses the same IPC command, consent gate,
single-flight guard, progress polling, scoped cancel and integrity check;
the artifact goes to the shared HF hub cache via
:mod:`voice_typer.server.translation.download`.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from voice_typer.server.branding import APP_NAME
from voice_typer.server.service._download_helpers import DownloadOutcome

if TYPE_CHECKING:
    from voice_typer.server.app import LausuApp

_DISK_FULL_MESSAGE = "Not enough disk space to download the translation model (1.31 GB). Free up space and try again."


class TranslationDownloadMixin:
    _app: LausuApp

    if TYPE_CHECKING:

        def _enqueue_download(self, model_name: str) -> DownloadOutcome: ...
        def _require_huggingface_consent(self, model_name: str) -> DownloadOutcome | None: ...
        def _register_download(self, model_name: str) -> str: ...
        def _unregister_download(self, download_id: str) -> None: ...
        def _is_download_cancelled(self, download_id: str) -> bool: ...
        def _invalidate_model_status_cache(self) -> None: ...

    def _download_translation(self, model_name: str) -> DownloadOutcome:
        """Download Index-Translate Q4_K_M through the shared transfer gate."""
        from voice_typer.server import event_bus, i18n
        from voice_typer.server.asr_setup import (
            ModelDownloadAborted,
            get_download_tqdm_class,
            is_download_active,
            request_download_abort,
            reset_download_pause_state,
        )
        from voice_typer.server.model_availability import shared_hub_dir
        from voice_typer.server.service import _download_helpers as helpers
        from voice_typer.server.service.model._download_dispatch import (
            _GGUF_REASON_MESSAGES,
            _cancelled_outcome,
            _clear_pause_state,
            _friendly_download_error,
        )
        from voice_typer.server.translation.catalogue import resolve_spec
        from voice_typer.server.translation.download import (
            check_translation_disk_space,
            download_translation_weights,
        )

        spec = resolve_spec(model_name)

        # A translation transfer shares the single-flight gate with ASR
        # downloads. queueing by name would enqueue an id no ASR downloader
        # recognises, so refuse with the same "already active" shape instead.
        if is_download_active():
            return {
                "success": False,
                "model": model_name,
                "error": "Another model download is already in progress.",
                "download_already_active": True,
            }

        consent_err = self._require_huggingface_consent(model_name)
        if consent_err is not None:
            return consent_err

        try:
            check_translation_disk_space(spec)
        except RuntimeError:
            helpers.push_progress(event_bus, model_name, 0, _DISK_FULL_MESSAGE)
            helpers.notify(self._app.tray, model_name, APP_NAME, _DISK_FULL_MESSAGE)
            return {
                "success": False,
                "model": model_name,
                "error": _DISK_FULL_MESSAGE,
                "reason": "disk_space_insufficient",
                "code": "translation_disk_space_insufficient",
            }

        reset_download_pause_state()
        helpers.push_progress(event_bus, model_name, 0, f"Starting {spec.label} download...")
        download_id = self._register_download(model_name)
        errors: list[BaseException] = []
        verdicts: list[tuple[bool, str, object]] = []

        def transfer() -> None:
            try:
                try:
                    tqdm_class = get_download_tqdm_class()
                except ImportError:
                    tqdm_class = None
                verdicts.append(
                    download_translation_weights(
                        spec,
                        config=getattr(self._app, "config", None),
                        tqdm_class=tqdm_class,
                    )
                )
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=transfer, daemon=True, name=f"translation-download-{model_name}")
        thread.start()
        try:
            poll_outcome, _bytes_seen = helpers.poll_download_progress(
                thread=thread,
                target_bytes=spec.size_bytes,
                target_mb=max(1, spec.size_bytes // (1024 * 1024)),
                model_name=model_name,
                repo_id=spec.repo_id,
                cache_dir=shared_hub_dir(),
                download_id=download_id,
                event_bus=event_bus,
                is_cancelled_fn=self._is_download_cancelled,
            )
        finally:
            self._unregister_download(download_id)
        thread.join(timeout=helpers.DOWNLOAD_ABORT_JOIN_S)

        if errors:
            error = errors[0]
            _clear_pause_state()
            if isinstance(error, ModelDownloadAborted):
                return _cancelled_outcome(model_name)
            message = _friendly_download_error(error)
            helpers.push_progress(event_bus, model_name, 0, message)
            helpers.notify(self._app.tray, model_name, APP_NAME, message)
            return {
                "success": False,
                "model": model_name,
                "error": message,
                "reason": "download_failed",
                "code": "translation_download_failed",
            }
        if poll_outcome == "cancelled":
            request_download_abort()
            thread.join(timeout=helpers.DOWNLOAD_ABORT_JOIN_S)
            _clear_pause_state()
            return _cancelled_outcome(model_name)

        ok, reason, exc_info = verdicts[0] if verdicts else (False, "download_failed", None)
        if not ok:
            _clear_pause_state()
            if reason == "huggingface_consent_false":
                return self._require_huggingface_consent(model_name) or {
                    "success": False,
                    "error": "HuggingFace consent required",
                    "consent_required": True,
                    "model": model_name,
                }
            if reason == "huggingface_hub_missing":
                message = "huggingface_hub is not installed. Install it and try again."
            elif reason in _GGUF_REASON_MESSAGES:
                message = _GGUF_REASON_MESSAGES[reason]
            elif exc_info is not None:
                message = _friendly_download_error(exc_info[1])
            else:
                message = f"Translation model download failed: {reason}"
            helpers.push_progress(event_bus, model_name, 0, message)
            helpers.notify(self._app.tray, model_name, APP_NAME, message)
            return {
                "success": False,
                "model": model_name,
                "error": message,
                "reason": reason,
                "code": f"translation_{reason}",
            }

        _clear_pause_state()
        helpers.push_progress(event_bus, model_name, 100, "Translation model download complete")
        helpers.notify(self._app.tray, model_name, APP_NAME, i18n.t("notify.model.translation_downloaded"))
        self._invalidate_model_status_cache()
        try:
            from voice_typer.server.tray_models import invalidate_model_availability_cache

            invalidate_model_availability_cache()
        except Exception:
            # Tray cache refresh is cosmetic; the download itself succeeded.
            pass
        return {"success": True, "model": model_name}
