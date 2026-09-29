"""Regression guard: av Cython shims must be stripped pre-freeze.

Nuitka's optimizer crashes on av's ``import cython`` sources
(assert micro_passes == 0 on av.video.stream). Each shim ships a
precompiled twin Python prefers, so deleting the .py is import-safe.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER = PROJECT_ROOT / "scripts" / "build" / "strip_av_cython_shims.py"


def _load_helper():
    spec = importlib.util.spec_from_file_location("strip_av_cython_shims", HELPER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_site(tmp_path: Path) -> Path:
    av = tmp_path / "av"
    (av / "video").mkdir(parents=True)
    (av / "__init__.py").write_text("x = 1\n", encoding="utf-8")
    (av / "about.py").write_text("v = 1\n", encoding="utf-8")
    (av / "video" / "stream.py").write_text("import cython\n", encoding="utf-8")
    (av / "video" / "stream.pyd").write_bytes(b"\x00")
    (av / "video" / "stream.pyi").write_text("s: int\n", encoding="utf-8")
    (av / "audio.py").write_text("import cython\n", encoding="utf-8")
    (av / "audio.pyd").write_bytes(b"\x00")
    return tmp_path


def test_removes_only_py_with_compiled_twin(tmp_path: Path):
    site = _fake_site(tmp_path)
    mod = _load_helper()
    assert mod.strip_av_shims(site) == 2
    av = site / "av"
    assert not (av / "video" / "stream.py").exists()
    assert not (av / "audio.py").exists()
    assert (av / "__init__.py").exists()
    assert (av / "about.py").exists()
    assert (av / "video" / "stream.pyd").exists()
    assert (av / "video" / "stream.pyi").exists()


def test_second_run_is_noop(tmp_path: Path):
    site = _fake_site(tmp_path)
    mod = _load_helper()
    assert mod.strip_av_shims(site) == 2
    assert mod.strip_av_shims(site) == 0


def test_missing_av_dir_returns_zero(tmp_path: Path):
    mod = _load_helper()
    assert mod.strip_av_shims(tmp_path / "empty-site") == 0


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
def test_build_entries_invoke_shim_strip(entry: str):
    text = (PROJECT_ROOT / entry).read_text(encoding="utf-8")
    assert "strip_av_cython_shims" in text, f"{entry} must strip av shims pre-Nuitka"
