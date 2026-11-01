"""Installer for the native runtimes the two TTS engines need.

A model pack is useless without its executable, and telling a user to drop
``audiocpp_server.exe`` into the Hugging Face folder by hand is not an install
flow. This module resolves each engine's current release archive from the
GitHub API (asset names embed the version, so a pinned URL would rot),
downloads it once, verifies the byte count, and unpacks it so the executable
lands exactly where :mod:`voice_typer.server.tts.paths` looks for it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from voice_typer.server.tts.paths import bin_dir
from voice_typer.server.tts.types import TtsError

_API = "https://api.github.com/repos/{repo}/releases/latest"
_CHUNK = 1 << 20


@dataclass(frozen=True)
class RuntimeRelease:
    """One engine's release source plus the executable to install from it."""

    repo: str
    asset_pattern: str
    exe_name: str


RELEASES: dict[str, RuntimeRelease] = {
    # Vulkan build: drives NVIDIA/AMD/Intel through the Vulkan driver, which is
    # the backend the Audio8 engine spec asks for by default.
    "audio8": RuntimeRelease(
        repo="0xShug0/audio.cpp",
        asset_pattern=r"^audio-v[\d.]+-bin-windows-x64-vulkan\.zip$",
        exe_name="audiocpp_server.exe",
    ),
    # CPU build: the app bundles no CUDA redistributables, and the CPU build
    # already renders Magpie faster than playback on this class of machine.
    "magpie": RuntimeRelease(
        repo="NVIDIA/NeMo-Speech.cpp",
        asset_pattern=r"^nemo-speech-[\d.]+-windows-x86_64-cpu\.zip$",
        exe_name="nemo-speech.exe",
    ),
}


def _safe_member(name: str) -> bool:
    """Reject archive entries that could land outside the staging directory."""
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts


def _latest_asset(release: RuntimeRelease) -> dict[str, object]:
    """Resolve the newest matching release asset for ``release``."""
    request = Request(
        _API.format(repo=release.repo),
        headers={"Accept": "application/vnd.github+json"},
    )
    try:
        with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed https host
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise TtsError(f"cannot resolve the latest {release.repo} release: {exc}") from exc
    pattern = re.compile(release.asset_pattern)
    for asset in payload.get("assets", []):
        if pattern.match(str(asset.get("name", ""))):
            return asset
    raise TtsError(f"no asset matching {release.asset_pattern} in {release.repo}")


def _download(asset: dict[str, object], target: Path) -> Path:
    """Download ``asset`` to ``target``, verifying the publisher's byte count."""
    url = str(asset["browser_download_url"])
    expected = int(asset["size"])
    partial = target.with_suffix(target.suffix + ".partial")
    # The engine's bin directory may not exist yet on a fresh install.
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with urlopen(url, timeout=300) as response, partial.open("wb") as out:  # noqa: S310
            while chunk := response.read(_CHUNK):
                out.write(chunk)
                written += len(chunk)
    except (HTTPError, URLError, TimeoutError) as exc:
        partial.unlink(missing_ok=True)
        raise TtsError(f"runtime download failed: {exc}") from exc
    if written != expected:
        partial.unlink(missing_ok=True)
        raise TtsError(f"runtime download truncated: {written} != {expected} bytes")
    partial.replace(target)
    return target


def install_from_archive(archive: Path, dest: Path, *, exe_name: str) -> Path:
    """Unpack ``archive`` so ``exe_name`` and its DLLs sit directly in ``dest``."""
    staging = dest / "._unpack"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.namelist():
                if not _safe_member(member):
                    raise TtsError(f"unsafe path in runtime archive: {member}")
            bundle.extractall(staging)
        matches = sorted(staging.rglob(exe_name))
        if not matches:
            raise TtsError(f"runtime archive does not contain {exe_name}")
        exe_dir = matches[0].parent
        # audio.cpp ships a FLAT archive (exe at the root) with ``model_specs``
        # beside it; other builds nest both under ``bin/``. Resolve the specs
        # directory before the move, otherwise a flat archive makes
        # ``exe_dir.parent`` the destination and the move targets itself.
        specs_src = next(
            (p for p in (exe_dir / "model_specs", exe_dir.parent / "model_specs") if p.is_dir()),
            None,
        )
        dest.mkdir(parents=True, exist_ok=True)
        for item in exe_dir.iterdir():
            if specs_src is not None and item == specs_src:
                continue
            target = dest / item.name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            shutil.move(str(item), str(target))
        if specs_src is not None:
            target = dest / "model_specs"
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(specs_src), str(target))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    installed = dest / exe_name
    if not installed.is_file():
        raise TtsError(f"runtime install incomplete: {installed} missing")
    return installed


def install(engine: str) -> Path:
    """Install ``engine``'s runtime into the HF folder and return its path.

    Idempotent: an executable already in place short-circuits before any
    network call, so a repeated ``tts_prepare`` costs nothing.
    """
    release = RELEASES.get(engine)
    if release is None:
        raise TtsError(f"unknown tts engine: {engine}")
    dest = bin_dir(engine)
    existing = dest / release.exe_name
    if existing.is_file():
        return existing
    if os.name != "nt":
        raise TtsError(
            f"no prebuilt {engine} runtime for this platform; "
            "set the binary path env var instead"
        )
    asset = _latest_asset(release)
    archive = dest / f".{asset['name']}"
    try:
        _download(asset, archive)
        return install_from_archive(archive, dest, exe_name=release.exe_name)
    finally:
        archive.unlink(missing_ok=True)
