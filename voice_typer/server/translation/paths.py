"""Canonical storage locations for the translation model and its runtime.

Both assets follow the app's existing HF-hub / installer-bundle architecture:

* the GGUF lives in the SHARED HuggingFace hub cache
  (``~/.cache/huggingface/hub``), addressed by its repo id — never inside an
  Ollama blob dir and never in a developer scratch directory;
* ``llama-server`` is an installer-bundled binary found via the same shipped
  directory search the ffmpeg sidecar uses (exe-adjacent, ``resources/``,
  parent chain, onefile extraction), with the writable app-data dir as the
  last fallback.

Dev overrides (``LAUSU_TRANSLATION_MODEL`` / ``LAUSU_TRANSLATION_RUNTIME``)
stay as escape hatches for local experiments but are NOT the default path.
"""

from __future__ import annotations

import os
from pathlib import Path

from voice_typer.server._paths import config_dir
from voice_typer.server.model_availability import app_hub_dir, shared_hub_dir
from voice_typer.server.platform_utils import is_windows
from voice_typer.server.translation.catalogue import TranslationModelSpec

MODEL_ENV = "LAUSU_TRANSLATION_MODEL"
RUNTIME_ENV = "LAUSU_TRANSLATION_RUNTIME"

RUNTIME_BASENAME = "llama-server.exe" if is_windows() else "llama-server"


def _snapshot_leaf(repo_id: str) -> str:
    return f"models--{repo_id.replace('/', '--')}"


def hub_search_dirs(spec: TranslationModelSpec) -> list[Path]:
    """HF hub roots to search, shared cache first, app-local legacy second."""
    leaf = _snapshot_leaf(spec.repo_id)
    return [shared_hub_dir() / leaf, app_hub_dir(config_dir()) / leaf]


def _candidate_files(root: Path, filename: str) -> list[Path]:
    """Both HF snapshot layouts: ``snapshots/<rev>/<file>`` and flat blobs."""
    out: list[Path] = []
    snapshots = root / "snapshots"
    if snapshots.is_dir():
        out.extend(sorted(snapshots.glob(f"*/{filename}")))
    flat = root / filename
    if flat.is_file():
        out.append(flat)
    return [p for p in out if p.is_file()]


def resolve_model_path(spec: TranslationModelSpec, config: object) -> Path | None:
    """Resolve the GGUF from HF cache; explicit dev overrides win.

    Order: config path → env override → shared HF hub → app-local hub legacy.
    Never returns a path into an Ollama blob directory by default.
    """
    configured = str(getattr(config, "translation_model_path", "") or "")
    for raw in (configured, os.environ.get(MODEL_ENV, "")):
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_dir():
            candidate = path / spec.filename
            if candidate.is_file():
                return candidate
        elif path.is_file():
            return path

    for root in hub_search_dirs(spec):
        candidates = _candidate_files(root, spec.filename)
        if candidates:
            return candidates[0]
    return None


def model_is_available(spec: TranslationModelSpec, config: object | None = None) -> bool:
    """True when the GGUF is on disk in the HF cache (or explicit override)."""
    cfg = config if config is not None else _default_config()
    return resolve_model_path(spec, cfg) is not None


def _default_config() -> object:
    from voice_typer.server.config import Config

    return Config.load()


def runtime_search_dirs() -> list[Path]:
    """Installer-bundled binary locations, same order as the ffmpeg resolver."""
    from voice_typer.server.media_ingest.ffmpeg_binaries import _shipped_dirs

    dirs = list(_shipped_dirs())
    # A writable app-data location for manually installed / updated runtimes.
    dirs.append(config_dir() / "translation")
    seen: set[str] = set()
    unique: list[Path] = []
    for d in dirs:
        key = str(d).lower() if is_windows() else str(d)
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def resolve_runtime_path(config: object) -> Path | None:
    """Resolve llama-server from config, env, installer bundle, then app data."""
    configured = str(getattr(config, "translation_runtime_path", "") or "")
    for raw in (configured, os.environ.get(RUNTIME_ENV, "")):
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_file():
            return path
        if path.is_dir():
            candidate = path / RUNTIME_BASENAME
            if candidate.is_file():
                return candidate

    for directory in runtime_search_dirs():
        candidate = directory / RUNTIME_BASENAME
        if candidate.is_file():
            return candidate
    return None
