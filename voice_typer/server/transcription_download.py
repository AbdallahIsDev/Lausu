"""Model download for transcription."""

from __future__ import annotations

import logging
import threading

from voice_typer.server.asr_errors import (
    ModelIntegrityError,
    ModelNotDownloadedError,
)

# Use the ``transcription`` logger name so log records emitted from this
log = logging.getLogger("voice_typer.server.transcription")

_offline_probe_log_gate: set[tuple[str, str, str]] = set()
_offline_probe_log_lock = threading.Lock()


def _is_expected_offline_probe_error(exc: BaseException) -> bool:
    """True when *exc* is the routine offline cache-miss from a local-only probe."""
    try:
        from huggingface_hub.errors import CacheNotFound, EntryNotFoundError
    except ImportError:
        return False
    return isinstance(exc, (EntryNotFoundError, CacheNotFound))


def _log_offline_probe_miss_once(
    probe_kind: str,
    key: str,
    exc: BaseException,
    message: str,
) -> None:
    """Log a routine offline miss once per probe+key+exception type.

    Status/tray polling re-probes the same cache every few minutes; only the
    first miss carries information, repeats are pure noise.
    """
    gate_key = (probe_kind, key, type(exc).__name__)
    with _offline_probe_log_lock:
        if gate_key in _offline_probe_log_gate:
            return
        _offline_probe_log_gate.add(gate_key)
    log.debug(message, key, exc)


def resolve_whisper_repo_id(model_size: str) -> str:
    """Resolve HF repo for a whisper ``model_size`` via MODEL_REGISTRY."""
    try:
        from voice_typer.server.model_registry import get_model_metadata

        meta = get_model_metadata(model_size)
        if meta is not None and meta.repo_id:
            return meta.repo_id
    except Exception:
        log.debug(
            "[MODEL] model_registry lookup failed for %s; falling back to Systran default",
            model_size,
            exc_info=True,
        )
    return f"Systran/faster-whisper-{model_size}"


def whisper_model_ref(model_size: str) -> tuple[str, str]:
    """Canonical ``(repo_id, revision)`` so faster-whisper loads OUR cache dir.

    Passing the bare size name makes faster-whisper resolve its own alias map,
    which can point at a renamed repo and miss the snapshot this app downloaded.
    """
    repo_id = resolve_whisper_repo_id(model_size)
    from voice_typer.server.security import MODEL_HASHES

    revision = MODEL_HASHES.get(repo_id, {}).get("revision", "main")
    return repo_id, revision


def probe_cache(
    engine,
    snapshot_download_fn,
    repo_id: str,
    revision: str,
    allow_patterns,
    model_size: str,
    progress_callback=None,
) -> tuple[str | None, bool]:
    """Step 1: probe the HuggingFace cache (local-only).

    Returns ``(local_dir, integrity_failed)``:
    """
    try:
        local_dir = snapshot_download_fn(
            repo_id=repo_id,
            revision=revision,
            allow_patterns=allow_patterns,
            local_files_only=True,
        )
    except Exception as exc:
        if _is_expected_offline_probe_error(exc):
            _log_offline_probe_miss_once(
                "probe_cache",
                repo_id,
                exc,
                "[MODEL] HF cache probe miss for %s: %s",
            )
        else:
            log.debug("[MODEL] HF cache probe failed, will attempt download", exc_info=True)
        return None, False

    from voice_typer.server.security import verify_model_integrity

    if not verify_model_integrity(local_dir, repo_id):
        log.error(
            "[MODEL] Cached model '%s' failed integrity check (cache hit path), "
            "refusing to load tampered files (no automatic deletion).",
            model_size,
        )
        if progress_callback:
            progress_callback("Cached model failed integrity check; delete and re-download from the Models page.")
        return None, True

    return local_dir, False


