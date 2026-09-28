"""
OpenMP / ctranslate2 bundling validation (Win + macOS + Linux).

C7 (ADR-0025): ASR lives in the pack worker — the slim sidecar bundles
no ctranslate2 native libs and needs no OpenMP runtime of its own. The
old bundling pins below were inverted to absence pins: re-adding CT2
plumbing fails loudly here (and in test_nuitka_asr_exclusions.py).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.fixtures.bash_utils import bash_usable

# Path from file → root:
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD_DIR = PROJECT_ROOT / "scripts" / "build"

WINDOWS_SCRIPT = BUILD_DIR / "build_sidecar_windows.sh"
MACOS_SCRIPT = BUILD_DIR / "build_sidecar_macos.sh"
LINUX_SCRIPT = BUILD_DIR / "build_sidecar_linux.sh"

# All 3 scripts under test, for cross-platform parametrized checks.
ALL_BUILD_SCRIPTS = [
    pytest.param(WINDOWS_SCRIPT, id="windows"),
    pytest.param(MACOS_SCRIPT, id="macos"),
    pytest.param(LINUX_SCRIPT, id="linux"),
]


@pytest.fixture(scope="module")
def windows_text() -> str:
    """Read the Windows build script once; fail fast if missing."""
    assert WINDOWS_SCRIPT.is_file(), f"missing: {WINDOWS_SCRIPT}"
    return WINDOWS_SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def macos_text() -> str:
    """Read the macOS build script once; fail fast if missing."""
    assert MACOS_SCRIPT.is_file(), f"missing: {MACOS_SCRIPT}"
    return MACOS_SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def linux_text() -> str:
    """Read the Linux build script once; fail fast if missing."""
    assert LINUX_SCRIPT.is_file(), f"missing: {LINUX_SCRIPT}"
    return LINUX_SCRIPT.read_text(encoding="utf-8")


@pytest.mark.parametrize("script", ALL_BUILD_SCRIPTS)
def test_build_script_exists(script: Path):
    """Each platform's build_sidecar_*.sh must exist at the canonical path."""
    assert script.is_file(), f"missing build script: {script}. Did the project layout change?"
    # Also assert it's non-empty (a stub would be a regression).
    assert script.stat().st_size > 1000, (
        f"{script} is suspiciously small ({script.stat().st_size} bytes); "
        "expected a full Nuitka invocation script (~3-5 KB)."
    )


@pytest.mark.parametrize("script", ALL_BUILD_SCRIPTS)
def test_build_script_is_bash_syntax_valid(script: Path):
    """``bash -n`` must parse each script without syntax errors."""
    if not bash_usable():
        pytest.skip("bash not available or not usable on this host, cannot run `bash -n`.")
    result = subprocess.run(
        ["bash", "-n", str(script)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (
        f"bash -n failed on {script}:\n--- stderr ---\n{result.stderr}\n--- stdout ---\n{result.stdout}"
    )


def test_windows_has_no_ct2_native_lib_plumbing(windows_text: str):
    """C7: no ctranslate2 data-dir/DLL plumbing may remain (worker owns it)."""
    for token in ("CT2_DATA_DIR_SRC", "CT2_DLL", "CT2_LIBS_DIR", "CT2_LIB_DIR", "CT2_DIR"):
        assert token not in windows_text, f"build_sidecar_windows.sh still references {token}"
    assert "--include-data-dir" not in windows_text, "slim Windows build must not --include-data-dir anything"


def test_macos_has_no_ct2_native_lib_plumbing(macos_text: str):
    """C7: no ctranslate2 data-dir plumbing may remain (worker owns it)."""
    for token in ("CT2_DATA_DIR_SRC", "CT2_DLL", "CT2_LIBS_DIR", "CT2_LIB_DIR", "CT2_DIR"):
        assert token not in macos_text, f"build_sidecar_macos.sh still references {token}"
    assert "ctranslate2/lib" not in macos_text, "slim macOS build must not reference ctranslate2/lib"


def test_linux_has_no_ct2_native_lib_plumbing(linux_text: str):
    """C7: no ctranslate2 data-dir plumbing may remain (worker owns it)."""
    for token in ("CT2_DATA_DIR_SRC", "CT2_DLL", "CT2_LIBS_DIR", "CT2_DIR"):
        assert token not in linux_text, f"build_sidecar_linux.sh still references {token}"
    assert "ctranslate2/lib" not in linux_text, "slim Linux build must not reference ctranslate2/lib"


@pytest.mark.parametrize("script", ALL_BUILD_SCRIPTS)
def test_no_ct2_data_dir_guards_remain(script: Path):
    """C7: the XPLAT-3/BUILD-2 CT2 guard blocks are gone with the plumbing."""
    text = script.read_text(encoding="utf-8")
    assert 'if [[ -d "$CT2_LIBS_DIR" ]]' not in text, f"{script.name} still guards a removed CT2 dir"
    assert "CT2_LIBS_DIR" not in text, f"{script.name} still defines CT2_LIBS_DIR"


def test_macos_sibling_uses_nuitka_args_array_pattern(macos_text: str):
    """Sanity: macOS sibling uses the ``NUITKA_ARGS=(...)`` array pattern."""
    assert "NUITKA_ARGS=(" in macos_text
    assert '"${NUITKA_ARGS[@]}"' in macos_text


def test_linux_sibling_uses_nuitka_args_array_pattern(linux_text: str):
    """Sanity: Linux sibling uses the ``NUITKA_ARGS=(...)`` array pattern."""
    assert "NUITKA_ARGS=(" in linux_text
    assert '"${NUITKA_ARGS[@]}"' in linux_text


def test_all_three_scripts_exclude_ctranslate2_package(windows_text: str, macos_text: str, linux_text: str):
    """C7: all 3 scripts must ``--nofollow-import-to=ctranslate2``."""
    for label, text in (("windows", windows_text), ("macos", macos_text), ("linux", linux_text)):
        assert "--nofollow-import-to=ctranslate2" in text, f"build_sidecar_{label}.sh must exclude ctranslate2"
        assert "--include-package=ctranslate2" not in text, f"build_sidecar_{label}.sh must not bundle ctranslate2"


def test_all_three_scripts_exclude_faster_whisper_package(windows_text: str, macos_text: str, linux_text: str):
    """C7: all 3 scripts must ``--nofollow-import-to=faster_whisper``."""
    for label, text in (("windows", windows_text), ("macos", macos_text), ("linux", linux_text)):
        assert "--nofollow-import-to=faster_whisper" in text, f"build_sidecar_{label}.sh must exclude faster_whisper"
        assert "--include-package=faster_whisper" not in text, (
            f"build_sidecar_{label}.sh must not bundle faster_whisper"
        )
