"""Cycle bookkeeping, retention pruning, and history-delete cleanup."""

from __future__ import annotations

import contextlib
import json
import logging
import time
from pathlib import Path

from voice_typer.server.branding import APP_NAME
from voice_typer.server.screenshots import paths as _paths

log = logging.getLogger(__name__)

MAX_SHOTS_PER_CYCLE = 1
RETENTION_DAYS = 30
MAX_BYTES = 500 * 1024 * 1024


class AlreadyCapturedError(Exception):
    pass


def read_meta(cycle_id: str, *, base: Path | None = None) -> dict:
    meta = _paths.meta_path(cycle_id, base=base)
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_meta(cycle_id: str, payload: dict, *, base: Path | None = None) -> None:
    meta = _paths.meta_path(cycle_id, base=base)
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def cycle_captured(cycle_id: str, *, base: Path | None = None) -> bool:
    shots = read_meta(cycle_id, base=base).get("shots", [])
    if shots and any(Path(s).exists() for s in shots if isinstance(s, str)):
        return True
    return _paths.shot_path(cycle_id, base=base).exists()


def register_shot(cycle_id: str, shot: str, *, base: Path | None = None) -> None:
    if cycle_captured(cycle_id, base=base):
        raise AlreadyCapturedError("screenshot_already_captured")
    meta = read_meta(cycle_id, base=base)
    shots = [s for s in meta.get("shots", []) if isinstance(s, str)]
    shots.append(shot)
    meta["shots"] = shots[:MAX_SHOTS_PER_CYCLE]
    meta["cycle"] = _paths.sanitize_cycle_id(cycle_id)
    write_meta(cycle_id, meta, base=base)


def get_status(cycle_id: str, *, base: Path | None = None) -> dict:
    meta = read_meta(cycle_id, base=base)
    shots = [s for s in meta.get("shots", []) if isinstance(s, str) and Path(s).exists()]
    default = str(_paths.shot_path(cycle_id, base=base))
    if not shots and Path(default).exists():
        shots = [default]
    return {"captured": bool(shots), "paths": shots}


def clear_cycle(cycle_id: str, *, base: Path | None = None) -> bool:
    directory = _paths.cycle_dir(cycle_id, base=base)
    if not directory.exists():
        return False
    for child in sorted(directory.glob("*")):
        with contextlib.suppress(OSError):
            child.unlink() if child.is_file() else None
    with contextlib.suppress(OSError):
        directory.rmdir()
    return True


def delete_files_for_paths(files: list[str]) -> int:
    removed = 0
    for item in files:
        with contextlib.suppress(OSError):
            if item and Path(item).is_file():
                Path(item).unlink()
                removed += 1
    return removed


def delete_screenshots_for_history_id(history_id: int, *, base: Path | None = None) -> int:
    # No DB column (migration risk); scan sidecar metas for the linked id.
    root = _paths.screenshots_root(base=base)
    if not root.exists():
        return 0
    removed = 0
    for meta_file in root.glob("*/**/" + _paths.META_FILENAME):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("history_id") != history_id:
            continue
        removed += delete_files_for_paths([s for s in meta.get("shots", []) if isinstance(s, str)])
        with contextlib.suppress(OSError):
            meta_file.unlink()
    return removed


def delete_all_screenshots(*, base: Path | None = None) -> int:
    root = _paths.screenshots_root(base=base)
    if not root.exists():
        return 0
    removed = 0
    for png in root.glob("*/**/shot-*.png"):
        with contextlib.suppress(OSError):
            png.unlink()
            removed += 1
    return removed


def prune_screenshots(*, base: Path | None = None, now: float | None = None) -> dict:
    root = _paths.screenshots_root(base=base)
    if not root.exists():
        return {"removed": 0, "bytes": 0}
    cutoff = (now if now is not None else time.time()) - RETENTION_DAYS * 86400
    pngs = [p for p in root.glob("*/**/shot-*.png") if p.is_file()]
    # Oldest first so the size cap evicts stale shots before recent ones.
    pngs.sort(key=lambda p: p.stat().st_mtime)
    removed = 0
    for png in pngs:
        try:
            if png.stat().st_mtime < cutoff:
                png.unlink()
                removed += 1
        except OSError:
            continue
    remaining = [p for p in root.glob("*/**/shot-*.png") if p.is_file()]
    remaining.sort(key=lambda p: p.stat().st_mtime)
    total = 0
    sizes: dict[Path, int] = {}
    for png in remaining:
        try:
            sizes[png] = png.stat().st_size
            total += sizes[png]
        except OSError:
            continue
    for png in remaining:
        if total <= MAX_BYTES:
            break
        try:
            png.unlink()
            total -= sizes[png]
            removed += 1
        except OSError:
            continue
    for cycle in sorted(root.glob("*/**")):
        with contextlib.suppress(OSError):
            if cycle.is_dir() and not any(cycle.iterdir()):
                cycle.rmdir()
    log.info("[%s] screenshot prune removed=%d", APP_NAME, removed)
    return {"removed": removed, "bytes": total}