def require_model_downloaded(engine, model_size: str, progress_callback=None) -> None:
    """Ensure the Whisper model is present in the local HF cache."""
    from voice_typer.server.model_registry import get_model_metadata

    model_meta = get_model_metadata(model_size) if model_size else None
    # Non-Whisper backends own their own loader/availability checks.
    if not model_size or (model_meta is not None and model_meta.backend not in ("whisper", "distil-whisper")):
        log.debug(
            "[MODEL] Skipping download-required check for non-Whisper model '%s'",
            model_size,
        )
        return
    try:
        from huggingface_hub import snapshot_download

        repo_id, whisper_revision = whisper_model_ref(model_size)

        # Shared allow-pattern list (see ``_model_integrity``).
        from voice_typer.server._model_integrity import ALLOW_PATTERNS_WHISPER

        if progress_callback:
            progress_callback(f"Checking model cache for '{model_size}'...")
        local_dir, integrity_failed = engine._probe_cache(
            snapshot_download,
            repo_id,
            whisper_revision,
            ALLOW_PATTERNS_WHISPER,
            model_size,
            progress_callback=progress_callback,
        )
        if local_dir is not None and not integrity_failed:
            log.info("[MODEL] Model '%s' already cached (integrity verified)", model_size)
            return
        if integrity_failed:
            raise ModelIntegrityError(
                f"The cached model '{model_size}' failed integrity verification. "
                "Delete it and download it again from the Models page to recover.",
                model_size=model_size,
                backend="whisper",
                repo_id=repo_id,
            )
        raise ModelNotDownloadedError(
            f"The Whisper model '{model_size}' is not downloaded yet. "
            "Open the Models page and click Download before using it.",
            model_size=model_size,
            backend="whisper",
            repo_id=repo_id,
        )
    except ImportError:
        # huggingface_hub unavailable, we cannot verify the cache, so
        raise ModelNotDownloadedError(
            f"The Whisper model '{model_size}' is not downloaded yet. "
            "Open the Models page and click Download before using it.",
            model_size=model_size,
            backend="whisper",
        ) from None


def whisper_size_cached(engine, model_size: str) -> bool:
    """Local-only probe: is ``model_size`` fully present in the HF cache?"""
    try:
        from huggingface_hub import snapshot_download

        repo_id, revision = whisper_model_ref(model_size)

        from voice_typer.server._model_integrity import ALLOW_PATTERNS_WHISPER

        snapshot_download(
            repo_id=repo_id,
            revision=revision,
            allow_patterns=ALLOW_PATTERNS_WHISPER,
            local_files_only=True,
        )
        return True
    except ImportError:
        # Cannot probe, allow the load attempt (WhisperModel will
        return True
    except Exception as exc:
        # Cache miss (or local probe failure), never auto-download. The
        if _is_expected_offline_probe_error(exc):
            _log_offline_probe_miss_once(
                "whisper_size_cached",
                model_size,
                exc,
                "[MODEL] whisper_size_cached probe miss for %s: %s",
            )
        else:
            log.debug("[MODEL] whisper_size_cached probe miss for %s", model_size, exc_info=True)
        return False


def is_model_snapshot_complete(repo_id: str) -> bool:
    """Local-only completeness probe: does the HF cache hold the FULL

    Returns ``False`` when ``huggingface_hub`` is unavailable, the
    """
    from voice_typer.server.config import _config_dir
    from voice_typer.server.model_availability import snapshot_search_dirs
    from voice_typer.server.qwen_layout import cached_qwen_model_dir, qwen_repo_ids

    if repo_id in qwen_repo_ids():
        # ONNX exports are only complete when the loader's own files exist;
        # the whisper allowlist below would never match *.onnx/*.data.
        return cached_qwen_model_dir(repo_id) is not None

    search_dirs = snapshot_search_dirs(_config_dir(), repo_id)
    if not any(d.is_dir() for d in search_dirs):
        # Never downloaded (or fully deleted), skip the hf probe.
        return False
    try:
        from huggingface_hub import snapshot_download

        from voice_typer.server._model_integrity import (
            ALLOW_PATTERNS_PARAKEET_ONNX,
            ALLOW_PATTERNS_WHISPER,
        )
        from voice_typer.server.asr_setup import ensure_hf_env
        from voice_typer.server.model_availability import app_hub_dir
        from voice_typer.server.security import MODEL_HASHES

        if "parakeet" in repo_id:
            allow_patterns: list[str] = sorted(ALLOW_PATTERNS_PARAKEET_ONNX)
        else:
            allow_patterns = list(ALLOW_PATTERNS_WHISPER)
        revision = MODEL_HASHES.get(repo_id, {}).get("revision", "main")

        ensure_hf_env()
        try:
            snapshot_download(
                repo_id=repo_id,
                revision=revision,
                allow_patterns=allow_patterns,
                local_files_only=True,
            )
            return True
        except Exception:
            pass
        snapshot_download(
            repo_id=repo_id,
            revision=revision,
            allow_patterns=allow_patterns,
            local_files_only=True,
            cache_dir=str(app_hub_dir(_config_dir())),
        )
        return True
    except Exception as exc:
        # Incomplete snapshot (missing files), cache-schema mismatch, or
        if _is_expected_offline_probe_error(exc):
            _log_offline_probe_miss_once(
                "is_model_snapshot_complete",
                repo_id,
                exc,
                "[MODEL] is_model_snapshot_complete probe miss for %s: %s",
            )
        else:
            log.debug("[MODEL] is_model_snapshot_complete probe miss for %s", repo_id, exc_info=True)
        return False
