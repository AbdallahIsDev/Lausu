"""Cached model-status computation for the Models page."""

from __future__ import annotations

import logging
import time

from ._constants import _MODEL_STATUS_CACHE_TTL_S

log = logging.getLogger(__name__)


class StatusMixin:
    # Owned by DownloadStateMixin.__init__ (model/_download_state.py);
    # declared here so the cache reads/writes below type-check.
    _model_status_cache: dict[str, object] | None
    _model_status_cache_ts: float

    def get_model_status(self) -> dict[str, object]:
        """Results are cached for ``_MODEL_STATUS_CACHE_TTL_S`` seconds."""
        now = time.monotonic()
        with self._model_status_cache_lock:
            if self._model_status_cache is not None and (now - self._model_status_cache_ts) < _MODEL_STATUS_CACHE_TTL_S:
                return self._model_status_cache
        status = self._compute_model_status()
        with self._model_status_cache_lock:
            self._model_status_cache = status
            self._model_status_cache_ts = now
        return status

    def _compute_model_status(self) -> dict[str, object]:
        """Extracted from :meth:`get_model_status` so the cache check and
        the (slower) status computation stay independently readable."""
        import os

        from voice_typer.server.config import _config_dir

        config = self._app.config
        status: dict[str, object] = {}

        # Whisper models. Check ALL models from the registry, using
        # PARTIAL-DOWNLOAD HONESTY: the completeness answer comes from the
        from voice_typer.server import model_availability
        from voice_typer.server.model_registry import MODEL_REGISTRY, get_model_metadata

        for meta in MODEL_REGISTRY.values():
            if meta.backend not in ("whisper", "distil-whisper"):
                continue
            downloaded = model_availability.is_available(meta.repo_id, _config_dir())
            status[meta.name] = {
                "downloaded": downloaded,
            }

        # Qwen variants: a matching manual override path OR the pinned HF
        # cache snapshot (``qwen_layout`` knows both).
        from voice_typer.server.qwen_layout import override_matches_variant

        qwen_path = getattr(config, "qwen_model_path", None)
        for meta in MODEL_REGISTRY.values():
            if meta.backend != "qwen":
                continue
            status[meta.name] = {
                "downloaded": override_matches_variant(meta.name, qwen_path)
                or model_availability.is_available(meta.repo_id, _config_dir()),
                # The Qwen backend is ONNX-only (qwen_onnx_model.py);
                "deps_ok": True,
            }

        # Parakeet model
        parakeet_path = getattr(config, "parakeet_model_path", None)
        parakeet_meta = get_model_metadata("parakeet")
        if parakeet_meta is not None:
            parakeet_in_cache = model_availability.is_available(parakeet_meta.repo_id, _config_dir())
        else:
            parakeet_in_cache = False
        status["parakeet"] = {
            "downloaded": bool(parakeet_path and os.path.isdir(parakeet_path)) or parakeet_in_cache,
            # The Parakeet backend is ONNX-only (parakeet_engine.py via
            "deps_ok": True,
        }

        return status

    def _invalidate_model_status_cache(self) -> None:
        """Drop the cached model-status dict."""
        from voice_typer.server import model_availability

        model_availability.invalidate()
        with self._model_status_cache_lock:
            self._model_status_cache = None
            self._model_status_cache_ts = 0.0
