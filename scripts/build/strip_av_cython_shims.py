"""Remove PyAV's Cython pure-mode .py shims before a Nuitka freeze.

Nuitka's optimizer chokes on av's ``import cython`` sources
(assert micro_passes == 0 on av.video.stream, Nuitka issue 3970).
Each shim has a precompiled twin (.pyd/.so) that Python prefers at
runtime, so deleting the .py is import-safe (verified: import av +
audio decode still work). Pure-Python files without a twin are kept.
"""

from __future__ import annotations

import importlib.machinery
import site
import sys
from pathlib import Path


def strip_av_shims(site_dir: str | Path) -> int:
    av_dir = Path(site_dir) / "av"
    if not av_dir.is_dir():
        print(f"[strip-av-shims] no av package at {av_dir}, nothing to do")
        return 0
    exts = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    deleted = 0
    for py in av_dir.rglob("*.py"):
        if any((py.parent / (py.stem + s)).exists() for s in exts):
            py.unlink()
            deleted += 1
    print(f"[strip-av-shims] removed {deleted} Cython .py shims under {av_dir}")
    return deleted


def main() -> int:
    candidates = site.getsitepackages()
    total = 0
    for cand in candidates:
        total += strip_av_shims(cand)
    try:
        import av

        print(f"[strip-av-shims] import av ok ({av.__version__})")
    except ImportError as exc:
        print(f"[strip-av-shims] WARNING: import av failed after strip: {exc}")
        return 1
    _ = total
    return 0


if __name__ == "__main__":
    sys.exit(main())
