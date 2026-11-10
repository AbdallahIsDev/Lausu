"""Filesystem layout of the user-level CUDA runtime install."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

from voice_typer.server._paths import config_dir

CUDA_DIRNAME = "cuda"
SITE_PACKAGES_DIRNAME = "site-packages"


def cuda_root() -> Path:
    """Root of the user-level CUDA install (writable app-data dir)."""
    return config_dir() / CUDA_DIRNAME


def install_dir() -> Path:
    """Mini site-packages holding ``nvidia/*`` + ``onnxruntime``."""
    return cuda_root() / SITE_PACKAGES_DIRNAME


def downloads_dir() -> Path:
    """Verified wheel cache; survives restarts so a retry resumes."""
    return cuda_root() / "downloads"


def staging_dir() -> Path:
    """Scratch space for wheel extraction (never on ``sys.path``)."""
    return cuda_root() / "staging"


def activation_file() -> Path:
    """Pending/failed activation record written after a verified install."""
    return cuda_root() / "activation.json"


def ensure_install_on_sys_path() -> bool:
    """Prepend the install to ``sys.path`` so ``onnxruntime`` resolves there.

    Must run before any ``import onnxruntime``: the CPU and GPU wheels share
    the module name, so the first import wins for the whole process.
    """
    target = install_dir()
    if not target.is_dir():
        return False
    entry = str(target)
    if sys.path and sys.path[0] == entry:
        return True
    with contextlib.suppress(ValueError):
        sys.path.remove(entry)
    sys.path.insert(0, entry)
    return True
