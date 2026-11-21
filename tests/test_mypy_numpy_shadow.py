"""Guard the mypy numpy shadow stubs (CQ-058).

mypy runs at ``python_version = "3.11"`` but numpy 2.x real stubs use PEP 695
``type`` statements, which mypy cannot parse at that language level. A parse
error cannot be suppressed by ``ignore_errors`` or ``follow_imports``, so
numpy is shadowed by local Any stubs under ``voice_typer/mypy_stubs/numpy/``.

This test forces mypy to follow every shadowed submodule with the repo config
and fails if any real PEP 695 stub leaks back into the build (the exact shape
of the CI failure on ``numpy.ctypeslib``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "pyproject.toml"
SHADOW_ROOT = PROJECT_ROOT / "voice_typer" / "mypy_stubs" / "numpy"


def _has_mypy() -> bool:
    try:
        return subprocess.run(
            [sys.executable, "-m", "mypy", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        ).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _shadowed_submodules() -> list[str]:
    """Top-level numpy submodules that have a local shadow stub."""
    if not SHADOW_ROOT.is_dir():
        return []
    subs: list[str] = []
    for entry in sorted(SHADOW_ROOT.iterdir()):
        if entry.name == "__init__.pyi":
            continue
        if entry.is_dir() and (entry / "__init__.pyi").is_file():
            subs.append(entry.name)
        elif entry.suffix == ".pyi":
            subs.append(entry.stem)
    return subs


@pytest.mark.skipif(not _has_mypy(), reason="mypy not installed in this environment")
@pytest.mark.timeout(120)
def test_numpy_shadow_stubs_parse_with_repo_config(tmp_path: Path) -> None:
    """All shadowed numpy submodules resolve without a PEP 695 parse error."""
    subs = _shadowed_submodules()
    assert subs, "numpy shadow stub package is missing"
    assert "ctypeslib" in subs, "numpy.ctypeslib shadow must exist (CI syntax failure)"

    snippet = tmp_path / "shadow_probe.py"
    snippet.write_text(
        "".join(f"import numpy.{sub}\n" for sub in subs) + "x = numpy.ctypeslib.as_ctypes\n",
        encoding="utf-8",
    )

    env = {k: v for k, v in os.environ.items() if k not in {"MYPYPATH", "MYPY_CACHE_DIR", "MYPY_CONFIG_FILE_DIR"}}
    env["MYPY_CACHE_DIR"] = str(tmp_path / "mypy_cache")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            str(snippet),
            "--config-file",
            str(CONFIG_PATH),
            "--no-incremental",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=110,
    )
    output = (result.stdout or "") + (result.stderr or "")

    assert result.returncode in (0, 1), (
        f"mypy failed to run (exit {result.returncode}) on the numpy shadow probe.\n{output}"
    )
    assert "[syntax]" not in output, f"a real numpy stub with PEP 695 syntax leaked in:\n{output}"
    assert "Type statement is only supported" not in output, f"PEP 695 parse error:\n{output}"
    assert "errors prevented further checking" not in output, f"fatal mypy parse failure:\n{output}"
