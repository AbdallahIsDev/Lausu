"""Slash-form coverage for the torch-free bundle gate.

The gate scans a Nuitka onefile for embedded torch import sites. Nuitka records
module paths with slashes (``torch/__init__.py``), so a dot-only regex misses the
very paths the gate's own comment promises to catch. These tests drive the real
script through both scanner paths: ``grep -E`` (when ``strings`` exists) and
the chunked Python ``re`` fallback.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fixtures.bash_utils import bash_usable

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build" / "check_bundle_torch_free.sh"

CLEAN_BUNDLE = b"silero_vad.onnx\nnumpy.core\n"
SLASH_FORM = b"torch/__init__.py\n"
DOTTED_FORM = b"import torch.nn\n"


def _bash_python() -> str:
    """A real interpreter the script can resolve via ``command -v`` in bash."""
    python = sys.executable
    if os.name == "nt":
        drive, rest = os.path.splitdrive(python)
        python = f"/{drive[0].lower()}{rest.replace(chr(92), '/')}"
    return python


def _write_binary(tmp_path: Path, content: bytes) -> Path:
    binary = tmp_path / "sidecar.bin"
    binary.write_bytes(content)
    return binary


def _gate_env(ere: bool = False, tmp_path: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHON"] = _bash_python()
    if ere:
        assert tmp_path is not None
        shim_dir = tmp_path / "shimbin"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "strings"
        shim.write_text('#!/bin/sh\ncat "$@"\n', encoding="utf-8")
        shim.chmod(0o755)
        env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
    return env


def _run_gate(binary: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), str(binary)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env or _gate_env(),
    )


@pytest.mark.skipif(not bash_usable(), reason="bash not available on this host")
class TestTorchFreeGate:
    def test_slash_form_torch_path_fails_gate(self, tmp_path: Path) -> None:
        result = _run_gate(_write_binary(tmp_path, SLASH_FORM))
        assert result.returncode == 1, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    def test_dotted_torch_import_still_fails_gate(self, tmp_path: Path) -> None:
        result = _run_gate(_write_binary(tmp_path, DOTTED_FORM))
        assert result.returncode == 1, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    def test_clean_bundle_passes_gate(self, tmp_path: Path) -> None:
        result = _run_gate(_write_binary(tmp_path, CLEAN_BUNDLE))
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    def test_slash_form_detected_by_ere_scanner(self, tmp_path: Path) -> None:
        env = _gate_env(ere=True, tmp_path=tmp_path)
        result = _run_gate(_write_binary(tmp_path, SLASH_FORM), env=env)
        assert result.returncode == 1, f"stdout={result.stdout!r} stderr={result.stderr!r}"


@pytest.mark.skipif(not bash_usable(), reason="bash not available on this host")
def test_bash_syntax_valid() -> None:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
