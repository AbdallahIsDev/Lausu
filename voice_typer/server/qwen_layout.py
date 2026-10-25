"""On-disk identity of a Qwen3-ASR ONNX export: variant, files, location."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Registry name -> decoder hidden size. ``decoder.hidden_size`` in the
# export's config.json is the only reliable variant marker (1.7B = 2048,
# 0.6B = 1024), so a hand-configured ``qwen_model_path`` can be matched to
# the variant the user selected.
VARIANT_HIDDEN_SIZES: dict[str, int] = {"qwen3-1.7b": 2048, "qwen3-0.6b": 1024}

#: Variant assumed when an override directory carries no readable
#: config.json (the 1.7B default).
DEFAULT_QWEN_VARIANT = "qwen3-1.7b"

_SESSION_SUFFIXES = (".int4.onnx", ".onnx")


def canonical_qwen_name(model_name: str) -> str | None:
    """Registry key for ``model_name``'s variant, or ``None`` if it isn't one.

    Pre-rename keys (``qwen`` / ``qwen-0.6b``) resolve through
    :data:`~voice_typer.server.model_registry.LEGACY_MODEL_ALIASES`.
    """
    from voice_typer.server.model_registry import LEGACY_MODEL_ALIASES

    name = LEGACY_MODEL_ALIASES.get(model_name, model_name)
    return name if name in VARIANT_HIDDEN_SIZES else None


def qwen_variant_names() -> tuple[str, ...]:
    """Registry names of every Qwen3-ASR variant the app can run."""
    return tuple(VARIANT_HIDDEN_SIZES)


def is_qwen_variant_name(model_name: str) -> bool:
    """True if ``model_name`` is a Qwen3-ASR variant registry key."""
    return canonical_qwen_name(model_name) is not None


def qwen_repo_id(model_name: str) -> str | None:
    """HuggingFace repo id of a Qwen variant (from ``MODEL_REGISTRY``)."""
    from voice_typer.server.model_registry import get_model_metadata

    meta = get_model_metadata(model_name)
    if meta is None or meta.backend != "qwen" or not meta.repo_id:
        return None
    return meta.repo_id


def qwen_repo_ids() -> tuple[str, ...]:
    """Every Qwen3-ASR HF repo id the app knows about."""
    return tuple(repo for repo in (qwen_repo_id(name) for name in VARIANT_HIDDEN_SIZES) if repo)


def read_decoder_hidden_size(config: dict[str, Any]) -> int | None:
    """Decoder width from an export ``config.json`` (``decoder.hidden_size``).

    The pre-exported ONNX repos put the width under ``decoder``; older
    layouts used ``text_config`` or the top level.
    """
    decoder = config.get("decoder")
    hidden = decoder.get("hidden_size") if isinstance(decoder, dict) else None
    if not isinstance(hidden, int) or hidden <= 0:
        text_config = config.get("text_config")
        candidate = text_config.get("hidden_size") if isinstance(text_config, dict) else None
        if not isinstance(candidate, int) or candidate <= 0:
            candidate = config.get("hidden_size")
        hidden = candidate if isinstance(candidate, int) and candidate > 0 else None
    return hidden


def read_dir_decoder_hidden_size(model_dir: str | Path) -> int | None:
    """Read the decoder width from ``<model_dir>/config.json`` (None if absent)."""
    config_path = Path(model_dir) / "config.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return read_decoder_hidden_size(raw) if isinstance(raw, dict) else None


def detect_qwen_variant(model_dir: str | Path) -> str | None:
    """Registry name of the variant in ``model_dir`` (None when unidentified)."""
    hidden = read_dir_decoder_hidden_size(model_dir)
    if hidden is None:
        return None
    for name, size in VARIANT_HIDDEN_SIZES.items():
        if size == hidden:
            return name
    return None


def is_complete_qwen_dir(model_dir: str | Path) -> bool:
    """True when ``model_dir`` holds every file the ONNX loader requires."""
    from voice_typer.server.qwen_onnx_model import is_onnx_model_dir

    path = Path(model_dir)
    if not is_onnx_model_dir(path):
        return False
    return all(
        any((path / f"{stem}{suffix}").is_file() for suffix in _SESSION_SUFFIXES)
        for stem in ("decoder_init", "decoder_step")
    )


def cached_qwen_model_dir(repo_id: str) -> Path | None:
    """Complete Qwen export of ``repo_id`` inside the HuggingFace caches."""
    from voice_typer.server.config import _config_dir
    from voice_typer.server.model_availability import snapshot_search_dirs
    from voice_typer.server.security import MODEL_HASHES

    pinned = (MODEL_HASHES.get(repo_id) or {}).get("revision")
    pinned_name = pinned if isinstance(pinned, str) and pinned else None
    for root in snapshot_search_dirs(_config_dir(), repo_id):
        snapshots = root / "snapshots"
        if not snapshots.is_dir():
            continue
        candidates: list[Path] = []
        if pinned_name:
            pinned_dir = snapshots / pinned_name
            if pinned_dir.is_dir():
                candidates.append(pinned_dir)
        try:
            candidates.extend(p for p in sorted(snapshots.iterdir()) if p.is_dir() and p.name != pinned_name)
        except OSError:
            continue
        for candidate in candidates:
            if is_complete_qwen_dir(candidate):
                return candidate
    return None


def override_matches_variant(model_name: str, override_path: str | None) -> bool:
    """True if a manual ``qwen_model_path`` holds ``model_name``'s variant."""
    if not isinstance(override_path, str) or not override_path:
        return False
    path = Path(override_path)
    if not path.is_dir():
        return False
    detected = detect_qwen_variant(path)
    if detected is None:
        return canonical_qwen_name(model_name) == DEFAULT_QWEN_VARIANT
    return detected == canonical_qwen_name(model_name)


def resolve_qwen_model_dir(model_name: str | None, override_path: str | None = None) -> str | None:
    """Directory to load for ``model_name``: the override, else the HF cache."""
    name = canonical_qwen_name(model_name) if isinstance(model_name, str) else None
    if name is None:
        name = DEFAULT_QWEN_VARIANT
    if override_matches_variant(name, override_path):
        return override_path
    repo_id = qwen_repo_id(name)
    if repo_id is None:
        return None
    cached = cached_qwen_model_dir(repo_id)
    if cached is None:
        log.debug("[QWEN] no complete %s export on disk (repo=%s)", name, repo_id)
        return None
    return str(cached)


__all__ = [
    "DEFAULT_QWEN_VARIANT",
    "VARIANT_HIDDEN_SIZES",
    "cached_qwen_model_dir",
    "canonical_qwen_name",
    "detect_qwen_variant",
    "is_complete_qwen_dir",
    "is_qwen_variant_name",
    "override_matches_variant",
    "qwen_repo_id",
    "qwen_repo_ids",
    "qwen_variant_names",
    "read_decoder_hidden_size",
    "read_dir_decoder_hidden_size",
    "resolve_qwen_model_dir",
]
