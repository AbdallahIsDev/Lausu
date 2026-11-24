"""Consent-gated, verified download for GGUF ASR weights.

Mirrors the translation model flow: the file lands in the shared Hugging Face
cache, is checked for exact byte size and SHA-256, and inference only ever
resolves it with ``local_files_only=True``. Placeholder hashes refuse the
download instead of silently accepting an unverified file.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from voice_typer.server.asr_setup import ensure_hf_env
from voice_typer.server.gguf_model_registry import (
    GgufModelSpec,
    is_frozen as _frozen,
    is_placeholder_hash,
    is_placeholder_size,
    require_complete_spec,
    resolve_gguf_spec,
)

log = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_gguf_model_path(model_key: str) -> Path | None:
    """Local-only lookup used at inference. Never touches the network."""
    spec = resolve_gguf_spec(model_key)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return None
    try:
        path = Path(
            hf_hub_download(
                repo_id=spec.repo_id,
                filename=spec.filename,
                local_files_only=True,
            )
        )
    except Exception:
        log.debug("[GGUF] model %s not in local cache", model_key, exc_info=True)
        return None
    return path if path.is_file() else None


def download_gguf_model(
    model_key: str,
    *,
    progress_callback: Callable[[str], None] | None = None,
    config: Any = None,
) -> tuple[bool, str]:
    """Download + verify one GGUF model. Returns (ok, failure_code)."""
    spec: GgufModelSpec = resolve_gguf_spec(model_key)
    if spec.dev_only and _frozen():
        log.error("[GGUF] refused dev-only model %s in a frozen build", model_key)
        return (False, "dev_model_not_allowed")

    def report(message: str) -> None:
        log.info("[GGUF] %s: %s", model_key, message)
        if progress_callback:
            progress_callback(message)

    if is_placeholder_hash(spec.sha256) or is_placeholder_size(spec.size_bytes):
        log.error("[GGUF] %s has a placeholder hash/size; refusing to download", model_key)
        return (False, "placeholder_in_registry")

    if config is None or not bool(getattr(config, "huggingface_consent", False)):
        report("huggingface_consent_false")
        return (False, "huggingface_consent_false")

    require_complete_spec(spec)
    ensure_hf_env()
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        return (False, "huggingface_hub_missing")

    try:
        cached = Path(
            hf_hub_download(
                repo_id=spec.repo_id,
                filename=spec.filename,
                local_files_only=True,
            )
        )
        if cached.is_file() and cached.stat().st_size == spec.size_bytes and _sha256(cached) == spec.sha256:
            report("already cached")
            return (True, "")
    except Exception:
        log.debug("[GGUF] cache probe missed; downloading", exc_info=True)

    report(f"downloading {spec.filename}")
    try:
        downloaded = Path(hf_hub_download(repo_id=spec.repo_id, filename=spec.filename))
    except Exception:
        log.exception("[GGUF] download failed for %s", spec.repo_id)
        return (False, "download_failed")

    if downloaded.stat().st_size != spec.size_bytes:
        return (False, "size_mismatch")
    if _sha256(downloaded) != spec.sha256:
        return (False, "sha256_mismatch")
    report("downloaded and verified")
    return (True, "")
