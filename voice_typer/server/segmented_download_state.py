"""Resume state, part files, and assembly for the segmented downloader.

Owns the on-disk ``.state.json`` schema (atomic tmp+rename), the
``.partN`` path helpers, the repo-relative path guard, state
reconciliation against part sizes, and the assemble+sha256 verification.
Moved verbatim out of ``voice_typer.server.segmented_download`` (which
re-exports every name).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from voice_typer.server.segmented_download_base import (
    READ_CHUNK_BYTES,
    SegmentedDownloadError,
    SegmentRange,
)

_STATE_VERSION = 1


def _safe_filename(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", filename)


def _resolve_within(root: Path, relative: str) -> Path:
    """Resolve a repo-relative path inside ``root``, rejecting escapes.

    Snapshot paths come from the remote tree API; a crafted entry must not
    place a file outside the cache directory.
    """
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise SegmentedDownloadError(f"refusing unsafe snapshot path: {relative!r}")
    # POSIX does not parse Windows-absolute forms (``C:/...``, ``C:\\...``,
    # UNC ``\\\\...``) as absolute, but a Windows host would resolve them
    # outside the cache. Reject them on every platform.
    if re.match(r"^[A-Za-z]:", relative) or relative.startswith("\\\\"):
        raise SegmentedDownloadError(f"refusing unsafe snapshot path: {relative!r}")
    root = root.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise SegmentedDownloadError(f"refusing snapshot path outside cache dir: {relative!r}")
    return resolved


def state_path_for(scratch_dir: Path, filename: str) -> Path:
    return scratch_dir / f"{_safe_filename(filename)}.state.json"


def part_path_for(scratch_dir: Path, filename: str, index: int) -> Path:
    return scratch_dir / f"{_safe_filename(filename)}.part{index}"


def write_state(
    state_path: Path,
    *,
    url: str,
    etag: str | None,
    total_size: int,
    expected_sha256: str,
    segments: list[dict[str, Any]],
) -> None:
    """Atomically persist segment completion (tmp + rename)."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _STATE_VERSION,
        "url": url,
        "etag": etag,
        "total_size": total_size,
        "expected_sha256": expected_sha256,
        "segments": segments,
    }
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, state_path)


def read_state(state_path: Path) -> dict[str, Any] | None:
    """Load a state file; ``None`` when absent/corrupt/wrong version."""
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != _STATE_VERSION:
        return None
    return data


def state_matches(
    state: dict[str, Any],
    *,
    url: str,
    etag: str | None,
    total_size: int,
    expected_sha256: str,
) -> bool:
    """True when the on-disk state describes THIS exact download."""
    if (
        state.get("url") != url
        or state.get("total_size") != total_size
        or state.get("expected_sha256") != expected_sha256
    ):
        return False
    # An ETag change means the server-side file changed, stale parts
    return state.get("etag") == etag


def _discard_resume_state(scratch_dir: Path, filename: str, state_path: Path) -> None:
    import contextlib

    state_path.unlink(missing_ok=True)
    for part in scratch_dir.glob(f"{_safe_filename(filename)}.part*"):
        with contextlib.suppress(OSError):
            part.unlink()


def _reconcile_state(
    scratch_dir: Path,
    filename: str,
    segments: list[SegmentRange],
    saved: list[dict[str, Any]],
) -> list[bool]:
    """Validate saved completion flags against on-disk part sizes."""
    by_index = {int(s.get("index", -1)): s for s in saved if isinstance(s, dict)}
    done: list[bool] = []
    for seg in segments:
        part = part_path_for(scratch_dir, filename, seg.index)
        entry = by_index.get(seg.index, {})
        flagged = bool(entry.get("done"))
        size = part.stat().st_size if part.exists() else -1
        if flagged and size == seg.length:
            done.append(True)
            continue
        if size > seg.length and part.exists():
            # Torn write (kill -9 mid-flush): truncate, re-fetch segment.
            with open(part, "r+b") as f:
                f.truncate(seg.length)
        done.append(False)
    return done


def _assemble_parts(scratch_dir: Path, filename: str, segments: list[SegmentRange], dest: Path) -> None:
    with open(dest, "wb") as out:
        for seg in segments:
            part = part_path_for(scratch_dir, filename, seg.index)
            with open(part, "rb") as f:
                shutil.copyfileobj(f, out, length=READ_CHUNK_BYTES)


def _assemble_and_verify(
    scratch_dir: Path,
    filename: str,
    segments: list[SegmentRange],
    expected_sha256: str,
    assembled: Path,
) -> None:
    _assemble_parts(scratch_dir, filename, segments, assembled)
    digest = hashlib.sha256()
    with open(assembled, "rb") as f:
        for chunk in iter(lambda: f.read(READ_CHUNK_BYTES), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256.lower():
        # Poisoned parts must not linger for a later retry to trust.
        import contextlib

        _discard_resume_state(scratch_dir, filename, state_path_for(scratch_dir, filename))
        with contextlib.suppress(OSError):
            assembled.unlink()
        raise SegmentedDownloadError(
            f"assembled sha256 mismatch for {filename} (got {digest.hexdigest()[:16]}…, parts discarded)"
        )
