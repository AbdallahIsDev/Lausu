"""Whisper model ownership for pack-less runs.

The shipped app transcribes inside the runtime-pack worker through the GGUF
speech runner. In-process Whisper decoding was removed with the legacy ASR
stack: there is no system-library fallback left in this process. The worker
loader and its proxy engine stay here because the registry and the model-load
IPC still use them; ``try_load_system_whisper`` remains as an explicit refusal
so callers fall through to the offline-pack error.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.asr_utils import asr_language_param

log = logging.getLogger(__name__)

_WORKER_TRANSCRIBE_TIMEOUT_SECONDS = 120.0


def try_load_system_whisper(config: Any) -> None:
    """Always refuse: system-library ASR was removed with the legacy stack."""
    return None


def try_load_worker_whisper(config: Any, timeout: float = 300.0) -> Any | None:
    """Ask the pack worker to load whisper; return a proxy engine or ``None``.

    Worker-first path for pack-absent runs: when the worker is connected
    its already-cached model serves transcription with no model load in
    this process. Returns ``None`` when the worker is down, refuses, or
    times out so the caller shows the offline-pack error. Never raises.
    """
    try:
        model_size = getattr(config, "model_size", "") or ""
        if not model_size:
            return None
        device = getattr(config, "device", "auto") or "auto"
        # Auto ("") must reach the engine as None: an empty string or a
        # forced "en" both mean "this audio is English", which is how a
        # non-English dictation got decoded/pinned wrong.
        language = asr_language_param(getattr(config, "language", ""))
        from voice_typer.server.worker_client import get_shared_client

        client = get_shared_client()
        if client.port is None:
            log.debug("[MODEL] worker whisper unavailable (worker not connected)")
            return None
        future = client.request_load_whisper_model(model_size, device, language, timeout=timeout)
        if future is None:
            return None
        try:
            result = future.result(timeout=timeout)
        except Exception:
            log.debug("[MODEL] worker whisper load timed out or failed", exc_info=True)
            return None
        if not isinstance(result, dict) or not result.get("loaded") or result.get("error"):
            reason = result.get("error") if isinstance(result, dict) else result
            log.debug("[MODEL] worker whisper load refused: %s", reason)
            return None
        device_info = result.get("device_info")
        engine = WorkerWhisperProxyEngine(
            model_size=model_size,
            device_info=device_info if isinstance(device_info, str) and device_info else "pack worker",
            language=language or "",
        )
        log.info("[MODEL] serving whisper/%s from pack worker", model_size)
        return engine
    except Exception:
        log.debug("[MODEL] worker whisper fallback failed", exc_info=True)
        return None


class WorkerWhisperProxyEngine:
    """Registry backend that transcribes via the pack worker's loaded model."""

    worker_backed = True

    def __init__(
        self,
        *,
        model_size: str,
        device_info: str = "pack worker",
        language: str = "en",
        client: Any | None = None,
    ) -> None:
        self._model_size = model_size
        self._device_info = device_info or "pack worker"
        self._language = language or "en"
        self._client = client
        self._loaded = True
        self.last_rejection_reason: str | None = None

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def device_info(self) -> str:
        try:
            from voice_typer.server.tray_models import describe_device

            return describe_device(self._device_info)
        except Exception:
            return self._device_info

    @property
    def loaded_via(self) -> str:
        return f"worker/{self._model_size}"

    def load(self, *, progress_callback: Any | None = None, **kwargs: Any) -> bool:
        self._loaded = True
        return True

    def unload(self) -> None:
        self._loaded = False

    def clear_abort(self) -> None:
        pass

    def request_abort(self) -> None:
        try:
            client = self._client
            if client is None:
                from voice_typer.server.worker_client import get_shared_client

                client = get_shared_client()
            client.abort_all_outstanding()
        except Exception:
            log.debug("[MODEL] worker proxy abort failed", exc_info=True)

    def transcribe(self, audio: Any, audio_stats: Any | None = None) -> str:
        return self.transcribe_with_fallback(audio)

    def transcribe_with_fallback(self, audio: Any, *args: object, **kwargs: object) -> str:
        import numpy as _np

        from voice_typer.server.worker_backed_asr import WorkerTranscriptionError

        try:
            raw = _np.asarray(audio, dtype=_np.float32).reshape(-1).tobytes()
        except Exception as exc:
            raise WorkerTranscriptionError(f"invalid audio array: {exc}") from exc
        try:
            client = self._client
            if client is None:
                from voice_typer.server.worker_client import get_shared_client

                client = get_shared_client()
        except Exception as exc:
            raise WorkerTranscriptionError(f"worker request failed: {exc}") from exc
        if client.port is None:
            raise WorkerTranscriptionError("worker not connected")
        language_arg: object = kwargs.get("language", self._language)
        language: str | None = language_arg if isinstance(language_arg, (str, type(None))) else self._language
        sample_rate_arg: object = kwargs.get("sample_rate", 16000)
        if isinstance(sample_rate_arg, bool):
            sample_rate = 16000
        elif isinstance(sample_rate_arg, int):
            sample_rate = sample_rate_arg
        else:
            sample_rate = 16000
        try:
            future = client.request_samples(raw, sample_rate, language, timeout=_WORKER_TRANSCRIBE_TIMEOUT_SECONDS)
        except Exception as exc:
            raise WorkerTranscriptionError(f"worker request failed: {exc}") from exc
        if future is None:
            raise WorkerTranscriptionError("worker request refused")
        try:
            result = future.result(timeout=_WORKER_TRANSCRIBE_TIMEOUT_SECONDS)
        except Exception as exc:
            from voice_typer.server.worker_client import WorkerAbortedError

            if isinstance(exc, WorkerAbortedError):
                raise
            raise WorkerTranscriptionError(f"worker transcription failed: {exc}") from exc
        if not isinstance(result, dict) or result.get("error"):
            raise WorkerTranscriptionError(str((result or {}).get("error") or "worker returned an error"))
        device_info = result.get("device_info")
        if isinstance(device_info, str) and device_info:
            self._device_info = device_info
        rejected = result.get("rejected_reason")
        self.last_rejection_reason = rejected if isinstance(rejected, str) and rejected else None
        return str(result.get("text") or "")
