"""Transfer mechanics of the whisper / distil-whisper download branch.

Split out of ``voice_typer.server.service.model._downloads`` (one concern per
file): the facade keeps the orchestration (single-flight guard, consent gate,
pause/resume handoff, per-download cancellation, finalize), this module owns
the two transfer paths a download can take — the classic HuggingFace snapshot
transfer and the segmented fast lane for big pinned files.

Both entries are plain functions taking the values they need (no mixin, no
host state), so each is unit-testable on its own. The closed-over values of
the former ``_do_download`` closure arrive as explicit arguments.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from voice_typer.server import segmented_download as segdl
from voice_typer.server.asr_setup import ModelDownloadAborted, check_download_gate
from voice_typer.server.service._download_helpers import DownloadOutcome

# The facade's namespace on purpose: every line of this flow logged under
# ``voice_typer.server.service.model._downloads`` before the split (C-LOG-1).
log = logging.getLogger("voice_typer.server.service.model._downloads")


def run_classic_transfer(
    *,
    snapshot_download: Any,
    repo_id: str,
    revision: str,
    allow_patterns: Any,
    ignore_patterns: list[str] | None,
    tqdm_class: Any,
    errors: list[Any],
) -> None:
    """Run the classic snapshot transfer, capturing the failure for the caller.

    ``errors`` is the caller's list: a raised ``BaseException`` (which includes
    ``ModelDownloadAborted``) is appended instead of propagating, so the
    orchestrating thread keeps ownership of the cancel/abort decision.
    """
    try:
        # use retry-with-backoff wrapper
        from voice_typer.server.transcription import _download_with_retry

        _download_with_retry(
            snapshot_download,
            repo_id=repo_id,
            revision=revision,
            allow_patterns=allow_patterns,
            # Segmented fast lane owns the big files —
            ignore_patterns=ignore_patterns,
            resume_download=True,
            # pause/abort gate: intercepts every ~10 MB
            tqdm_class=tqdm_class,
        )
    except BaseException as e:
        # ModelDownloadAborted is a BaseException, catch
        errors.append(e)


def run_segmented_fast_lane(
    *,
    seg_plan: Any,
    repo_id: str,
    revision: str,
    cache_dir: Path,
    snapshot_download: Any,
    allow_patterns: list[str],
    event_bus: Any,
    model_name: str,
    target_mb: int,
    target_bytes: int,
) -> DownloadOutcome | None:
    """Download the big pinned files concurrently, then self-verify the snapshot.

    Returns the cancelled outcome when the transfer gate aborted the lane
    (the caller returns it verbatim); ``None`` means the lane finished and the
    caller continues with the finalize path.
    """
    from voice_typer.server.asr_setup import clear_download_pause_state, get_download_tqdm_class
    from voice_typer.server.service._download_helpers import push_progress as _push_progress

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
            commit=revision,
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
            revision=revision,
            allow_patterns=allow_patterns,
            resume_download=True,
            tqdm_class=get_download_tqdm_class(),
        )
    # Self-verify the assembled snapshot by HF's own
    try:
        snapshot_download(
            repo_id=repo_id,
            revision=revision,
            allow_patterns=allow_patterns,
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
            revision=revision,
            allow_patterns=allow_patterns,
            resume_download=True,
            tqdm_class=get_download_tqdm_class(),
        )
    return None
