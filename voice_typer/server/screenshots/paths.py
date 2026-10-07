"""Path resolver for beta screenshot files under the profile dir."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

SCREENSHOTS_SUBDIR = "screenshots"
META_FILENAME = "meta.json"

_UNSAFE_CYCLE_RE = re.compile(r"[^0-9A-Za-z_-]+")


def _config_dir() -> Path:
    from voice_typer.server.config import _config_dir as _real

    return _real()


def screenshots_root(*, base: Path | None = None) -> Path:
    return (base if base is not None else _config_dir()) / SCREENSHOTS_SUBDIR


def sanitize_cycle_id(cycle_id: str) -> str:
    cleaned = _UNSAFE_CYCLE_RE.sub("_", cycle_id.strip()).strip("_")
    return cleaned[:64] if cleaned else "manual"


def _date_for_cycle(cycle_id: str) -> str:
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", cycle_id.strip())
    if m:
        return m.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def cycle_dir(cycle_id: str, *, base: Path | None = None) -> Path:
    # Date prefix keeps per-day listing cheap without parsing cycle ids.
    return screenshots_root(base=base) / _date_for_cycle(cycle_id) / sanitize_cycle_id(cycle_id)


def shot_path(cycle_id: str, index: int = 1, *, base: Path | None = None) -> Path:
    return cycle_dir(cycle_id, base=base) / f"shot-{index}.png"


def meta_path(cycle_id: str, *, base: Path | None = None) -> Path:
    return cycle_dir(cycle_id, base=base) / META_FILENAME


def ensure_cycle_dir(cycle_id: str, *, base: Path | None = None) -> Path:
    path = cycle_dir(cycle_id, base=base)
    path.mkdir(parents=True, exist_ok=True)
    return path
