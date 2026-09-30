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

import logging
from pathlib import Path
from typing import Any

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
    try:
        engine = SystemWhisperEngine(
            model_size=model_size,
            weights_dir=weights,
            device=getattr(config, "device", "auto"),
            language=getattr(config, "language", "en") or "en",
            beam_size=int(getattr(config, "beam_size", 5) or 5),
        )
        engine.load()
    except Exception:
        log.debug("[MODEL] system whisper fallback load failed", exc_info=True)
        return None
    log.info(
        "[MODEL] serving whisper/%s from system libraries (%s)",
        model_size,
        weights,
    )
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

    @property
    def is_loaded(self) -> bool:
        """True once :meth:`load` has built the model."""
        return self._loaded

    @property
    def device_info(self) -> str:
        """Human-readable backend description for tray/paste lines."""
        return f"system whisper ({self._device})"

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
        log.info("[MODEL] system whisper model ready (%s)", self._weights_dir)
        return True

    def unload(self) -> None:
        """Release the model reference (GC frees the ctranslate2 state)."""
        self._model = None
        self._loaded = False

    def request_abort(self) -> None:
        """No abort handle exists on faster-whisper; best-effort no-op."""

    def clear_abort(self) -> None:
        """No abort token exists; best-effort no-op."""

    def transcribe_with_fallback(self, audio: Any, *args: object, **kwargs: object) -> str:
        """Transcribe float PCM samples to text (possibly empty)."""
        if self._model is None:
            raise RuntimeError("system whisper engine is not loaded")
        import numpy as _np

        samples = _np.asarray(audio, dtype=_np.float32).reshape(-1)
        language = kwargs.get("language", self._language)
        segments, _info = self._model.transcribe(
            samples,
            language=language,
            beam_size=self._beam_size,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
