"""Resolve the ffmpeg/ffprobe executables used by media ingest.

Search order: explicit dev/test env override -> binary shipped next to the
sidecar/app -> PATH, but PATH is a NON-frozen development-only concession:
the locally installed ffmpeg 9.x is a GPL build and must never be shipped or
silently relied on in a frozen app.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

log = logging.getLogger(__name__)

ENV_FFMPEG = "LAUSU_FFMPEG"
ENV_FFPROBE = "LAUSU_FFPROBE"


@dataclass(frozen=True)
class BinaryPair:
    """Resolved executables. ``ffprobe`` is optional; probe calls fail soft."""

    ffmpeg: str
    ffprobe: str | None


def is_frozen_build(
    module_globals: dict[str, object] | None = None,
    sys_module: ModuleType | None = None,
) -> bool:
    """True for Nuitka-compiled and PyInstaller-frozen builds.

    ``sys.frozen`` is a PyInstaller convention; Nuitka does not set it. The
    compiled module instead carries a ``__compiled__`` global (proved with a
    real Nuitka 2.8.10 onefile probe). Both signals are checked.
    """
    g = globals() if module_globals is None else module_globals
    s = sys if sys_module is None else sys_module
    return (
        g.get("__compiled__") is not None
        or bool(getattr(s, "frozen", False))
        or bool(getattr(s, "_MEIPASS", None))
    )


def _arch() -> str:
    machine = platform.machine().lower()
    if "x86_64" in machine or "amd64" in machine:
        return "x86_64"
    if "aarch64" in machine or "arm64" in machine:
        return "aarch64"
    return ""


def _names(program: str) -> tuple[str, ...]:
    suffix = ".exe" if os.name == "nt" else ""
    candidates = [f"{program}{suffix}", program]
    arch = _arch()
    if arch:
        candidates += [f"{program}-{arch}{suffix}", f"{program}-{arch}"]
    return tuple(dict.fromkeys(candidates))


def bundled_bin_dir(
    module_globals: dict[str, object] | None = None,
    sys_module: ModuleType | None = None,
) -> Path:
    """Directory holding binaries installed beside the original executable.

    A real Nuitka 2.8.10 onefile probe (all four launch modes, including
    spawn by a Python parent) showed ``sys.executable`` points INSIDE the
    cached extraction dir while ``__compiled__.containing_dir`` points at the
    original exe. Tauri installs ffmpeg beside the original exe, so using
    ``sys.executable`` there silently broke the shipped app.
    """
    g = globals() if module_globals is None else module_globals
    s = sys if sys_module is None else sys_module
    compiled = g.get("__compiled__")
    containing = getattr(compiled, "containing_dir", None) if compiled is not None else None
    if containing:
        try:
            base = Path(containing).expanduser().resolve()
        except (OSError, RuntimeError, TypeError):
            base = None
        if base is not None and base.is_dir():
            return base
    try:
        return Path(s.executable).resolve().parent
    except (OSError, RuntimeError):
        return Path(s.executable).parent


def _shipped_dirs() -> tuple[Path, ...]:
    """Exe-adjacent, resources, parent chain and onefile extraction dirs.

    Mirrors the lookup order in ``server/autostart/tauri_spawn.py``: inside a
    onefile extraction the ``__file__`` tree is garbage, so the executable
    directory is searched first.
    """
    dirs: list[Path] = []
    exe_dir = bundled_bin_dir()
    dirs.extend((exe_dir, exe_dir / "resources"))
    dirs.extend(list(exe_dir.parents)[:3])
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        dirs.extend((base / "bin", base / "voice_typer" / "server" / "bin", base))
    module_dir = Path(__file__).resolve().parent
    dirs.extend((module_dir / "bin", module_dir.parent / "bin"))
    return tuple(dict.fromkeys(dirs))


def _env_path(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    if Path(value).is_file():
        return value
    log.warning("[MEDIA] %s is set but is not a file: %s", name, value)
    return None


def _shipped(program: str) -> str | None:
    for directory in _shipped_dirs():
        for name in _names(program):
            candidate = directory / name
            try:
                if candidate.is_file():
                    return str(candidate)
            except OSError:
                continue
    return None


def _dev_path(program: str) -> str | None:
    """PATH fallback, development only (never in a frozen build)."""
    if is_frozen_build():
        return None
    found = shutil.which(program)
    if found:
        log.warning(
            "[MEDIA] using %s from PATH (%s); this is a dev-only fallback — "
            "local GPL builds must never be bundled or relied on in a release",
            program,
            found,
        )
    return found


def resolve_binaries() -> BinaryPair | None:
    """Find ffmpeg (required) and ffprobe (optional) for this process."""
    ffmpeg = _env_path(ENV_FFMPEG) or _shipped("ffmpeg") or _dev_path("ffmpeg")
    if not ffmpeg:
        return None
    ffprobe = _env_path(ENV_FFPROBE) or _shipped("ffprobe") or _dev_path("ffprobe")
    return BinaryPair(ffmpeg=ffmpeg, ffprobe=ffprobe)
