"""regression guard for requirements-lock.txt completeness."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
LOCKFILE = REPO_ROOT / "requirements-lock.txt"


def _normalize(name: str) -> str:
    """normalisation: ``keyring-foo`` → ``keyring-foo`` (already canonical)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _marker_applies_current_platform(marker_str: str) -> bool:
    """Return True if a PEP 508 environment marker matches the running platform."""
    if not marker_str.strip():
        return True  # no marker → always applies
    try:
        from packaging.markers import Marker  # type: ignore[import-not-found]

        return Marker(marker_str).evaluate()
    except ImportError:  # pragma: no cover, packaging is a pip dep
        # Naive fallback: handle the common ``sys_platform == 'X'`` case.
        m = re.search(r"sys_platform\s*==\s*['\"]([^'\"]+)['\"]", marker_str)
        if m:
            return sys.platform == m.group(1)
        return True


def _direct_deps() -> set[str]:
    """Return the set of canonical names declared in pyproject.toml [project.dependencies]."""
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    deps_raw: list[str] = data.get("project", {}).get("dependencies", [])
    names: set[str] = set()
    for line in deps_raw:
        # Strip environment markers + version specifiers.
        m = re.match(r"^\s*([A-Za-z0-9_.-]+)", line)
        if m:
            names.add(_normalize(m.group(1)))
    return names


def _direct_deps_for_current_platform() -> set[str]:
    """Return direct deps whose environment marker matches the current platform."""
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    deps_raw: list[str] = data.get("project", {}).get("dependencies", [])
    names: set[str] = set()
    for line in deps_raw:
        # Split off the environment marker (everything after the first ``;``).
        if ";" in line:
            dep_part, marker_part = line.split(";", 1)
        else:
            dep_part, marker_part = line, ""
        if not _marker_applies_current_platform(marker_part):
            continue
        m = re.match(r"^\s*([A-Za-z0-9_.-]+)", dep_part)
        if m:
            names.add(_normalize(m.group(1)))
    return names


def _lockfile_pinned_names() -> set[str]:
    """Return the set of canonical names that appear as ``<name>==<version>`` in the lockfile."""
    with LOCKFILE.open("r", encoding="utf-8") as fh:
        text = fh.read()
    # ``websockets==13.1 \`` → captures ``websockets``
    names: set[str] = set()
    for m in re.finditer(r"^([A-Za-z0-9_.-]+)==[A-Za-z0-9.+!]+", text, re.MULTILINE):
        names.add(_normalize(m.group(1)))
    return names


def test_every_direct_dep_is_pinned_in_lockfile() -> None:
    """Every dep declared in pyproject.toml MUST have a pinned entry in the lockfile."""
    direct = _direct_deps_for_current_platform()
    pinned = _lockfile_pinned_names()
    missing = direct - pinned
    assert not missing, (
        "regression: these pyproject.toml direct dependencies are MISSING from "
        "requirements-lock.txt (the `pip install --require-hashes` flow would install "
        "successfully but the runtime would crash with ModuleNotFoundError):\n  "
        + "\n  ".join(sorted(missing))
        + "\n\nFix: add the missing entries to requirements-lock.txt with sha256 hashes "
        "(run `uv pip compile --generate-hashes --universal --python-version 3.12 "
        "pyproject.toml -o requirements-lock.txt` or "
        "add them manually with `pip download <pkg>==<ver> --no-deps -d /tmp/whl "
        "&& pip hash /tmp/whl/*.whl`)."
    )


def test_known_critical_deps_are_pinned() -> None:
    """Targeted sentinel test for the two deps that were missing in H-20."""
    pinned = _lockfile_pinned_names()
    assert "websockets" in pinned, (
        "regression: `websockets` is missing from requirements-lock.txt. "
        "sidecar_ws.py imports it for the Tauri WS transport (ADR-0020 §14)."
    )
    assert "keyring" in pinned, (
        "regression: `keyring` is missing from requirements-lock.txt. "
        "credential_store.py imports it for OS-native credential storage."
    )


def _pyproject_dep_specifiers() -> dict[str, list[tuple[str, str]]]:
    """Return ``{normalized_name: [(specifier_str, marker_str)]}``.

    One entry per declared line: a package with a platform split (e.g.
    cryptography's Intel-Mac pin) yields two entries with different markers.
    """
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    deps_raw: list[str] = data.get("project", {}).get("dependencies", [])
    out: dict[str, list[tuple[str, str]]] = {}
    for line in deps_raw:
        # Split off environment markers.
        if ";" in line:
            dep_part, marker_part = line.split(";", 1)
        else:
            dep_part, marker_part = line, ""
        # ``"psutil>=5.9,<8.0"`` → name="psutil", spec=">=5.9,<8.0".
        m = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*(.*)$", dep_part)
        if not m:
            continue
        name = _normalize(m.group(1))
        spec = m.group(2).strip()
        if spec:
            out.setdefault(name, []).append((spec, marker_part.strip()))
    return out


