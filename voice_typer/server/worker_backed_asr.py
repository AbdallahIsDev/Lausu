"""Worker-backed whisper backend (ADR-0025 C7).

One purpose only: expose the in-process ``AsrBackend`` surface for the
``whisper`` registry slot while running ZERO inference in this process.
Every call forwards to the runtime-pack worker over the C2/C3 bridge;
the faster_whisper engine class it replaces
(``transcription.TranscriptionEngine``) is deleted, which is what lets
the Nuitka sidecar exclude ``faster_whisper``/``ctranslate2``.

``parakeet``/``qwen`` keep their in-process ONNX engines; only
``whisper`` is worker-backed. There is deliberately no
``transcribe_words`` here: word-level streaming goes through the C6
worker session (the coordinator checks for this class), never through
an in-process engine that no longer exists.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.worker_client import WorkerAbortedError, get_shared_client

log = logging.getLogger(__name__)

# Bounded wait for one worker inference (matches the C5 dictation path).
_TRANSCRIBE_TIMEOUT_SECONDS = 120.0


class WorkerTranscriptionError(RuntimeError):
    """Worker-backed transcription failed (no in-process fallback exists)."""


class WorkerBackedAsr:
    """Registry backend that forwards whisper work to the pack worker."""

    # Marker: callers that must distinguish "runs here" from "runs in
    # the worker" check this instead of backend names (E7: one flag).
    worker_backed = True

    def __init__(self, **kwargs: Any) -> None:
        self._kwargs = dict(kwargs)
        # Mirror the engine's live-config handle (manager wiring pins it).
        self.config = kwargs.get("config")
        self._device_info = "pack worker"
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """True once :meth:`load` succeeds (pack-gated, like the engine)."""
        return self._loaded

    @property
    def device_info(self) -> str:
        """Human-readable backend description for tray/paste lines."""
        return self._device_info

    @property
    def loaded_via(self) -> str:
        """How the model is served (registry/tray surface parity)."""
        return f"worker/{self._kwargs.get('model_size', 'unknown')}"

    def load(self, *, progress_callback: Any | None = None, **kwargs: Any) -> bool:
        """Verify the pack can serve; nothing loads in-process.

        Raises the same ``ModelNotDownloadedError`` the engine path
        raises when there is no model, so the manager's refused-load UX
        is unchanged.
        """
        from voice_typer.server.asr_errors import OfflinePackMissingError
        from voice_typer.server.service import update_check

        if update_check._local_offline_pack_version() is None:
            raise OfflinePackMissingError(
                "The offline pack is not installed. Open Settings to download it.",
                model_size=str(self._kwargs.get("model_size", "")),
                backend="whisper",
            )
        self._loaded = True
        log.info("[WORKER] whisper backend ready (worker-backed, nothing loaded in-process)")
        return True

    def unload(self) -> None:
        """Release the backend (nothing held in-process)."""
        self._loaded = False

    def clear_abort(self) -> None:
        """No local abort token exists; the worker owns abort state."""

    def request_abort(self) -> None:
        """Abort outstanding worker requests for this backend."""
        try:
            get_shared_client().abort_all_outstanding()
        except Exception:
            log.debug("[WORKER] worker abort from shim failed", exc_info=True)

    def transcribe(self, audio: Any, audio_stats: tuple[float, float, float] | None = None) -> str:
        """TranscriberProtocol surface (mic-test, CloudEngine local fallback).

        Same worker hop as :meth:`transcribe_with_fallback`; ``audio_stats``
        is accepted for signature parity and unused (no local decode).
        """
        return self.transcribe_with_fallback(audio)

    def transcribe_with_fallback(self, audio: Any, *args: object, **kwargs: object) -> str:
        """Transcribe via worker in-memory samples; raise when it fails.

        ``WorkerTranscriptionError`` (not silent ``""``) so callers can
        tell "worker down" apart from "no speech": an empty result still
        means silence, exactly like the engine contract.
        """
        import numpy as _np

        try:
            raw = _np.asarray(audio, dtype=_np.float32).reshape(-1).tobytes()
        except Exception as exc:
            raise WorkerTranscriptionError(f"invalid audio array: {exc}") from exc
        client = get_shared_client()
        if client.port is None:
            raise WorkerTranscriptionError("worker not connected")
        language = kwargs.get("language", self._kwargs.get("language"))
        sample_rate = kwargs.get("sample_rate", 16000)
        try:
            sample_rate = int(sample_rate)
        except (TypeError, ValueError):
            sample_rate = 16000
        try:
            future = client.request_samples(raw, sample_rate, language, timeout=_TRANSCRIBE_TIMEOUT_SECONDS)
        except Exception as exc:
            raise WorkerTranscriptionError(f"worker request failed: {exc}") from exc
        if future is None:
            raise WorkerTranscriptionError("worker request refused")
        try:
            result = future.result(timeout=_TRANSCRIBE_TIMEOUT_SECONDS)
        except WorkerAbortedError:
            # User cancel is not a failure: propagate unwrapped so the
            # pipeline's cancelled-cycle path owns the UX (silent "").
            raise
        except Exception as exc:
            raise WorkerTranscriptionError(f"worker transcription failed: {exc}") from exc
        if not isinstance(result, dict) or result.get("error"):
            raise WorkerTranscriptionError(str((result or {}).get("error") or "worker returned an error"))
        device_info = result.get("device_info")
        if isinstance(device_info, str) and device_info:
            self._device_info = device_info
        return str(result.get("text") or "")
