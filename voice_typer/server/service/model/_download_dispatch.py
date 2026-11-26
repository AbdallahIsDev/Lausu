"""download_model dispatcher: consent, queue and the GGUF transfer path."""

from __future__ import annotations

import importlib
import logging
import threading
from typing import TYPE_CHECKING

from voice_typer.server._secrets import redact_secret, redact_url
from voice_typer.server.asr_setup import ModelDownloadAborted
from voice_typer.server.branding import APP_NAME
from voice_typer.server.service._download_helpers import (
    DOWNLOAD_ABORT_JOIN_S,
    DownloadOutcome,
)

if TYPE_CHECKING:
    from voice_typer.server.app import LausuApp

log = logging.getLogger(__name__)

_NETWORK_DOWN_MESSAGE = "Could not reach HuggingFace. Check your internet connection and try again."
_STALLED_DOWNLOAD_MESSAGE = (
    "The download stalled. Check your connection and try again; already-downloaded files are kept."
)
_DISK_FULL_MESSAGE = "Not enough disk space to finish the download. Free up space and try again."

_NETWORK_ERROR_MARKERS = (
    "getaddrinfo failed",
    "name or service not known",
    "temporary failure in name resolution",
    "network is unreachable",
    "connection refused",
    "connection reset",
    # httpx's shared client reports the closed client, never the real cause.
    "client has been closed",
    "cannot send a request",
)
_STALLED_ERROR_MARKERS = ("timed out", "timeout", "stalled", "no progress for")
_DISK_FULL_ERROR_MARKERS = ("no space left", "not enough space", "winerror 112")
# httpx2/httpcore2 are the huggingface-hub 2.x stack; httpx/httpcore the 1.x one.
_TRANSPORT_MODULES = ("httpx2", "httpcore2", "httpx", "httpcore")
# ConnectTimeout is listed explicitly: httpx 1.x makes it a ConnectError
# subclass, httpx 2.x does not, and a connect timeout is a network outage.
_TRANSPORT_ERROR_NAMES = ("ConnectError", "ConnectTimeout")

_GGUF_REASON_MESSAGES = {
    "placeholder_in_registry": "This model's download details are incomplete. Select another model.",
    "size_mismatch": "The downloaded model file has an unexpected size. Retry the download.",
    "sha256_mismatch": "The downloaded model file failed verification. Retry the download.",
    "dev_model_not_allowed": "This model is not available in this build.",
    "model_not_allowed": "This model is not available in this build.",
}


def _exception_chain(exc: BaseException) -> list[BaseException]:
    """Return *exc* plus its ``__cause__``/``__context__`` chain, cycle-safe."""
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def _transport_error_types() -> tuple[type[BaseException], ...]:
    """Return the connect-error classes of every installed HTTP stack.

    Both generations are resolved by name so classification keeps working
    whichever one the environment provides.
    """
    found: list[type[BaseException]] = []
    for module_name in _TRANSPORT_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for error_name in _TRANSPORT_ERROR_NAMES:
            error_type = getattr(module, error_name, None)
            if error_type is not None:
                found.append(error_type)
    return tuple(found)


def _friendly_download_error(exc: BaseException) -> str:
    """Map known transport failures to short actionable text; redact the rest."""
    chain = _exception_chain(exc)
    transport_types = _transport_error_types()
    if transport_types and any(isinstance(err, transport_types) for err in chain):
        return _NETWORK_DOWN_MESSAGE
    texts = [str(err).lower() for err in chain]
    if any(marker in text for text in texts for marker in _NETWORK_ERROR_MARKERS):
        return _NETWORK_DOWN_MESSAGE
    if any(marker in text for text in texts for marker in _STALLED_ERROR_MARKERS):
        return _STALLED_DOWNLOAD_MESSAGE
    if any(marker in text for text in texts for marker in _DISK_FULL_ERROR_MARKERS):
        return _DISK_FULL_MESSAGE
    return redact_secret(redact_url(str(exc)))


def _clear_pause_state() -> None:
    """Release the module-level pause/abort gate on every exit path."""
    try:
        from voice_typer.server.asr_setup import clear_download_pause_state

        clear_download_pause_state()
    except Exception:
        log.debug("[SERVICE] could not clear pause state", exc_info=True)


