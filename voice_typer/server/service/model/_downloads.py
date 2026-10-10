"""Consent gate, download dispatch, engine-family downloaders."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from voice_typer.server import segmented_download as segdl
from voice_typer.server.asr_setup import ModelDownloadAborted, check_download_gate
from voice_typer.server.branding import APP_NAME
from voice_typer.server.service._download_helpers import DownloadOutcome

from ._constants import _PARAKEET_REASON_MESSAGES
from ._download_dispatch import DownloadDispatchMixin
from ._download_preflight import DownloadPreflightMixin
from ._download_queue import DownloadQueueMixin
from ._download_qwen_parakeet import QwenParakeetDownloadMixin

if TYPE_CHECKING:
    from voice_typer.server.app import LausuApp

log = logging.getLogger(__name__)


class DownloadsMixin(DownloadPreflightMixin, DownloadQueueMixin, DownloadDispatchMixin, QwenParakeetDownloadMixin):
    """Download surface of ``ModelMixin``: preflight, queue, dispatch, backends.

    The four concerns live in the sibling mixins composed here; this module
    keeps ``_download_whisper_family`` because source-text regression pins
    read this file.
    """
    # Members provided by the composed ``ModelMixin`` (mixin.py);
    _download_queue: list[str]
    _app: LausuApp
    _is_download_cancelled: Any
    _register_download: Any

    if TYPE_CHECKING:
        # Methods provided by sibling mixins at runtime.
        def _invalidate_model_status_cache(self) -> None: ...

        def _unregister_download(self, download_id: str) -> None: ...

        def _enqueue_download(self, model_name: str) -> DownloadOutcome: ...

        def _require_huggingface_consent(self, model_name: str) -> DownloadOutcome | None: ...


    def _download_whisper_family(self, model_name: str, model_meta) -> DownloadOutcome:
        """Whisper / distil-whisper branch of :meth:`download_model`.

        extracted from the original ``is_whisper_family`` branch
        of the monolithic ``download_model``.  Handles the
        HuggingFace consent gate, the  pause/resume state
        machine (via :func:`poll_download_progress` in Phase A and
        :func:`make_segmented_progress_tracker` in Phase B, with the
        shared pause/abort events kept alive across the handoff),
        and the per-download cancellation plumbing.

        Takes explicit args (``model_name``, ``model_meta``) so it can
        be unit-tested in isolation. Returns a :data:`DownloadOutcome`
        TypedDict with the same runtime shape the original branch
        produced.
        """
        # SINGLE-FLIGHT GUARD: only one gateable download may run at a
        from voice_typer.server.asr_setup import is_download_active

        if is_download_active():
            return self._enqueue_download(model_name)
        from voice_typer.server import event_bus
        from voice_typer.server.service._download_helpers import (
            notify as _notify,
            poll_download_progress,
            push_progress as _push_progress,
        )

        # HuggingFace consent gate.  Without this check,
        consent_err = self._require_huggingface_consent(model_name)
        if consent_err is not None:
            return consent_err
        log.info(
            "[SERVICE] Starting download for '%s' (repo=%s, backend=%s)",
            model_name,
            model_meta.repo_id if model_meta else "unknown",
            model_meta.backend if model_meta else "unknown",
        )
        # reset the pause + abort flags at the start of
        from voice_typer.server.asr_setup import (
            clear_download_pause_state,
            force_http_download_path,
            get_download_tqdm_class,
            reset_download_pause_state,
        )

        reset_download_pause_state()
        force_http_download_path()

        _push_progress(event_bus, model_name, 0, f"Starting download for {model_name}...")
        # pre-download via snapshot_download so we can
        download_id: str | None = None
        try:
            from huggingface_hub import snapshot_download

            from voice_typer.server import model_availability as _ma
            from voice_typer.server.config import _config_dir

            # use the registry's repo_id so
            assert model_meta is not None  # narrowed by is_whisper_family
            repo_id = model_meta.repo_id
            cache_dir = _ma.shared_hub_dir()

            # SEC-audit-005: Allowlist of file patterns permitted in downloads
            from voice_typer.server._model_integrity import (
                ALLOW_PATTERNS_WHISPER as SERVICE_ALLOW_PATTERNS_WHISPER,
            )
            from voice_typer.server.security import MODEL_HASHES

            _service_revision = MODEL_HASHES.get(repo_id, {}).get("revision", "main")

            _push_progress(event_bus, model_name, 5, f"Checking cache for {model_name}...")
            # Try local-only first; if cached, skip the polling.
            try:
                try:
                    snapshot_download(
                        repo_id=repo_id,
                        revision=_service_revision,
                        allow_patterns=SERVICE_ALLOW_PATTERNS_WHISPER,
                        local_files_only=True,
                    )
                except Exception:
                    snapshot_download(
                        repo_id=repo_id,
                        revision=_service_revision,
                        allow_patterns=SERVICE_ALLOW_PATTERNS_WHISPER,
                        local_files_only=True,
                        cache_dir=str(_ma.app_hub_dir(_config_dir())),
                    )
                log.info(
                    "[SERVICE] Model '%s' already cached (repo=%s), skipping download",
                    model_name,
                    repo_id,
                )
                # Status-only event at a NON-terminal percent: the single
                _push_progress(event_bus, model_name, 5, f"{model_name} already cached")
            except Exception:
                # pull target size from the
                target_mb = model_meta.download_size_mb if model_meta.download_size_mb else 500
                target_bytes = target_mb * 1024 * 1024
                # Segmented fast lane: big, pinned files download as
                from voice_typer.server.security import MODEL_HASHES as _MH

                seg_plan = segdl.plan_segmented_files(
                    repo_id=repo_id,
                    revision=_service_revision,
                    allow_patterns=SERVICE_ALLOW_PATTERNS_WHISPER,
                    file_hashes=(_MH.get(repo_id, {}) or {}).get("files", {}),
                )
                seg_names = [p.filename for p in seg_plan] if seg_plan else []
                _push_progress(
                    event_bus,
                    model_name,
                    10,
                    f"Downloading {model_name} from HuggingFace...",
                    total_bytes=target_bytes,
                )
                # Start the download in a thread so we can poll
                import threading

                # Register a per-download
                download_id = self._register_download(model_name)
                download_err: list = []

                def _do_download():
                    try:
                        # use retry-with-backoff wrapper
                        from voice_typer.server.transcription import _download_with_retry

                        _download_with_retry(
                            snapshot_download,
                            repo_id=repo_id,
                            revision=_service_revision,
                            allow_patterns=SERVICE_ALLOW_PATTERNS_WHISPER,
                            # Segmented fast lane owns the big files —
                            ignore_patterns=seg_names or None,
                            resume_download=True,
                            # pause/abort gate: intercepts every ~10 MB
                            tqdm_class=get_download_tqdm_class(),
                        )
                    except BaseException as e:
                        # ModelDownloadAborted is a BaseException, catch
                        download_err.append(e)

                # daemon=True is acceptable because
                t = threading.Thread(target=_do_download, daemon=True)
                t.start()
                log.info(
                    "[SERVICE] Download thread started for '%s' (target=%d MB)",
                    model_name,
                    target_mb,
                )
                # Poll cache size until download thread exits OR
                try:
                    poll_outcome, last_total_bytes_seen = poll_download_progress(
                        thread=t,
                        target_bytes=target_bytes,
                        target_mb=target_mb,
                        model_name=model_name,
                        repo_id=repo_id,
                        cache_dir=cache_dir,
                        download_id=download_id,
                        event_bus=event_bus,
                        is_cancelled_fn=self._is_download_cancelled,
                    )
                finally:
                    # Remove our per-download Event
                    self._unregister_download(download_id)
                # if cancelled, return early.
                if poll_outcome == "cancelled":
                    clear_download_pause_state()
                    return {
                        "success": False,
                        "model": model_name,
                        "cancelled": True,
                        "message": f"Download of {model_name} cancelled. "
                        "Partial files remain in cache; "
                        "retry to resume.",
                    }
                if download_err:
                    # B904: suppress context from the failed
                    first_err = download_err[0]
                    if isinstance(first_err, ModelDownloadAborted):
                        # The user cancelled: the transfer gate unwound the
                        log.info(
                            "[SERVICE] Download of '%s' aborted via transfer gate",
                            model_name,
                        )
                        clear_download_pause_state()
                        return {
                            "success": False,
                            "model": model_name,
                            "cancelled": True,
                            "message": f"Download of {model_name} cancelled. "
                            "Partial files remain in cache; "
                            "retry to resume.",
                        }
                    raise download_err[0] from None
                # Phase B, segmented fast lane for the big files (runs on
                if seg_plan:
                    try:
                        from voice_typer.server.asr_setup import (
                            is_download_paused as _seg_is_paused,
                        )
                        from voice_typer.server.service._download_helpers import (
                            make_segmented_progress_tracker as _make_seg_tracker,
                        )

                        try:
                            from huggingface_hub.utils import get_token as _get_token

                            _token = _get_token()
                        except Exception:
                            _token = None
                        _headers = {"Authorization": f"Bearer {_token}"} if _token else {}
                        try:
                            from voice_typer.server.service.offline_pack import (
                                proxy_env as _proxy_env,
                            )

                            _proxies = _proxy_env()
                        except Exception:
                            _proxies = None

                        _big_total = sum(p.size for p in seg_plan)
                        # Pause-aware progress tracker (owns the
                        _on_seg_progress = _make_seg_tracker(
                            event_bus=event_bus,
                            model_name=model_name,
                            target_mb=target_mb,
                            target_bytes=target_bytes,
                            phase_total_bytes=_big_total,
                            is_paused_fn=_seg_is_paused,
                        )

                        segdl.run_segmented_phase(
                            model_name=model_name,
                            repo_id=repo_id,
                            commit=_service_revision,
                            cache_dir=cache_dir,
                            seg_plan=seg_plan,
                            progress_cb=_on_seg_progress,
                            gate_check=check_download_gate,
                            headers=_headers,
                            proxies=_proxies,
                        )
                    except ModelDownloadAborted:
                        log.info(
                            "[SERVICE] Download of '%s' aborted via transfer gate",
                            model_name,
                        )
                        clear_download_pause_state()
                        return {
                            "success": False,
                            "model": model_name,
                            "cancelled": True,
                            "message": f"Download of {model_name} cancelled. "
                            "Partial files remain in cache; "
                            "retry to resume.",
                        }
                    except segdl.SegmentedDownloadError as e:
                        # Failover, not failure: anything the segmented
                        log.warning(
                            "[SERVICE] Segmented fast lane failed for '%s' (%s), falling back to classic download",
                            model_name,
                            e,
                        )
                        _push_progress(
                            event_bus,
                            model_name,
                            10,
                            f"Retrying {model_name} with standard download...",
                            total_bytes=target_bytes,
                        )
                        from voice_typer.server.transcription import (
                            _download_with_retry as _retry_classic,
                        )

                        _retry_classic(
                            snapshot_download,
                            repo_id=repo_id,
                            revision=_service_revision,
                            allow_patterns=SERVICE_ALLOW_PATTERNS_WHISPER,
                            resume_download=True,
                            tqdm_class=get_download_tqdm_class(),
                        )
                    # Self-verify the assembled snapshot by HF's own
                    try:
                        snapshot_download(
                            repo_id=repo_id,
                            revision=_service_revision,
                            allow_patterns=SERVICE_ALLOW_PATTERNS_WHISPER,
                            local_files_only=True,
                        )
                    except Exception as e:
                        log.warning(
                            "[SERVICE] Post-segmented snapshot probe failed "
                            "for '%s' (%s), falling back to classic download",
                            model_name,
                            e,
                        )
                        from voice_typer.server.transcription import (
                            _download_with_retry as _retry_verify,
                        )

                        _retry_verify(
                            snapshot_download,
                            repo_id=repo_id,
                            revision=_service_revision,
                            allow_patterns=SERVICE_ALLOW_PATTERNS_WHISPER,
                            resume_download=True,
                            tqdm_class=get_download_tqdm_class(),
                        )
                log.info(
                    "[SERVICE] Download of '%s' complete (%d MB)",
                    model_name,
                    last_total_bytes_seen // (1024 * 1024),
                )
        except ImportError:
            # huggingface_hub is missing or broken (stripped venv /
            if download_id is not None:
                self._unregister_download(download_id)
            clear_download_pause_state()
            msg = _PARAKEET_REASON_MESSAGES["huggingface_hub_missing"]
            log.exception("[SERVICE] Download of '%s' failed: %s", model_name, msg)
            _push_progress(event_bus, model_name, 0, msg)
            _notify(self._app.tray, model_name, APP_NAME, f"Failed to download {model_name}: {msg}")
            return {
                "success": False,
                "error": msg,
                "reason": "huggingface_hub_missing",
                "model": model_name,
            }

        # VERIFY-LIGHT: skip the expensive full-model load verification.
        log.info("[SERVICE] Download of '%s' verified via HF cache (no full model load)", model_name)
        # Single terminal 100% push per download call: the cache-hit
        _push_progress(event_bus, model_name, 100, f"Download of {model_name} complete")
        # invalidate the tray models submenu cache
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
        # Defense-in-depth cleanup. The ``finally:`` block inside the
        if download_id is not None:
            self._unregister_download(download_id)
        # clear the pause flag so subsequent
        clear_download_pause_state()
        _notify(self._app.tray, model_name, APP_NAME, f"Model '{model_name}' downloaded successfully")
        # On-disk model state changed, force the next status recompute.
        self._invalidate_model_status_cache()
        return {"success": True, "model": model_name}
