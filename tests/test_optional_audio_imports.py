"""Config imports must survive an install with no optional audio dependency.

The lock file excludes soundfile on macOS arm64 and bare-pytest guard jobs
install only pytest. The config import chain reaches the TTS package, so no
audio library may be imported at module import time.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_CONFIG_MODULES = (
    "voice_typer.server.config",
    "voice_typer.server.app",
    "voice_typer.server._paths",
    "voice_typer.server.config_internals.paths",
    "voice_typer.server.logging_setup",
    "voice_typer.server.startup_sequence._phases_early",
)


def test_config_modules_import_without_soundfile() -> None:
    """Every config-dir patch target imports with soundfile unavailable."""
    script = "\n".join(
        [
            "import sys",
            "sys.modules['soundfile'] = None",
            *(f"import {name}" for name in _CONFIG_MODULES),
            "print('config-import-ok')",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "config-import-ok" in result.stdout


def test_i18n_completeness_passes_in_minimal_environment(tmp_path: Path) -> None:
    """The CI-failing test file works with soundfile and pytest-benchmark absent."""
    (tmp_path / "sitecustomize.py").write_text(
        "import sys\nsys.modules['soundfile'] = None\n", encoding="utf-8"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(tmp_path), env.get("PYTHONPATH", "")] if env.get("PYTHONPATH") else [str(tmp_path)]
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_i18n_completeness.py",
            "--no-cov",
            "-q",
            "-p",
            "no:benchmark",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert "PytestConfigWarning" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stderr
