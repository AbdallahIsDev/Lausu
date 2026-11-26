"""Repo-id download for the one ADR-0030 translation model.

Uses ``huggingface_hub.hf_hub_download`` with no ``cache_dir`` so the artifact
lands in the shared HF hub cache (``~/.cache/huggingface/hub``), exactly like
the ASR models — never in an Ollama blob dir and never in a dev scratch dir.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from voice_typer.server.asr_setup import ensure_hf_env
from voice_typer.server.asr_utils import _DISK_SPACE_MARGIN_MB, _disk_space_error
from voice_typer.server.translation.catalogue import TranslationModelSpec

log = logging.getLogger(__name__)

_MIB = 1024 * 1024


def _hub_cache_dir() -> Path | None:
    """Resolve the shared HF hub cache without importing huggingface_hub."""
    try:
        from huggingface_hub import constants

        return Path(constants.HF_HUB_CACHE)
    except (ImportError, AttributeError):
        try:
            return Path(os.path.expanduser("~")) / ".cache" / "huggingface" / "hub"
        except Exception:
            return None


def check_translation_disk_space(spec: TranslationModelSpec) -> None:
    """Require room for this catalogue artefact before any network call.

    The ASR threshold (``asr_utils._check_disk_space_for_download``) is
    deliberately untouched; only the shared message builder is reused.
    """
    cache_dir = _hub_cache_dir()
    if cache_dir is None:
        return
    try:
        available_mb = shutil.disk_usage(str(cache_dir)).free // _MIB
        size_mb = -(-spec.size_bytes // _MIB)
        required_mb = size_mb + _DISK_SPACE_MARGIN_MB
        if available_mb < required_mb:
            raise _disk_space_error(
                str(cache_dir),
                available_mb,
                required_mb,
                f"translation model {spec.label}",
                detail=f"model ~{size_mb} MB + {_DISK_SPACE_MARGIN_MB} MB margin",
            )
    except RuntimeError:
        raise
    except Exception as exc:
        log.debug("[TRANSLATE] disk space check skipped: %s", exc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_translation_weights(
    spec: TranslationModelSpec,
    *,
    progress_callback: Callable[[str], None] | None = None,
    config: Any = None,
    force: bool = False,
    tqdm_class: type | None = None,
) -> tuple[bool, str, tuple[type, BaseException, Any] | None]:
    """Download + integrity-check the GGUF into the shared HF hub cache."""
    if not force and (config is None or not bool(getattr(config, "huggingface_consent", False))):
        if progress_callback:
            progress_callback("huggingface_consent_false")
        return (False, "huggingface_consent_false", None)

    ensure_hf_env()
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        log.exception("[TRANSLATE] huggingface_hub missing; cannot download weights")
        return (False, "huggingface_hub_missing", None)

    def report(message: str) -> None:
        log.info("[TRANSLATE] %s", message)
        if progress_callback:
            progress_callback(message)

    report("Checking translation model cache...")
    try:
        cached = Path(
            hf_hub_download(
                repo_id=spec.repo_id,
                filename=spec.filename,
                local_files_only=True,
                tqdm_class=tqdm_class,
            )
        )
        if cached.is_file() and cached.stat().st_size == spec.size_bytes and _sha256(cached) == spec.sha256:
            report("Translation model already cached")
            return (True, "", None)
    except Exception:
        log.debug("[TRANSLATE] cache probe missed; downloading", exc_info=True)

    report(f"Downloading {spec.label} ({spec.size_bytes / 1_000_000_000:.2f} GB)...")
    try:
        downloaded = Path(
            hf_hub_download(
                repo_id=spec.repo_id,
                filename=spec.filename,
                tqdm_class=tqdm_class,
            )
        )
    except Exception as exc:
        log.exception("[TRANSLATE] download failed")
        return (False, "download_failed", (type(exc), exc, None))

    if downloaded.stat().st_size != spec.size_bytes:
        return (False, "size_mismatch", None)
    if _sha256(downloaded) != spec.sha256:
        return (False, "sha256_mismatch", None)

    report("Translation model downloaded")
    return (True, "", None)
