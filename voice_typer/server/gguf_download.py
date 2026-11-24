"""Consent-gated, verified download for GGUF ASR weights.

Mirrors the translation model flow: the file lands in the shared Hugging Face
cache, is checked for exact byte size and SHA-256, and inference only ever
resolves it with ``local_files_only=True``. Placeholder hashes refuse the
download instead of silently accepting an unverified file.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from voice_typer.server.asr_setup import ensure_hf_env
from voice_typer.server.gguf_model_registry import (
    GgufModelSpec,
    is_dev_only_model_key as _is_dev_only,
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


def _resolved_spec_or_error(model_key: str) -> tuple[GgufModelSpec | None, str]:
    """Resolve through the catalogue, refusing dev-only models without I/O."""
    try:
        spec = resolve_gguf_spec(model_key)
    except KeyError:
        # A dev-only key is absent from the frozen catalogue by definition.
        if _is_dev_only(model_key):
            return None, "dev_model_not_allowed"
        return None, "model_not_allowed"
    if spec.dev_only and _frozen():
        return None, "dev_model_not_allowed"
    return spec, ""


def resolve_gguf_model_path(model_key: str) -> Path | None:
    """Local-only lookup used at inference. Never touches the network."""
    spec, error = _resolved_spec_or_error(model_key)
    if spec is None:
        log.debug("[GGUF] model %s not selectable: %s", model_key, error)
        return None
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
        # A missing local file is the normal "not downloaded" verdict; a
        # traceback here floods every cold start with five HF stack dumps.
        log.debug("[GGUF] model %s not in local cache", model_key)
        return None
    return path if path.is_file() else None


def download_gguf_model(
    model_key: str,
    *,
    progress_callback: Callable[[str], None] | None = None,
    config: Any = None,
    tqdm_class: type | None = None,
) -> tuple[bool, str]:
    """Download + verify one GGUF model. Returns (ok, failure_code)."""
    spec, error = _resolved_spec_or_error(model_key)
    if spec is None:
        log.error("[GGUF] refused model %s in this build: %s", model_key, error)
        return (False, error)

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
        # Same expected local-only miss as resolve_gguf_model_path.
        log.debug("[GGUF] cache probe missed; downloading")

    report(f"downloading {spec.filename}")
    # The caller needs the real transport error to build the user-facing
    # message; a bare failure code hides DNS/offline detail. The pause/abort
    # gate lives in tqdm.update, so pass the gated class to the transfer.
    downloaded = Path(
        hf_hub_download(repo_id=spec.repo_id, filename=spec.filename, tqdm_class=tqdm_class)
    )

    if downloaded.stat().st_size != spec.size_bytes:
        return (False, "size_mismatch")
    if _sha256(downloaded) != spec.sha256:
        return (False, "sha256_mismatch")
    report("downloaded and verified")
    return (True, "")


def install_gguf_model_from_file(
    model_key: str, source: str | Path, *, cache_dir: str | Path | None = None
) -> tuple[bool, str]:
    """Install an already-downloaded GGUF into the same cache a download fills.

    Verification is the downloader's (exact byte size + SHA-256) and the commit
    is an atomic rename inside the Hugging Face cache layout, so inference's
    ``local_files_only`` lookup resolves the file without any network access.
    Returns ``(ok, failure_code)`` like :func:`download_gguf_model`.
    """
    spec, error = _resolved_spec_or_error(model_key)
    if spec is None:
        return (False, error)
    if is_placeholder_hash(spec.sha256) or is_placeholder_size(spec.size_bytes):
        return (False, "placeholder_in_registry")
    require_complete_spec(spec)
    origin = Path(source).expanduser()
    if not origin.is_file():
        return (False, "source_missing")
    if origin.stat().st_size != spec.size_bytes:
        return (False, "size_mismatch")
    if _sha256(origin) != spec.sha256:
        return (False, "sha256_mismatch")

    ensure_hf_env()
    from huggingface_hub.constants import HF_HUB_CACHE
    from huggingface_hub.file_download import _get_pointer_path

    cache = Path(cache_dir) if cache_dir is not None else Path(HF_HUB_CACHE)
    storage = cache / f"models--{spec.repo_id.replace('/', '--')}"
    revision = spec.sha256[:40]
    pointer = Path(_get_pointer_path(str(storage), revision, spec.filename))
    pointer.parent.mkdir(parents=True, exist_ok=True)
    (storage / "refs").mkdir(parents=True, exist_ok=True)

    def _commit(destination: Path, payload: bytes) -> None:
        handle, temporary = tempfile.mkstemp(prefix=".gguf-install-", dir=str(destination.parent))
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    handle, temporary = tempfile.mkstemp(prefix=".gguf-install-", dir=str(pointer.parent))
    try:
        with os.fdopen(handle, "wb") as target, origin.open("rb") as incoming:
            shutil.copyfileobj(incoming, target, length=1024 * 1024)
        os.replace(temporary, pointer)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    _commit(storage / "refs" / "main", revision.encode("ascii"))
    log.info("[GGUF] installed %s from a local file", model_key)
    return (True, "")
