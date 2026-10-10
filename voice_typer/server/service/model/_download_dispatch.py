"""download_model dispatcher: backend branches and shared setup."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from voice_typer.server._secrets import redact_secret, redact_url
from voice_typer.server.asr_setup import ModelDownloadAborted
from voice_typer.server.branding import APP_NAME
from voice_typer.server.service._download_helpers import DownloadOutcome

if TYPE_CHECKING:
    from voice_typer.server.app import LausuApp

log = logging.getLogger(__name__)


class DownloadDispatchMixin:

    """download_model dispatcher: backend branches and shared setup.

    Host-state contract: the declarations below are attributes the
    composed ``ModelMixin`` (or a sibling mixin) owns.

    The TYPE_CHECKING stubs name methods the composite provides.
    """

    _app: LausuApp

    if TYPE_CHECKING:
        def _download_parakeet(self, model_name: str) -> DownloadOutcome: ...
        def _download_qwen(self, model_name: str) -> DownloadOutcome: ...
        def _download_whisper_family(self, model_name: str, model_meta) -> DownloadOutcome: ...
        def _start_next_queued_download(self) -> None: ...


    def download_model(self, model_name: str) -> dict[str, object]:
        """Download a model weight file via HuggingFace.

        Downloads the specified model (tiny, large-v3-turbo,
        large-v3, qwen, parakeet) to the local HF cache. Pushes
        ``download_progress`` events to the renderer so the Models page
        can update its progress bar and status text in real time, and
        fires a tray notification on completion / failure.
        Returns a result dict with success status.

        the return annotation is widened from the
        ``DownloadResult`` TypedDict union (removed) to
        ``dict[str, object]`` to match the actual runtime shape. The
        implementation returns plain ``dict`` literals (not TypedDict
        instances); the TypedDict union gave no real protection and
        caused 3 baselined ``bad-return`` pyrefly errors. The runtime
        shape is verified by ``tests/test_service_fixes.py``.

        now supports the turbo + distilled variants via
        :mod:`voice_typer.server.model_registry`.  The repo_id is
        resolved from the registry instead of being hard-coded.

        the polling loop checks
        :func:`asr_setup.is_download_paused` between iterations.  When
        paused, progress updates freeze and a ``paused: True`` event is
        pushed once per transition.  Resume clears the flag and pushes
        a ``resumed: True`` event.

        the Whisper and Parakeet branches now gate on
        :meth:`_require_huggingface_consent` before any HuggingFace
        network call, mirroring the consent gate that already lived in
        ``TranscriptionEngine._pre_download_model`` (transcription.py:835-849).
        The Qwen branch uses a local file path and does not phone home,
        so it is exempt from the consent gate.

        daemon=True is acceptable because _do_download only
        writes to the HF cache dir, no critical cleanup. The download
        completes or fails naturally; on force-kill the partial
        download is resumed on next start via HF's resume_download=True.

        the original 558-LOC god method has been split into a
        ~40-LOC dispatcher (this method) plus three branch methods
        (``_download_whisper_family``, ``_download_qwen``,
        ``_download_parakeet``).  The shared helpers
        (:func:`push_progress`, :func:`notify`,
        :func:`poll_download_progress`) live in
        :mod:`voice_typer.server.service._download_helpers`.  Each
        branch returns a :data:`DownloadOutcome` TypedDict; the
        dispatcher converts it to a plain ``dict`` via ``dict(outcome)``
        so the IPC layer sees the exact same runtime shape as before.
        All 10 distinct return shapes are preserved verbatim.

        The progress-polling loop (delegated to
        :func:`poll_download_progress` in
        :mod:`voice_typer.server.service._download_helpers`) walks
        ONLY the per-repo subdir to keep I/O bounded::

            model_dir = cache_dir / f"models--{repo_id.replace('/', '--')}"
            ... = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())

        (Regression guard, kept as a docstring snippet so the
        ``tests/test_perf_fixes.py::TestDownloadPollScopedToModelDir``
        source-pin still trips if a future refactor re-widens the
        rglob to walk the whole ``cache_dir``.)
        """
        try:
            # consult the model registry so we support
            from voice_typer.server.model_registry import get_model_metadata

            model_meta = get_model_metadata(model_name)
            is_whisper_family = model_meta is not None and model_meta.backend in ("whisper", "distil-whisper")
            if is_whisper_family:
                outcome = self._download_whisper_family(model_name, model_meta)
            elif model_name == "qwen":
                outcome = self._download_qwen(model_name)
            elif model_name == "parakeet":
                outcome = self._download_parakeet(model_name)
            else:
                log.warning(
                    "[SERVICE] Unknown model requested for download: '%s'",
                    model_name,
                )
                return {
                    "success": False,
                    "model": model_name,
                    "error": f"Unknown model: {model_name}",
                }
            return dict(outcome)  # Convert TypedDict to regular dict for IPC
        except ModelDownloadAborted:
            # An abort unwinding the transfer surfaces here as a
            log.info(
                "[SERVICE] Download of '%s' aborted via transfer gate",
                model_name,
            )
            try:
                from voice_typer.server.asr_setup import clear_download_pause_state

                clear_download_pause_state()
            except Exception:
                log.debug("[SERVICE] could not clear pause flag on abort", exc_info=True)
            return {
                "success": False,
                "model": model_name,
                "cancelled": True,
                "message": f"Download of {model_name} cancelled. Partial files remain in cache; retry to resume.",
            }
        except Exception as exc:
            log.exception("download_model failed for %s: %s", model_name, exc)
            # The per-download Event cleanup is handled by the
            try:
                from voice_typer.server.asr_setup import clear_download_pause_state

                clear_download_pause_state()
            except Exception:
                log.debug("[SERVICE] could not clear pause flag on failure", exc_info=True)
            from voice_typer.server import event_bus
            from voice_typer.server.service._download_helpers import (
                notify as _notify_helper,
                push_progress as _push_progress_helper,
            )

            _push_progress_helper(event_bus, model_name, 0, f"Download failed: {redact_secret(redact_url(str(exc)))}")
            _notify_helper(
                self._app.tray,
                model_name,
                APP_NAME,
                f"Failed to download {model_name}: {redact_secret(redact_url(str(exc)))}",
            )
            return {
                "success": False,
                "model": model_name,
                "error": redact_secret(redact_url(str(exc))),
            }
        finally:
            # Queue drain: EVERY exit path (success, failure, cancel,
            try:
                self._start_next_queued_download()
            except Exception:
                log.debug("[SERVICE] download-queue drain failed (non-fatal)", exc_info=True)
