"""Freeze pins: the retired Python ASR stack has no place in any build.

Replaces the per-platform legacy-engine validation tests. The native GGUF
runner is shipped as a sibling binary; no Python ASR package is installed or
referenced by Nuitka flags on any platform.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "build"
WORKFLOW = ROOT / ".github" / "workflows" / "tauri-windows-build.yml"
FW = "faster" + "_whisper"
LEGACY_CT = "ctranslate" + "2"
BANNED = (FW, "faster" + "-whisper", LEGACY_CT, "av")


@pytest.fixture(scope="module")
def freeze_texts() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8", errors="replace")
        for path in SCRIPTS.glob("build_*.sh")
        if path.is_file()
    } | {"tauri-windows-build.yml": WORKFLOW.read_text(encoding="utf-8")}


@pytest.mark.parametrize("package", BANNED)
def test_no_legacy_package_flag_anywhere(freeze_texts: dict[str, str], package: str) -> None:
    for label, text in freeze_texts.items():
        for flag in ("--include-package", "--nofollow-import-to", "--include-data-dir"):
            assert f"{flag}={package}" not in text, f"{label} still carries {flag}={package}"


def test_no_legacy_python_install_step(freeze_texts: dict[str, str]) -> None:
    for label, text in freeze_texts.items():
        assert f"import {FW}" not in text, f"{label} still verifies the retired ASR import"
        assert f"import {LEGACY_CT}" not in text, f"{label} still verifies the retired ASR import"


def test_gpl_gate_switch_is_unchanged(freeze_texts: dict[str, str]) -> None:
    text = freeze_texts["tauri-windows-build.yml"]
    assert "ENFORCE_NO_GPL_DLLS" in text
    assert "${{ vars.ENFORCE_NO_GPL_DLLS || '0' }}" in text
