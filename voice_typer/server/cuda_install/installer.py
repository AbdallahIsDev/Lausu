"""Extract verified wheels into the app-data mini site-packages.

The install is only "complete" when the marker lists every pinned artifact by
hash AND the DLLs a GPU backend needs are physically present; anything less
stays an install that the activation step refuses to switch to.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path

from voice_typer.server.cuda_install.manifest import (
    REQUIRED_DLLS,
    REQUIRED_ORT_FILES,
    Artifact,
)
from voice_typer.server.cuda_install.paths import install_dir, staging_dir

log = logging.getLogger(__name__)

MARKER_NAME = "install-manifest.json"


class InstallError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def marker_path() -> Path:
    return install_dir() / MARKER_NAME


def installed_artifacts() -> dict[str, str]:
    """``{filename: sha256}`` from the last successful install ({} when none)."""
    try:
        data = json.loads(marker_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    artifacts = data.get("artifacts") if isinstance(data, dict) else None
    if not isinstance(artifacts, dict):
        return {}
    return {str(k): str(v) for k, v in artifacts.items()}


def is_installed(artifacts: tuple[Artifact, ...]) -> bool:
    """True when every pinned artifact is recorded with its pinned hash."""
    if not artifacts:
        return False
    recorded = installed_artifacts()
    return all(recorded.get(a.filename) == a.sha256 for a in artifacts)


def verify_layout() -> list[str]:
    """Names of required files that are missing from the install."""
    root = install_dir()
    if not root.is_dir():
        return [*REQUIRED_DLLS, *REQUIRED_ORT_FILES]
    present = {p.name.lower() for p in root.rglob("*") if p.is_file()}
    missing = [name for name in REQUIRED_DLLS if name.lower() not in present]
    missing.extend(name for name in REQUIRED_ORT_FILES if name.lower() not in present)
    return missing


def install(artifacts: tuple[Artifact, ...], wheels: dict[str, Path]) -> None:
    """Extract every wheel into the install dir, then write the marker."""
    if not artifacts:
        raise InstallError("unsupported_runtime")
    root = install_dir()
    root.mkdir(parents=True, exist_ok=True)
    scratch = staging_dir() / f"extract-{os.getpid()}-{int(time.time())}"
    shutil.rmtree(scratch, ignore_errors=True)
    try:
        for artifact in artifacts:
            wheel = wheels.get(artifact.key)
            if wheel is None:
                raise InstallError("missing_wheel", artifact.filename)
            _extract_wheel(wheel, scratch)
        _merge_tree(scratch, root)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    missing = verify_layout()
    if missing:
        raise InstallError("incomplete_install", ", ".join(sorted(missing)))
    _write_marker(artifacts)


def _extract_wheel(wheel: Path, target: Path) -> None:
    try:
        archive = zipfile.ZipFile(wheel)
    except (OSError, zipfile.BadZipFile) as exc:
        raise InstallError("corrupt_wheel", wheel.name) from exc
    with archive:
        for member in archive.infolist():
            name = member.filename
            if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                raise InstallError("unsafe_wheel_path", name)
            if member.is_dir():
                continue
            archive.extract(member, target)


def _merge_tree(source: Path, target: Path) -> None:
    for entry in source.iterdir():
        destination = target / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, destination)


def _write_marker(artifacts: tuple[Artifact, ...]) -> None:
    path = marker_path()
    payload = {
        "artifacts": {a.filename: a.sha256 for a in artifacts},
        "installed_at": time.time(),
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)