def _cancelled_outcome(model_name: str) -> DownloadOutcome:
    """Cancel keeps HF's resumable partial; the retry resumes from it."""
    return {
        "success": False,
        "model": model_name,
        "cancelled": True,
        "message": f"Download of {model_name} cancelled. Partial files remain in cache; retry to resume.",
    }


class DownloadDispatchMixin:

    """Download dispatch: consent, single-flight and the verified GGUF path."""

    _app: LausuApp

    if TYPE_CHECKING:
        def _download_translation(self, model_name: str) -> DownloadOutcome: ...
        def _download_gguf(self, model_name: str) -> DownloadOutcome: ...
        def _enqueue_download(self, model_name: str) -> DownloadOutcome: ...
        def _require_huggingface_consent(self, model_name: str) -> DownloadOutcome | None: ...
        def _register_download(self, model_name: str) -> str: ...
        def _unregister_download(self, download_id: str) -> None: ...
        def _is_download_cancelled(self, download_id: str) -> bool: ...
        def _start_next_queued_download(self) -> None: ...
        def _invalidate_model_status_cache(self) -> None: ...

    def _gguf_failure_outcome(self, model_name: str, reason: str) -> DownloadOutcome:
        """Translate a verifier/downloader failure code into the IPC shape."""
        from voice_typer.server import event_bus
        from voice_typer.server.service import _download_helpers as _helpers

        if reason == "huggingface_consent_false":
            return self._require_huggingface_consent(model_name) or {
                "success": False,
                "error": "HuggingFace consent required",
                "consent_required": True,
                "model": model_name,
            }
        if reason == "huggingface_hub_missing":
            from voice_typer.server.service.model._constants import _PARAKEET_REASON_MESSAGES

            message = _PARAKEET_REASON_MESSAGES["huggingface_hub_missing"]
            _helpers.push_progress(event_bus, model_name, 0, message)
            _helpers.notify(self._app.tray, model_name, APP_NAME, f"Failed to download {model_name}: {message}")
            return {
                "success": False,
                "model": model_name,
                "error": message,
                "reason": reason,
                "code": reason,
            }
        message = _GGUF_REASON_MESSAGES.get(reason, f"Download failed: {reason}")
        log.error("[SERVICE] GGUF download of '%s' failed (%s)", model_name, reason)
        _helpers.push_progress(event_bus, model_name, 0, message)
        _helpers.notify(self._app.tray, model_name, APP_NAME, f"Failed to download {model_name}: {message}")
        return {
            "success": False,
            "model": model_name,
            "error": message,
            "reason": reason,
            "code": reason,
        }

    def _download_gguf(self, model_name: str) -> DownloadOutcome:
        """One GGUF transfer, with consent, progress polling and scoped cancel."""
        from voice_typer.server import event_bus
        from voice_typer.server.asr_setup import (
            get_download_tqdm_class,
            is_download_active,
            request_download_abort,
            reset_download_pause_state,
        )
        from voice_typer.server.gguf_download import download_gguf_model
        from voice_typer.server.gguf_model_registry import resolve_gguf_spec
        from voice_typer.server.model_availability import shared_hub_dir
        from voice_typer.server.service import _download_helpers as _helpers

        if is_download_active():
            return self._enqueue_download(model_name)
        consent_err = self._require_huggingface_consent(model_name)
        if consent_err is not None:
            return consent_err

        spec = resolve_gguf_spec(model_name)
        target_mb = max(1, spec.size_bytes // (1024 * 1024))
        reset_download_pause_state()
        _helpers.push_progress(event_bus, model_name, 0, f"Starting download for {model_name}...")
        download_id = self._register_download(model_name)
        errors: list[BaseException] = []
        verdicts: list[tuple[bool, str]] = []

        def transfer() -> None:
            try:
                try:
                    tqdm_class = get_download_tqdm_class()
                except ImportError:
                    # A missing hub is reported by the downloader itself as
                    # huggingface_hub_missing, not as an opaque import error.
                    tqdm_class = None
                verdicts.append(
                    download_gguf_model(
                        model_name,
                        config=getattr(self._app, "config", None),
                        tqdm_class=tqdm_class,
                    )
                )
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=transfer, daemon=True, name=f"gguf-download-{model_name}")
        thread.start()
        try:
            poll_outcome, _bytes_seen = _helpers.poll_download_progress(
                thread=thread,
                target_bytes=spec.size_bytes,
                target_mb=target_mb,
                model_name=model_name,
                repo_id=spec.repo_id,
                cache_dir=shared_hub_dir(),
                download_id=download_id,
                event_bus=event_bus,
                is_cancelled_fn=self._is_download_cancelled,
            )
        finally:
            self._unregister_download(download_id)
        thread.join(timeout=DOWNLOAD_ABORT_JOIN_S)
        if errors:
            error = errors[0]
            if isinstance(error, ModelDownloadAborted):
                _clear_pause_state()
                return _cancelled_outcome(model_name)
            raise error
        if poll_outcome == "cancelled":
            request_download_abort()
            thread.join(timeout=DOWNLOAD_ABORT_JOIN_S)
            _clear_pause_state()
            return _cancelled_outcome(model_name)
        ok, reason = verdicts[0] if verdicts else (False, "download_failed")
        if not ok:
            _clear_pause_state()
            return self._gguf_failure_outcome(model_name, reason)

        _clear_pause_state()
        _helpers.push_progress(event_bus, model_name, 100, f"Download of {model_name} complete")
        try:
            from voice_typer.server.tray_models import invalidate_model_availability_cache

            invalidate_model_availability_cache()
        except Exception:
            log.debug("[SERVICE] failed to invalidate tray model cache", exc_info=True)
        _helpers.notify(self._app.tray, model_name, APP_NAME, f"Model '{model_name}' downloaded successfully")
        self._invalidate_model_status_cache()
        return {"success": True, "model": model_name}

    def download_model(self, model_name: str) -> dict[str, object]:
        """Download one verified GGUF ASR model (or the text-translation model).

        Consent, single-flight queueing, progress events and scoped cancellation
        are shared across every model; the transfer itself belongs to
        :meth:`_download_gguf`. The frozen gate runs before any consent check,
        cache probe or network call.
        """
        try:
            from voice_typer.server.translation.catalogue import TRANSLATION_MODEL_ID

            if model_name == TRANSLATION_MODEL_ID:
                return dict(self._download_translation(model_name))

            from voice_typer.server.gguf_model_registry import (
                is_dev_only_model_key,
                is_frozen,
                is_registered_model_key,
                production_models,
            )

            if is_frozen() and model_name not in production_models():
                from voice_typer.server.ipc.error_codes import ErrorCodes

                dev_only = is_dev_only_model_key(model_name)
                reason = "dev_model_not_allowed" if dev_only else "model_not_allowed"
                code_value = ErrorCodes.DEV_MODEL_NOT_ALLOWED if dev_only else ErrorCodes.NOT_SUPPORTED
                log.warning("[SERVICE] Refused %s in frozen build: %s", model_name, reason)
                return {
                    "success": False,
                    "model": model_name,
                    "code": code_value,
                    "error": reason,
                }
            if not is_registered_model_key(model_name):
                from voice_typer.server.ipc.error_codes import ErrorCodes

                log.warning("[SERVICE] Unknown model requested for download: '%s'", model_name)
                return {
                    "success": False,
                    "model": model_name,
                    "error": f"Unknown model: {model_name}",
                    "code": ErrorCodes.NOT_SUPPORTED,
                }
            return dict(self._download_gguf(model_name))
        except ModelDownloadAborted:
            log.info("[SERVICE] Download of '%s' aborted via transfer gate", model_name)
            _clear_pause_state()
            return dict(_cancelled_outcome(model_name))
        except Exception as exc:
            log.exception("download_model failed for %s: %s", model_name, exc)
            friendly = _friendly_download_error(exc)
            _clear_pause_state()
            from voice_typer.server import event_bus
            from voice_typer.server.service import _download_helpers as _helpers

            _helpers.push_progress(event_bus, model_name, 0, f"Download failed: {friendly}")
            _helpers.notify(
                self._app.tray,
                model_name,
                APP_NAME,
                f"Failed to download {model_name}: {friendly}",
            )
            return {
                "success": False,
                "model": model_name,
                "error": friendly,
            }
        finally:
            # Every exit (success, failure, consent, cancel) advances the queue.
            try:
                self._start_next_queued_download()
            except Exception:
                log.debug("[SERVICE] download-queue drain failed (non-fatal)", exc_info=True)
