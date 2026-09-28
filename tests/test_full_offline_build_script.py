"""Pins for scripts/build/build_full_offline_installer_windows.sh (plan §4.1/§11.9).

The full-offline installer binds the slim-core installer .exe + a
runtime-pack zip via makensis on scripts/windows/full-offline-installer.nsi.
No bash/makensis on dev hosts: static contract pins (+ bash -n when available).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests.fixtures.bash_utils import bash_usable

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build" / "build_full_offline_installer_windows.sh"
NSI = REPO_ROOT / "scripts" / "windows" / "full-offline-installer.nsi"


def _text() -> str:
    assert SCRIPT.is_file(), f"missing: {SCRIPT}"
    return SCRIPT.read_text(encoding="utf-8")


def test_script_exists_and_non_stub():
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_size > 1000


def test_bash_syntax_valid():
    if not bash_usable():
        pytest.skip("bash not available on this host")
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


def test_pack_version_integer_gated():
    text = _text()
    assert re.search(r"PACK_VERSION.*\^?\[0-9\]", text), "pack version must be integer-validated"


def test_output_name_canonical():
    text = _text()
    assert "artifact_names.py" in text and "--full-offline" in text, (
        "output name must come from artifact_names.py --full-offline (C-CI-13, single naming scheme)"
    )


def test_missing_inputs_fail_fast():
    text = _text()
    assert 'test -f "$SLIM_EXE"' in text or '[[ -f "$SLIM_EXE" ]]' in text
    assert 'test -f "$PACK_ZIP"' in text or '[[ -f "$PACK_ZIP" ]]' in text
    assert "command -v makensis" in text
