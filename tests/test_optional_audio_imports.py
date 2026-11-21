"""Config imports and WAV validation must survive an install without soundfile.

The lock file excludes soundfile on macOS arm64 and bare-pytest guard jobs
install only pytest. The config import chain reaches the TTS package, so no
audio library may be imported at module import time; a missing file must still
fail with the documented error before the optional import is attempted.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fixtures.pytest_env import scrub_pytest_env

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


def test_probe_wav_checks_file_before_importing_soundfile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Missing/zero-byte WAVs raise TtsError even with soundfile unavailable."""
    monkeypatch.setitem(sys.modules, "soundfile", None)

    from voice_typer.server.tts.types import TtsError
    from voice_typer.server.tts.wav import probe_wav

    with pytest.raises(TtsError, match="engine produced no audio"):
        probe_wav(tmp_path / "missing.wav")

    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(TtsError, match="engine produced no audio"):
        probe_wav(empty)


def test_probe_wav_translates_absent_soundfile_to_tts_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A non-empty WAV with soundfile absent raises TtsError, not ImportError."""
    monkeypatch.setitem(sys.modules, "soundfile", None)
    malformed = tmp_path / "malformed.wav"
    malformed.write_bytes(b"RIFF\x00\x00\x00\x00WAVEnot-a-real-wav")

    from voice_typer.server.tts.types import TtsError
    from voice_typer.server.tts.wav import probe_wav

    with pytest.raises(TtsError, match="unreadable WAV"):
        probe_wav(malformed)


def test_i18n_completeness_passes_without_soundfile(tmp_path: Path) -> None:
    """The CI-failing test file passes when soundfile cannot be imported."""
    (tmp_path / "sitecustomize.py").write_text("import sys\nsys.modules['soundfile'] = None\n", encoding="utf-8")
    env = scrub_pytest_env()
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
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
