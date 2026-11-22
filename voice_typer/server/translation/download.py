"""Repo-id download for the one ADR-0030 translation model.

Uses ``huggingface_hub.hf_hub_download`` with no ``cache_dir`` so the artifact
lands in the shared HF hub cache (``~/.cache/huggingface/hub``), exactly like
the ASR models — never in an Ollama blob dir and never in a dev scratch dir.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from voice_typer.server.asr_setup import ensure_hf_env
from voice_typer.server.translation.catalogue import TranslationModelSpec

log = logging.getLogger(__name__)


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
