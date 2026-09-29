"""yt-dlp extractors must ship as bytecode in every Nuitka freeze.

``yt_dlp.extractor`` holds ~940 extractor modules plus the 781KB
``lazy_extractors`` hub. Compiling them to C OOMs MSVC (C1060/C1002 on
the 7GB CI runner) and bloats the binary; yt-dlp lazy-loads extractors
via ``importlib`` at runtime, which resolves bytecode modules fine
(Nuitka anti-bloat "bytecode" mode, same mechanism as its
eventlet/matplotlib rules).
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FLAG = "--noinclude-custom-mode=yt_dlp.extractor:bytecode"

INVOCATIONS = [
    ".github/workflows/tauri-windows-build.yml",
    "scripts/build/build_sidecar_windows.sh",
    "scripts/build/build_sidecar_macos.sh",
    "scripts/build/build_sidecar_linux.sh",
    "scripts/build/build_worker_windows.sh",
    "scripts/build/build_worker_macos.sh",
    "scripts/build/build_worker_linux.sh",
]


@pytest.mark.parametrize("relative", INVOCATIONS)
def test_extractor_bytecode_flag_present(relative: str):
    """Every Nuitka invocation pulling yt-dlp must bytecode the extractors."""
    path = PROJECT_ROOT / relative
    assert path.is_file(), f"missing Nuitka invocation file: {relative}"
    assert FLAG in path.read_text(encoding="utf-8"), (
        f"{relative} is missing {FLAG!r}; without it Nuitka compiles all "
        "~940 yt-dlp extractor modules to C and MSVC runs out of heap "
        "(C1060/C1002)."
    )
