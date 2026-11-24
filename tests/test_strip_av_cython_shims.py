"""The retired media-library shim strip must not return to the freeze path."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER = PROJECT_ROOT / "scripts" / "build" / "strip_av_cython_shims.py"


def test_helper_is_deleted() -> None:
    assert not HELPER.exists(), "the retired Cython-shim strip helper must stay deleted"


@pytest.mark.parametrize(
    "entry",
    [
        ".github/workflows/tauri-windows-build.yml",
        "scripts/build/build_sidecar_windows.sh",
        "scripts/build/build_sidecar_macos.sh",
        "scripts/build/build_sidecar_linux.sh",
        "scripts/build/build_worker_windows.sh",
    ],
)
def test_build_entries_do_not_invoke_shim_strip(entry: str) -> None:
    text = (PROJECT_ROOT / entry).read_text(encoding="utf-8")
    assert "strip_av_cython_shims" not in text, f"{entry} must not strip retired media-library shims"
