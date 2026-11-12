"""Session/provider selection, availability checks, model load/unload."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from voice_typer.server.duration import format_duration

from ._constants import (
    _CHUNK_SECONDS,
    _PARAKERT_ONNX_MODEL_NAME,
    _PARAKERT_ONNX_REPO_ID,
    _PARAKERT_QUANTIZATION,
    _PARAKERT_WEIGHTS_MB,
)

log = logging.getLogger(__name__)

# ORT builds its CUDA/cuDNN state on the FIRST Run, not at session creation:
# a 141s dictation spent 17s in chunk 1/7 and ~1.5s in every chunk after it.
# Priming at load moves that cost off the dictation path. GPU primes with the
# real chunk shape; CPU has no shape plan to build, so a short buffer is enough.
_WARMUP_CPU_SECONDS = 0.5


class LoadMixin:
    # Members owned by ParakeetEngine (engine.py):
    _imports_lock: threading.Lock
    _lock: threading.RLock
    _model: Any
    device: str

    def _make_sess_options(self) -> Any | None:
        """Build ORT SessionOptions with the CPU arena off.

        ORT enables the CPU arena by default and never returns its peak,
        so one warm decode pins process RSS for the process lifetime.
        arena-off makes allocations direct and reclaimed per inference.
        """
        ort = getattr(self, "_ort", None)
        if ort is None:
            return None
        try:
            options = ort.SessionOptions()
            options.enable_cpu_mem_arena = False
            return options
        except Exception:
            log.debug("[PARAKEET] SessionOptions unavailable, using ORT defaults", exc_info=True)
            return None

    @classmethod
    def _ensure_imports(cls) -> bool:
        """Lazily import ``onnx_asr`` + ``onnxruntime``.

        Returns ``True`` on success, ``False`` if either package is not
        """
        with cls._imports_lock:
            if cls._imports_loaded:
                return True
            _t0 = time.perf_counter()
            try:
                import onnx_asr
                import onnxruntime as ort

                cls._onnx_asr = onnx_asr
                cls._ort = ort
                cls._imports_loaded = True
                _elapsed = time.perf_counter() - _t0
                log.info(
                    "[PARAKEET] onnx_asr %s + onnxruntime %s imported%s",
                    getattr(onnx_asr, "__version__", "?"),
                    getattr(ort, "__version__", "?"),
                    format_duration(_elapsed),
                )
                return True
            except ImportError as exc:
                cls._imports_loaded = False
                log.warning(
                    "[PARAKEET] onnx_asr/onnxruntime import failed. Install onnx-asr + onnxruntime: %s",
                    exc,
                )
                return False

    @classmethod
    def is_available(cls) -> bool:
        """Return ``True`` if the ONNX backend can be loaded."""
        try:
            import onnx_asr  # noqa: F401
            import onnxruntime  # noqa: F401
        except ImportError:
            return False
        return True

    def _select_providers(self, device: str) -> list[str]:
        """Map a device string to an ORT ``providers=`` list."""
        if device == "cuda":
            try:
                available = self._ort.get_available_providers() if self._ort is not None else []
            except Exception:
                available = []
            if "CUDAExecutionProvider" in available:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
            # AzureExecutionProvider is present in CPU builds but needs
            # config to run; don't list it as an available fallback.
            have = [p for p in available if p != "AzureExecutionProvider"]
            log.info(
                "[PARAKEET] CUDAExecutionProvider not available (have: %s), using CPU only",
                ", ".join(have) if have else "none",
            )
            return ["CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    @staticmethod
    def _should_force_cpu() -> bool:
        """Check disk space on system drive, if under 500MB, force CPU."""
        from voice_typer.server.platform_utils import is_windows

        if not is_windows():
            return False
        try:
            import psutil

            system_drive = os.environ.get("SYSTEMDRIVE", "C:") + "\\"
            usage = psutil.disk_usage(system_drive)
            free_mb = usage.free // (1024 * 1024)
            if free_mb < 500:
                log.warning(
                    "[PARAKEET] Only %d MB free on %s, forcing CPU (CUDA needs pagefile space to allocate GPU memory)",
                    free_mb,
                    system_drive,
                )
                return True
        except Exception:
            log.debug("[PARAKEET] _should_force_cpu disk space check failed (non-fatal)", exc_info=True)
        return False

    @staticmethod
    def _is_cached() -> bool:
        """Quick check if the Parakeet ONNX model is in the HF cache."""
        from voice_typer.server.config import _config_dir
        from voice_typer.server.model_availability import snapshot_search_dirs

        for model_dir in snapshot_search_dirs(_config_dir(), _PARAKERT_ONNX_REPO_ID):
            snapshots = model_dir / "snapshots"
            if not snapshots.is_dir():
                continue
            try:
                for entry in snapshots.iterdir():
                    if not entry.is_dir():
                        continue
                    if any(entry.glob("*.onnx")):
                        return True
            except OSError:
                log.debug("[PARAKEET] _is_cached snapshot iterdir failed (non-fatal)", exc_info=True)
        return False

    def load(self, progress_callback: Callable[[str], None] | None = None) -> bool:
        """Load the Parakeet ONNX model via ``onnx_asr.load_model(...)``."""
        _total_t0 = time.perf_counter()
        log.info("[PARAKEET] load() entered, importing onnx-asr if needed")
        if not self._ensure_imports():
            if progress_callback:
                progress_callback("Missing dependencies: onnx-asr + onnxruntime")
            return False

        with self._lock:
            if self._model is not None:
                return True

            # Reset the one-time CPU-fallback notification flag on
            self._cpu_fallback_notified = False
            self._cpu_fallback_since = None
            self._cpu_transcribe_count = 0

            # Quick cache check, avoids calling onnx_asr.load_model(...)
            _cache_t0 = time.perf_counter()
            _cached = self._is_cached()
            log.info(
                "[PARAKEET] model cache check: cached=%s%s",
                _cached,
                format_duration(time.perf_counter() - _cache_t0),
            )
            if not _cached:
                # The app NEVER auto-downloads models, downloading is
                from voice_typer.server.asr_errors import ModelNotDownloadedError

                raise ModelNotDownloadedError(
                    "The Parakeet model is not downloaded yet. "
                    "Open the Models page and click Download before using it.",
                    model_size="parakeet",
                    backend="parakeet",
                    repo_id=_PARAKERT_ONNX_REPO_ID,
                )

            # Verify model integrity (hash check), UNCONDITIONALLY on
            from voice_typer.server.config import _config_dir
            from voice_typer.server.model_availability import snapshot_search_dirs
            from voice_typer.server.security import verify_model_integrity

            verified_snapshot: str | None = None
            model_dir = snapshot_search_dirs(_config_dir(), _PARAKERT_ONNX_REPO_ID)[0]
            verified = False
            verify_exc: Exception | None = None
            verify_elapsed = 0.0
            _verify_t0 = time.perf_counter()
            try:
                for candidate in snapshot_search_dirs(_config_dir(), _PARAKERT_ONNX_REPO_ID):
                    if not candidate.is_dir():
                        continue
                    for snapshot in (candidate / "snapshots").iterdir():
                        if snapshot.is_dir() and verify_model_integrity(str(snapshot), _PARAKERT_ONNX_REPO_ID):
                            verified = True
                            verified_snapshot = str(snapshot)
                            break
                    if verified:
                        break
            except OSError as exc:
                verify_exc = exc
            verify_elapsed = time.perf_counter() - _verify_t0
            if not verified:
                log.error(
                    "[PARAKEET] Model integrity check failed%s for %s at %s. "
                    "Refusing to load tampered model. To fix: delete it from the Models page.%s",
                    f" (OSError: {verify_exc})" if verify_exc else "",
                    _PARAKERT_ONNX_REPO_ID,
                    model_dir,
                    format_duration(verify_elapsed),
                )
                if progress_callback:
                    progress_callback("Model integrity check failed; delete and re-download from the Models page.")
                from voice_typer.server.asr_errors import ModelIntegrityError

                raise ModelIntegrityError(
                    "The cached Parakeet model failed integrity verification. "
                    "Delete it and download it again from the Models page to recover.",
                    model_size="parakeet",
                    backend="parakeet",
                    repo_id=_PARAKERT_ONNX_REPO_ID,
                )

            # Load ONNX model via onnx_asr.load_model(...), by TYPE
            try:
                if progress_callback:
                    progress_callback("Loading Parakeet Ultra ONNX model...")

                requested_device = self.device
                effective_device = requested_device
                if effective_device == "cuda" and self._should_force_cpu():
                    effective_device = "cpu"

                providers = self._select_providers(effective_device)
                effective_label = "GPU" if "CUDAExecutionProvider" in providers else "CPU"
                log.info(
                    "[PARAKEET] Loading Parakeet Ultra ONNX model on %s (requested=%s, providers=%s)...",
                    effective_label,
                    requested_device,
                    ", ".join(providers),
                )
                _load_start = time.perf_counter()

                # onnx-asr 0.12.0 exports ``load_model(...)``: there is
                self._onnx_model_dir = verified_snapshot
                self._model = self._onnx_asr.load_model(
                    _PARAKERT_ONNX_MODEL_NAME,
                    path=verified_snapshot,
                    quantization=_PARAKERT_QUANTIZATION,
                    providers=providers,
                    sess_options=self._make_sess_options(),
                )

                _elapsed = time.perf_counter() - _load_start
                _read_speed_mbs = _PARAKERT_WEIGHTS_MB / max(_elapsed, 0.1)
                # C-LOG-2: measured duration + throughput are the whole
                # warm/cold signal; a wall-time threshold would mislabel.
                log.info(
                    "[PARAKEET] Parakeet Ultra ONNX model loaded on %s (%s) (%.0f MB/s)%s",
                    effective_label,
                    ", ".join(providers),
                    _read_speed_mbs,
                    format_duration(_elapsed),
                )
                # Stash the effective providers so the GPU→CPU fallback
                self._effective_providers = providers
                _warm_elapsed = self._warm_session(providers)
                log.info(
                    "[PARAKEET] load timing: integrity%s, onnx load%s, warm%s, total%s",
                    format_duration(verify_elapsed),
                    format_duration(_elapsed),
                    format_duration(_warm_elapsed),
                    format_duration(time.perf_counter() - _total_t0),
                )
                if progress_callback:
                    progress_callback("Parakeet model ready")
                return True

            except ImportError as exc:
                log.exception("[PARAKEET] onnx_asr package not installed")
                if progress_callback:
                    progress_callback(f"Missing dependency: {exc}")
                return False
            except KeyboardInterrupt:
                log.warning("[PARAKEET] Loading interrupted by user")
                if progress_callback:
                    progress_callback("Loading cancelled")
                return False
            except Exception as exc:
                log.exception("[PARAKEET] Failed to load model")
                if progress_callback:
                    progress_callback(f"Model load failed: {exc}")
                return False

    def _warm_session(self, providers: list[str]) -> float:
        """Prime ORT's first-Run init so the first dictation does not pay it.

        Returns the warm duration in seconds; never raises (a failed warm
        must not fail the load, the first real decode just pays the init).
        """
        t0 = time.perf_counter()
        model = self._model
        if model is None:
            return 0.0
        seconds = _CHUNK_SECONDS if "CUDAExecutionProvider" in providers else _WARMUP_CPU_SECONDS
        try:
            import numpy as np

            from voice_typer.server._audio_constants import WHISPER_SAMPLE_RATE

            silence = np.zeros(int(seconds * WHISPER_SAMPLE_RATE), dtype=np.float32)
            model.recognize(silence, sample_rate=WHISPER_SAMPLE_RATE)
        except Exception:
            log.warning(
                "[PARAKEET] warm decode failed (non-fatal; the first dictation pays the init)",
                exc_info=True,
            )
        return time.perf_counter() - t0

    def _load_impl(self, *, providers: list[str]) -> bool:
        """Re-create the ONNX session (``onnx_asr.load_model``) with the given providers.

        Returns ``True`` on success, ``False`` if the new session could
        """
        if not self._ensure_imports():
            return False
        try:
            self._model = self._onnx_asr.load_model(
                _PARAKERT_ONNX_MODEL_NAME,
                path=self._onnx_model_dir,
                quantization=_PARAKERT_QUANTIZATION,
                providers=providers,
                sess_options=self._make_sess_options(),
            )
            self._effective_providers = providers
            return True
        except Exception:
            log.exception(
                "[PARAKEET] Failed to recreate ONNX session with providers=%s",
                providers,
            )
            return False

    def _unload_impl(self) -> None:
        """Drop the loaded onnx-asr model reference (without acquiring"""
        with self._lock:
            self._model = None
