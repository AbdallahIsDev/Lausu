"""Worker-proxy ASR backends for the ONNX models (parakeet / qwen).

This file exists so the sidecar can serve the two ONNX backends through
the runtime-pack worker (the model then lives in the worker across
sidecar restarts) while keeping the in-process ONNX engines as the
fallback when no worker is connected (no pack = no worker).

One concern only: the worker-hop surface (explicit load request +
samples transcribe) shared by both backends. Whisper's equivalent proxy
(``WorkerWhisperProxyEngine``) lives in ``system_whisper.py`` because it
is the pack-absent fallback path; the hop logic here deliberately mirrors
it, and only it, so the stranded-backends case stays identical.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.system_whisper import _WORKER_TRANSCRIBE_TIMEOUT_SECONDS

log = logging.getLogger(__name__)


class WorkerProxyEngine:
    """Registry backend that transcribes via the pack worker's loaded model.

    Shared by the ONNX backends (parakeet / qwen, see the subclasses):
    no model weights ever load in this process; every call forwards to
    the worker over the C2/C3 bridge, exactly like the whisper
    ``WorkerWhisperProxyEngine``. Subclasses only pin the backend name.
    """

    worker_backed = True

    def __init__(
        self,
        *,
        backend: str,
        device_info: str = "pack worker",
        language: str = "en",
        client: Any | None = None,
    ) -> None:
        self._backend = backend
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
        return f"worker/{self._backend}"

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


class WorkerParakeetProxyEngine(WorkerProxyEngine):
    """Worker proxy for the parakeet registry slot (see the base)."""

    def __init__(
        self,
        *,
        device_info: str = "pack worker",
        language: str = "en",
        client: Any | None = None,
    ) -> None:
        super().__init__(backend="parakeet", device_info=device_info, language=language, client=client)


class WorkerQwenProxyEngine(WorkerProxyEngine):
    """Worker proxy for the qwen registry slot (see the base)."""

    def __init__(
        self,
        *,
        model_path: str = "",
        device_info: str = "pack worker",
        language: str = "en",
        client: Any | None = None,
    ) -> None:
        self._model_path = model_path
        super().__init__(backend="qwen", device_info=device_info, language=language, client=client)


def try_load_worker_parakeet(config: Any, timeout: float = 300.0) -> Any | None:
    """Ask the pack worker to load parakeet; return a proxy engine or ``None``.

    Worker-first path for pack-present runs: when the worker is
    connected its already-cached model serves transcription with zero
    ``onnx_asr``/``onnxruntime`` import in this process. Returns ``None``
    when the worker is down, refuses, or times out so the caller falls
    through to the in-process ONNX engine. Never raises.
    """
    try:
        device = getattr(config, "device", "auto") or "auto"
        language = getattr(config, "language", "en") or "en"
        from voice_typer.server.worker_client import get_shared_client

        client = get_shared_client()
        if client.port is None:
            log.debug("[MODEL] worker parakeet unavailable (worker not connected)")
            return None
        future = client.request_load_parakeet_model(device, language, timeout=timeout)
        if future is None:
            return None
        try:
            result = future.result(timeout=timeout)
        except Exception:
            log.debug("[MODEL] worker parakeet load timed out or failed", exc_info=True)
            return None
        if not isinstance(result, dict) or not result.get("loaded") or result.get("error"):
            reason = result.get("error") if isinstance(result, dict) else result
            log.debug("[MODEL] worker parakeet load refused: %s", reason)
            return None
        device_info = result.get("device_info")
        engine = WorkerParakeetProxyEngine(
            device_info=device_info if isinstance(device_info, str) and device_info else "pack worker",
            language=language,
        )
        log.info("[MODEL] serving parakeet from pack worker")
        return engine
    except Exception:
        log.debug("[MODEL] worker parakeet fallback failed", exc_info=True)
        return None


def try_load_worker_qwen(config: Any, timeout: float = 300.0) -> Any | None:
    """Ask the pack worker to load qwen; return a proxy engine or ``None``.

    Same worker-first contract as :func:`try_load_worker_parakeet`.
    Returns ``None`` without touching the client when no model path is
    configured, so the caller falls through to the in-process engine.
    Never raises.
    """
    try:
        model_path = getattr(config, "qwen_model_path", None) or ""
        if not model_path:
            return None
        device = getattr(config, "device", "auto") or "auto"
        language = getattr(config, "language", "en") or "en"
        from voice_typer.server.worker_client import get_shared_client

        client = get_shared_client()
        if client.port is None:
            log.debug("[MODEL] worker qwen unavailable (worker not connected)")
            return None
        future = client.request_load_qwen_model(model_path, device, language, timeout=timeout)
        if future is None:
            return None
        try:
            result = future.result(timeout=timeout)
        except Exception:
            log.debug("[MODEL] worker qwen load timed out or failed", exc_info=True)
            return None
        if not isinstance(result, dict) or not result.get("loaded") or result.get("error"):
            reason = result.get("error") if isinstance(result, dict) else result
            log.debug("[MODEL] worker qwen load refused: %s", reason)
            return None
        device_info = result.get("device_info")
        engine = WorkerQwenProxyEngine(
            model_path=model_path,
            device_info=device_info if isinstance(device_info, str) and device_info else "pack worker",
            language=language,
        )
        log.info("[MODEL] serving qwen from pack worker")
        return engine
    except Exception:
        log.debug("[MODEL] worker qwen fallback failed", exc_info=True)
        return None


__all__ = [
    "WorkerParakeetProxyEngine",
    "WorkerProxyEngine",
    "WorkerQwenProxyEngine",
    "try_load_worker_parakeet",
    "try_load_worker_qwen",
]