def _lockfile_pinned_versions() -> dict[str, list[tuple[str, str]]]:
    """
    Return ``{normalized_name: [(pinned_version, marker_str)]}`` for every
    ``<name>==<version>[; markers]`` stanza header. ALL pins per package are
    recorded (a platform split legitimately pins several versions).
    """
    with LOCKFILE.open("r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out: dict[str, list[tuple[str, str]]] = {}
    for line in lines:
        m = re.match(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9.+!]+)\s*(?:;\s*(.*?))?\s*\\?\s*$", line)
        if not m:
            continue
        name = _normalize(m.group(1))
        out.setdefault(name, []).append((m.group(2), (m.group(3) or "").strip()))
    return out


_EVAL_ENVS: list[dict[str, str]] = [
    {
        "implementation_name": "cpython",
        "os_name": os_name,
        "platform_machine": machine,
        "platform_system": system,
        "python_version": py,
        "python_full_version": f"{py}.0",
        "sys_platform": platform,
    }
    for platform, os_name, system in (
        ("win32", "nt", "Windows"),
        ("linux", "posix", "Linux"),
        ("darwin", "posix", "Darwin"),
    )
    for machine in ("x86_64", "arm64")
    for py in ("3.11", "3.12", "3.13")
]


def test_lockfile_pinned_versions_satisfy_pyproject_constraints() -> None:
    """Every lockfile pin MUST satisfy the version specifier in pyproject.toml.

    Marker-aware per environment: each pyproject entry is checked against
    the lockfile pins that apply in the SAME matrix cell (uv unions extra
    bounds like ``python_full_version < '3.15'`` into pin markers, so raw
    string equality between spec and pin markers never holds).
    """
    try:
        from packaging.markers import Marker
        from packaging.specifiers import SpecifierSet
        from packaging.version import Version
    except ImportError:  # pragma: no cover, packaging is a pip dep
        pytest.skip("packaging library not available, cannot check version constraints")

    def _holds(marker_str: str, env: dict[str, str]) -> bool:
        if not marker_str.strip():
            return True
        return Marker(marker_str).evaluate(environment=env)

    specs = _pyproject_dep_specifiers()
    pins = _lockfile_pinned_versions()
    violations: list[str] = []
    for env in _EVAL_ENVS:
        env_label = f"{env['sys_platform']}/{env['platform_machine']}/py{env['python_version']}"
        for name, entries in sorted(specs.items()):
            for spec_str, spec_marker in entries:
                if not _holds(spec_marker, env):
                    continue
                candidates = [pin for pin, pin_marker in pins.get(name, []) if _holds(pin_marker, env)]
                if not candidates:
                    # Completeness is checked by test_every_direct_dep_is_pinned_in_lockfile.
                    continue
                try:
                    spec = SpecifierSet(spec_str)
                    versions = [Version(pin) for pin in candidates]
                except Exception as exc:  # pragma: no cover, defensive parse
                    violations.append(f"  [{env_label}] {name}: failed to parse spec={spec_str!r} ({exc})")
                    continue
                if not any(ver in spec for ver in versions):
                    violations.append(
                        f"  [{env_label}] {name}: lockfile pins {candidates} "
                        f"but pyproject.toml requires {spec_str}"
                    )
    assert not violations, (
        "Lockfile drift detected, the lockfile pin violates the version "
        "specifier declared in pyproject.toml. CI (which resolves from "
        "pyproject.toml) and the documented `pip install --require-hashes "
        "-r requirements-lock.txt` path now install DIFFERENT versions. "
        "Regenerate the lockfile with:\n"
        "  uv pip compile --generate-hashes --universal --python-version 3.12 "
        "pyproject.toml -o requirements-lock.txt\n\nViolations:\n" + "\n".join(violations)
    )


def test_lockfile_psutil_pin_matches_pyproject_constraint() -> None:
    """Sentinel test for the psutil major-version drift class."""
    try:
        import psutil
    except ImportError:  # pragma: no cover, psutil is a hard dep
        pytest.skip("psutil not installed in this environment")
    installed = psutil.__version__
    pins = _lockfile_pinned_versions()
    psutil_pins = pins.get("psutil") or []
    pinned = psutil_pins[0][0] if psutil_pins else None
    assert pinned is not None, (
        "psutil is missing from requirements-lock.txt, the reproducible-build "
        "path would crash with ModuleNotFoundError on the first "
        "`_another_voice_typer_alive` call."
    )
    assert pinned == installed, (
        f"psutil version drift: requirements-lock.txt pins psutil=={pinned} "
        f"but the live venv has psutil=={installed}. CI resolves from "
        f"pyproject.toml (picking {installed}) while the documented "
        f"`pip install --require-hashes -r requirements-lock.txt` path "
        f"would install {pinned}. Regenerate the lockfile with "
        f"`uv pip compile --generate-hashes --universal "
        f"--python-version 3.12 pyproject.toml -o requirements-lock.txt`."
    )


if __name__ == "__main__":
    # Manual run: ``python tests/test_requirements_lock_completeness.py``
    test_every_direct_dep_is_pinned_in_lockfile()
    test_known_critical_deps_are_pinned()
    test_lockfile_pinned_versions_satisfy_pyproject_constraints()
    test_lockfile_psutil_pin_matches_pyproject_constraint()
    print("OK: all direct deps are pinned in requirements-lock.txt (no drift)")
