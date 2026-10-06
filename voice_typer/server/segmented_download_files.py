"""Repo-file planning and HF cache installation for the segmented downloader.

Decides which repo files take the segmented path (threshold + manifest pin
== tree blob_id), runs the sequential per-file phase with aggregate
progress, and installs a verified file into the HuggingFace hub cache
layout (blob + snapshot symlink, copy fallback without symlink privilege).
Moved verbatim out of ``voice_typer.server.segmented_download`` (which
re-exports every name).
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.branding import APP_NAME
from voice_typer.server.segmented_download_base import (
    SEGMENT_THRESHOLD_BYTES,
    GateCheck,
    SegmentedDownloadError,
)
from voice_typer.server.segmented_download_http import build_opener, resolve_download
from voice_typer.server.segmented_download_state import _resolve_within

# Lazy proxy: the facade imports this module, so a direct import of the
# orchestrator it re-exports would be circular.
_dl = lazy_module("voice_typer.server.segmented_download")

log = logging.getLogger("voice_typer.server.segmented_download")


@dataclass(frozen=True)
class PlannedFile:
    """One repo file routed to the segmented engine."""

    filename: str  # repo-relative path
    size: int
    blob_id: str
    sha256: str  # manifest pin (== blob_id for LFS files)


def _matches_any_pattern(path: str, patterns: Any) -> bool:
    import fnmatch

    if patterns is None:
        return True
    if isinstance(patterns, str):
        patterns = [patterns]
    return any(fnmatch.fnmatchcase(path, pat) for pat in patterns)


def _default_list_files(repo_id: str, revision: str) -> list[tuple[str, int | None, str | None]]:
    """List (path, size, blob_id) via the Hub API (one metadata call)."""
    from huggingface_hub import HfApi

    out: list[tuple[str, int | None, str | None]] = []
    for entry in HfApi().list_repo_tree(repo_id, revision=revision, recursive=True):
        path = getattr(entry, "path", None)
        if path is None:
            continue
        out.append((path, getattr(entry, "size", None), getattr(entry, "blob_id", None)))
    return out


def plan_segmented_files(
    *,
    repo_id: str,
    revision: str,
    allow_patterns: Any,
    file_hashes: Any,
    threshold_bytes: int = SEGMENT_THRESHOLD_BYTES,
    list_files: Callable[[], list[tuple[str, int | None, str | None]]] | None = None,
) -> list[PlannedFile] | None:
    """Decide which repo files take the segmented path.

    Returns the list of big, pinned files (empty list = everything is
    """
    try:
        entries = list_files() if list_files is not None else _default_list_files(repo_id, revision)
        planned: list[PlannedFile] = []
        for path, size, blob_id in entries:
            if not _matches_any_pattern(path, allow_patterns):
                continue
            if size is None or size < threshold_bytes:
                continue
            pin = file_hashes.get(path) if isinstance(file_hashes, dict) else None
            if not pin or not blob_id:
                continue
            if str(pin).lower() != str(blob_id).lower():
                log.warning(
                    "[SEGDL] manifest pin != tree blob_id for %s:%s (drift?), classic path",
                    repo_id,
                    path,
                )
                continue
            planned.append(PlannedFile(filename=path, size=size, blob_id=blob_id, sha256=str(pin).lower()))
        return planned
    except Exception:
        log.debug(
            "[SEGDL] file planning failed for %s, classic path",
            repo_id,
            exc_info=True,
        )
        return None


def run_segmented_phase(
    *,
    model_name: str,
    repo_id: str,
    commit: str,
    cache_dir: str | Path,
    seg_plan: list[PlannedFile],
    progress_cb: Callable[[int, int], None] | None = None,
    file_cb: Callable[[str, int, int], None] | None = None,
    gate_check: GateCheck | None = None,
    headers: dict[str, str] | None = None,
    proxies: dict[str, str] | None = None,
) -> None:
    """Fetch every planned big file sequentially with live progress."""
    from huggingface_hub import hf_hub_url

    big_total = sum(p.size for p in seg_plan)
    cumulative = [0]
    base = [0]
    lock = threading.Lock()

    def aggregate(done: int, _total: int) -> None:
        if progress_cb is None:
            return
        with lock:
            cumulative[0] = base[0] + done
            current = cumulative[0]
        progress_cb(current, big_total)

    scratch_parent = Path(str(cache_dir)).parent.parent / "download-parts"
    repo_scratch = scratch_parent / f"models--{repo_id.replace('/', '--')}"
    opener = build_opener(proxies, user_agent=f"{APP_NAME}/segmented-downloader")
    for index, plan in enumerate(seg_plan):
        if gate_check is not None:
            gate_check()
        if file_cb is not None:
            file_cb(plan.filename, index, len(seg_plan))
        url = hf_hub_url(repo_id, plan.filename, revision=commit)
        final_url, size, etag = resolve_download(url, headers=headers, opener_factory=lambda: opener)
        if size is None or size != plan.size:
            raise SegmentedDownloadError(f"size changed for {plan.filename} (plan {plan.size}, now {size})")
        assembled = _dl.download_file_segmented(
            url=final_url,
            filename=plan.filename,
            total_size=size,
            etag=etag,
            expected_sha256=plan.sha256,
            scratch_dir=repo_scratch,
            progress_cb=aggregate,
            gate_check=gate_check,
            headers=headers,
            opener_factory=lambda: opener,
        )
        install_blob_into_hf_cache(
            cache_dir=cache_dir,
            repo_id=repo_id,
            commit=commit,
            filename=plan.filename,
            blob_sha256=plan.sha256,
            assembled_path=assembled,
        )
        with lock:
            base[0] += plan.size
    # Best-effort scratch cleanup (ignore_errors already suppresses;
    shutil.rmtree(repo_scratch, ignore_errors=True)


def install_blob_into_hf_cache(
    *,
    cache_dir: str | Path,
    repo_id: str,
    commit: str,
    filename: str,
    blob_sha256: str,
    assembled_path: str | Path,
) -> Path:
    """Place a verified file into the HF hub cache layout and return the"""
    cache = Path(cache_dir).resolve()
    blobs_dir = cache / "blobs"
    blobs_dir.mkdir(parents=True, exist_ok=True)
    blob_path = blobs_dir / blob_sha256
    if blob_path.exists():
        Path(assembled_path).unlink(missing_ok=True)
    else:
        shutil.move(str(assembled_path), str(blob_path))

    snap_dir = (cache / "snapshots" / commit).resolve()
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_file = _resolve_within(snap_dir, filename)
    snap_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        if snap_file.is_symlink() or snap_file.exists():
            snap_file.unlink()
        # Symlink targets resolve from the link's directory, not the snapshot root.
        rel = os.path.relpath(blob_path, snap_file.parent)
        os.symlink(rel, snap_file)
    except OSError:
        # Windows without symlink privilege (or any symlink failure):
        try:
            if snap_file.is_symlink() or snap_file.exists():
                snap_file.unlink()
        except OSError:
            log.debug(
                "[DOWNLOAD] could not remove stale snapshot symlink before copy: %s",
                snap_file,
                exc_info=True,
            )
        shutil.copyfile(blob_path, snap_file)
    return snap_file
