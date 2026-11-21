"""Python-side guard that no blanket ``ignore::ResourceWarning``"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests.fixtures.pytest_env import scrub_pytest_env

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


def test_no_blanket_resource_warning_filter() -> None:
    """No line in ``pyproject.toml`` may start with ``\"ignore::ResourceWarning\"``."""
    text = PYPROJECT_PATH.read_text(encoding="utf-8")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith('"ignore::ResourceWarning"'):
            msg = f"Blanket 'ignore::ResourceWarning' filter found at pyproject.toml:{lineno}: {stripped}"
            raise AssertionError(msg)


def test_norecursedirs_includes_hypothesis() -> None:
    """``norecursedirs`` in ``pyproject.toml`` MUST include ``.hypothesis``."""
    text = PYPROJECT_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    # Find the ``norecursedirs = [...]`` line. It's a single-line TOML
    norecursedirs_lines = [(idx + 1, raw) for idx, raw in enumerate(lines) if raw.lstrip().startswith("norecursedirs")]
    assert norecursedirs_lines, "norecursedirs key missing from pyproject.toml"
    lineno, line = norecursedirs_lines[0]
    assert ".hypothesis" in line, (
        f"'.hypothesis' must be listed in norecursedirs (pyproject.toml:{lineno}) "
        f"to suppress the hypothesis pytest plugin's 'Skipping collection of "
        f".hypothesis' UserWarning. Current value: {line.strip()}"
    )


def test_filterwarnings_has_voice_typer_deprecation_ratchet() -> None:
    """``filterwarnings`` MUST include ``\"error::DeprecationWarning:voice_typer\"``."""
    text = PYPROJECT_PATH.read_text(encoding="utf-8")
    assert '"error::DeprecationWarning:voice_typer"' in text, (
        "filterwarnings must include the literal string "
        "'error::DeprecationWarning:voice_typer' to ratchet "
        "voice_typer-originated DeprecationWarnings into errors. "
        "Without it, a regressed deprecation passes silently."
    )


def test_no_filterwarnings_reference_optional_plugin() -> None:
    """No filterwarnings entry may name a module a bare pytest cannot import."""
    data = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    filters = data["tool"]["pytest"]["ini_options"]["filterwarnings"]
    for entry in filters:
        assert not entry.startswith("ignore::pytest_benchmark."), (
            f"filterwarnings entry {entry!r} references pytest_benchmark, which is "
            "absent in bare-pytest jobs; pytest then warns PytestConfigWarning "
            "on every test. No plugin-specific filter; keep bare pytest importable."
        )


def test_bare_pytest_emits_no_benchmark_filter_warning(tmp_path: Path) -> None:
    """A pytest that cannot import pytest_benchmark emits no PytestConfigWarning."""
    stub = tmp_path / "pytest_benchmark"
    stub.mkdir()
    (stub / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "test_smoke.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    env = scrub_pytest_env()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join([str(tmp_path), existing]) if existing else str(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--no-cov",
            "-p",
            "no:benchmark",
            "-p",
            "no:cacheprovider",
            "-c",
            str(PYPROJECT_PATH),
            "test_smoke.py",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "PytestConfigWarning" not in result.stdout + result.stderr


def test_hypothesis_ci_profile_loaded_with_deadline_none() -> None:
    """The ``ci`` hypothesis profile MUST be registered with ``deadline=None``."""
    hypothesis = pytest.importorskip("hypothesis", reason="hypothesis not installed")
    settings = hypothesis.settings

    # (1) The ``ci`` profile is registered.
    registered_profiles = settings._profiles
    assert "ci" in registered_profiles, (
        "hypothesis 'ci' profile is not registered, "
        "tests/conftest.py:pytest_configure must call "
        "settings.register_profile('ci', deadline=None, ...). "
        f"Registered profiles: {sorted(registered_profiles)!r}"
    )

    # (2) The ``ci`` profile's deadline is None.
    ci_settings = settings.get_profile("ci")
    assert ci_settings.deadline is None, (
        f"hypothesis 'ci' profile must have deadline=None; "
        f"got deadline={ci_settings.deadline!r}. "
        "tests/conftest.py:pytest_configure must register the profile "
        "with deadline=None."
    )

    assert settings._current_profile == "ci", (
        f"hypothesis 'ci' profile is registered but not loaded, "
        f"current profile is {settings._current_profile!r}. "
        "tests/conftest.py:pytest_configure must call "
        "settings.load_profile('ci') after register_profile."
    )
