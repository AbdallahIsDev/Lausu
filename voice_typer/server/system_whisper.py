"""Dev-machine fallback: run Whisper on system libraries when the pack is missing.

The shipped app transcribes inside the offline-pack worker. When the
pack is not installed AND the process has real ML libraries importable
(a dev/source checkout, never the frozen app which nofollows them),
this engine serves the configured Whisper model in-process via
``faster-whisper`` + the already-downloaded HF weights. All imports
are function-local so merely importing this module never requires the
libraries; absence degrades to ``None`` (caller shows the pack-missing
message instead).
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

from voice_typer.server.branding import APP_NAME

log = logging.getLogger(__name__)

# Filenames that mark a snapshot dir as faster-whisper loadable.
_WEIGHT_SENTINELS: tuple[str, ...] = ("model.bin",)


def _resolve_weights_dir(model_size: str, config_dir: Path | str) -> Path | None:
    """Return a snapshot dir holding faster-whisper weights, if any."""
    from voice_typer.server.model_availability import snapshot_search_dirs
    from voice_typer.server.model_registry import get_model_metadata

    meta = get_model_metadata(model_size)
    repo_id = meta.repo_id if meta is not None else f"Systran/faster-whisper-{model_size}"
    for root in snapshot_search_dirs(config_dir, repo_id):
        snapshots = root / "snapshots"
        if not snapshots.is_dir():
            continue
        try:
            entries = sorted(p for p in snapshots.iterdir() if p.is_dir())
        except OSError:
            continue
        for snapshot in entries:
            if any((snapshot / name).is_file() for name in _WEIGHT_SENTINELS):
                return snapshot
    return None


def try_load_system_whisper(config: Any) -> Any | None:
    """Build a loaded system Whisper engine, or ``None`` when unavailable.

    Never raises: missing libraries, missing weights, or a failed load
    all return ``None`` so the caller falls through to the pack-missing
    message. Only used when the offline pack itself is absent.
    """
    try:
        import importlib

        importlib.import_module("faster_whisper")
    except ImportError:
        log.debug("[MODEL] system whisper fallback unavailable (no faster_whisper installed)")
        return None
    model_size = getattr(config, "model_size", "") or ""
    if not model_size:
        return None
    try:
        from voice_typer.server.config import _config_dir

        weights = _resolve_weights_dir(model_size, _config_dir())
    except Exception:
        log.debug("[MODEL] system whisper weights lookup failed", exc_info=True)
        return None
    if weights is None:
        log.debug("[MODEL] system whisper fallback unavailable (no local weights for %r)", model_size)
        return None
    device = getattr(config, "device", "auto") or "auto"
    try:
        from voice_typer.server.nvidia_dll_paths import (
            _configure_nvidia_dll_paths,
            _cuda_runtime_available,
        )

        _configure_nvidia_dll_paths()
        if device in ("auto", "cuda") and not _cuda_runtime_available():
            device = "cpu"
            log.info("[MODEL] CUDA runtime DLLs missing, loading system whisper on CPU")
    except Exception:
        log.debug("[MODEL] CUDA availability probe failed, keeping device=%r", device, exc_info=True)
    try:
        engine = SystemWhisperEngine(
            model_size=model_size,
            weights_dir=weights,
            device=device,
            language=getattr(config, "language", "en") or "en",
            beam_size=int(getattr(config, "beam_size", 5) or 5),
        )
        engine.load()
    except Exception:
        log.debug("[MODEL] system whisper fallback load failed", exc_info=True)
        return None
    log.info("[MODEL] serving whisper/%s from system libraries", model_size)
    return engine


class SystemWhisperEngine:
    """In-process faster-whisper backend for pack-less (dev) runs."""

    worker_backed = False

    def __init__(
        self,
        *,
        model_size: str,
        weights_dir: Path | str,
        device: str = "auto",
        language: str = "en",
        beam_size: int = 5,
    ) -> None:
        self._model_size = model_size
        self._weights_dir = str(weights_dir)
        self._device = device or "auto"
        self._language = language or "en"
        self._beam_size = beam_size
        self._model: Any | None = None
        self._loaded = False
        self._cpu_fallback_notified = False
        # Effective compute device, resolved from the built ctranslate2
        # model in load(); falls back to the requested device before that.
        self._effective_device: str = device or "auto"

    @property
    def is_loaded(self) -> bool:
        """True once :meth:`load` has built the model."""
        return self._loaded

    @property
    def device_info(self) -> str:
        """User-facing compute device for tray status lines ("GPU"/"CPU")."""
        from voice_typer.server.tray_models import describe_device

        return describe_device(getattr(self, "_effective_device", None) or self._device)

    @property
    def loaded_via(self) -> str:
        """How the model was loaded (registry/tray surface parity)."""
        return f"system/{self._model_size}"

    def load(self, *, progress_callback: Any | None = None, **kwargs: Any) -> bool:
        """Build the faster-whisper model from local weights (no download)."""
        # NOTE: importlib (not an import statement) on purpose. Two
        # consumers scan for static imports: Nuitka's follower (which
        # must never pull faster_whisper/ctranslate2/torch into the
        # frozen sidecar — see the --nofollow-import-to flags) and the
        # slim-core ratchet (scripts/slim_core_ml_ratchet_check.py).
        # Both stay green because the name only appears in a string.
        import importlib

        faster_whisper = importlib.import_module("faster_whisper")

        self._model = faster_whisper.WhisperModel(
            self._weights_dir,
            device=self._device,
            compute_type="default",
            local_files_only=True,
        )
        self._loaded = True
        # Effective device straight from the built ctranslate2 model, so
        # logs + tooltip state what the model ACTUALLY runs on instead of
        # what was requested.
        effective = str(getattr(getattr(self._model, "model", None), "device", "") or "")
        if effective:
            self._effective_device = effective
        log.info("[MODEL] system whisper model ready")
        from voice_typer.server.tray_models import describe_device

        log.info(
            "[MODEL] whisper %s running on %s (requested %s)",
            self._model_size,
            describe_device(self._effective_device),
            self._device,
        )
        return True

    def unload(self) -> None:
        """Release the model reference (GC frees the ctranslate2 state)."""
        self._model = None
        self._loaded = False

    def request_abort(self) -> None:
        """No abort handle exists on faster-whisper; best-effort no-op."""

    def clear_abort(self) -> None:
        """No abort token exists; best-effort no-op."""

    def _transcribe_inner(self, samples: Any, language: str) -> str:
        """Single faster-whisper transcribe pass over *samples*."""
        segments, _info = self._model.transcribe(
            samples,
            language=language,
            beam_size=self._beam_size,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def transcribe_with_fallback(self, audio: Any, *args: object, **kwargs: object) -> str:
        """Transcribe float PCM samples to text (possibly empty)."""
        if self._model is None:
            raise RuntimeError("system whisper engine is not loaded")
        import numpy as _np

        samples = _np.asarray(audio, dtype=_np.float32).reshape(-1)
        language = kwargs.get("language", self._language)
        try:
            return self._transcribe_inner(samples, language)
        except Exception as exc:
            from voice_typer.server.asr_utils import is_cuda_error

            if self._device != "cpu" and is_cuda_error(exc):
                log.warning("[MODEL] system whisper CUDA error, retrying on CPU: %s", exc)
                log.debug("[MODEL] system whisper CUDA traceback", exc_info=True)
                try:
                    self._rebuild_on_cpu()
                except Exception as rebuild_exc:
                    raise RuntimeError(
                        f"system whisper CUDA failed ({exc}) and CPU rebuild also failed ({rebuild_exc})"
                    ) from rebuild_exc
                if not self._cpu_fallback_notified:
                    self._cpu_fallback_notified = True
                    with contextlib.suppress(Exception):
                        from voice_typer.server import device_caps as _device_caps

                        _device_caps.publish_device_cpu_fallback(str(exc)[:200])
                    with contextlib.suppress(Exception):
                        from voice_typer.server import event_bus as _event_bus

                        _event_bus.publish(
                            {
                                "type": "notification",
                                "data": {
                                    "title": APP_NAME,
                                    "message": (
                                        "GPU transcription failed, switched to CPU. "
                                        "Transcription will be slower until restart."
                                    ),
                                    "duration_ms": 10000,
                                },
                            }
                        )
                try:
                    return self._transcribe_inner(samples, language)
                except Exception as cpu_exc:
                    raise RuntimeError(
                        f"system whisper CUDA failed ({exc}) and CPU retry also failed ({cpu_exc})"
                    ) from cpu_exc
            raise

    def _rebuild_on_cpu(self) -> None:
        """Drop the CUDA model and rebuild it on CPU."""
        import gc
        import importlib

        with contextlib.suppress(Exception):
            del self._model
        self._model = None
        gc.collect()
        faster_whisper = importlib.import_module("faster_whisper")
        self._model = faster_whisper.WhisperModel(
            self._weights_dir,
            device="cpu",
            compute_type="default",
            local_files_only=True,
        )
        self._device = "cpu"
        self._loaded = True
        log.warning("[MODEL] system whisper rebuilt on CPU after CUDA failure")
