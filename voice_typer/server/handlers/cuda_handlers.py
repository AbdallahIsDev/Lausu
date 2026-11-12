"""GPU capability + CUDA install IPC handlers."""

from voice_typer.server.handlers._base import HandlerBase
from voice_typer.server.handlers._log import log

# Refusal reasons surfaced to the renderer as `set_config` error codes.
REJECT_DOWNLOAD_RUNNING = "cuda_download_in_progress"
REJECT_STACK_NOT_READY = "gpu_not_ready"


def device_request_rejection(updates: dict, config: object | None = None) -> str | None:
    """CPU-retention guard: refuse ``device: "cuda"`` too early.

    Two states must never be persisted as a GPU request:

    * the install job is still running, the wheels are half-extracted and
      no backend could possibly serve GPU yet;
    * the ACTIVE backend cannot serve GPU (or, when no backend is known,
      the whole stack is incomplete), where persisting ``cuda`` would
      produce a GPU pill that cannot serve (C-UI-15).

    The per-backend check is the important half: a machine whose
    CTranslate2 path sees the GPU but whose ``onnxruntime`` is the CPU-only
    wheel reports global ``cuda_ready`` True, so gating on that let a
    Parakeet user write ``cuda`` and silently fall back to CPU.

    ``config`` is the live ``Config`` (``config.asr_backend`` is read the
    same way ``config_service.get_config`` reads it). Passing ``None``
    falls back to the stricter whole-stack signal — never to the loose
    ``cuda_ready``.

    Returns ``None`` when the request may proceed. Read-only: never
    writes config, never touches the job.
    """
    if not isinstance(updates, dict) or updates.get("device") != "cuda":
        return None
    try:
        from voice_typer.server.cuda_install.service import get_service

        if get_service().is_running():
            return REJECT_DOWNLOAD_RUNNING
    except Exception:
        log.debug("[CUDA] install-state probe failed during device guard", exc_info=True)
    backend = getattr(config, "asr_backend", None) if config is not None else None
    if not isinstance(backend, str) or not backend:
        backend = None
    try:
        from voice_typer.server import gpu_capability

        snapshot = gpu_capability.snapshot(active_backend=backend)
    except Exception:
        log.debug("[CUDA] capability probe failed during device guard", exc_info=True)
        return REJECT_STACK_NOT_READY
    if backend is None:
        # No backend information: only the whole stack can vouch for `cuda`.
        return None if snapshot.get("stack_complete") else REJECT_STACK_NOT_READY
    backends = snapshot.get("backends")
    entry = None
    if isinstance(backends, list):
        entry = next(
            (item for item in backends if item.get("name") == backend),
            None,
        )
    # A backend that cannot do GPU at all (Qwen pins its ONNX session to
    # CPU by design) makes `device` a global preference rather than a
    # claim about this engine — do not block it with a CUDA modal.
    if entry is not None and not entry.get("gpu_capable"):
        return None
    return None if snapshot.get("active_backend_gpu_ready") else REJECT_STACK_NOT_READY


class CudaHandlersMixin(HandlerBase):
    """Mixin: GPU capability reads and the user-level CUDA install job."""

    def _handle_get_gpu_capability(self, data: object | None, resp: dict) -> dict:
        """Handle the ``get_gpu_capability`` IPC command (read-only)."""
        try:
            from voice_typer.server import gpu_capability

            backend = getattr(self.app.config, "asr_backend", None)
            snapshot = gpu_capability.snapshot(
                active_backend=backend if isinstance(backend, str) else None,
                refresh=True,
            )
            resp["type"] = "gpu_capability"
            resp["data"] = snapshot
        except Exception as exc:
            self._respond_with_error(resp, exc, "get_gpu_capability")
        return resp

    def _handle_start_cuda_download(self, data: object | None, resp: dict) -> dict:
        """Handle the ``start_cuda_download`` IPC command (single-flight)."""
        try:
            from voice_typer.server.cuda_install.service import get_service

            log.info("[IPC] start_cuda_download called")
            resp["type"] = "cuda_download_state"
            resp["data"] = get_service().start()
        except Exception as exc:
            self._respond_with_error(resp, exc, "start_cuda_download")
        return resp

    def _handle_cancel_cuda_download(self, data: object | None, resp: dict) -> dict:
        """Handle the ``cancel_cuda_download`` IPC command (instant control)."""
        try:
            from voice_typer.server.cuda_install.service import get_service

            log.info("[IPC] cancel_cuda_download called")
            resp["type"] = "cuda_download_state"
            resp["data"] = get_service().cancel()
        except Exception as exc:
            self._respond_with_error(resp, exc, "cancel_cuda_download")
        return resp

    def _handle_ack_cuda_activation(self, data: object | None, resp: dict) -> dict:
        """Handle ``ack_cuda_activation``: clear a shown activation failure."""
        try:
            from voice_typer.server.cuda_install import activation

            activation.acknowledge()
            resp["type"] = "ack"
            resp["data"] = {"ok": True}
        except Exception as exc:
            self._respond_with_error(resp, exc, "ack_cuda_activation")
        return resp
