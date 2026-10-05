"""Compute-device capability probe (CPU vs CUDA) + fallback broadcast.

Single-purpose module: answers "can this machine run models on GPU?"
fast enough for startup and every ``get_config`` call. Results are
cached per process; GPUs don't hot-plug, so one probe is enough.
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)

# Total wall-clock budget for one probe. The ctypes DLL check is
# microseconds; the subprocess/ORT steps each carry their own shorter
# timeout so the sum stays under this cap.
_PROBE_BUDGET_S = 0.9

_cached_available: bool | None = None


def reset_cache() -> None:
    """Drop the cached probe result (tests only)."""
    global _cached_available
    _cached_available = None


def gpu_available(*, refresh: bool = False) -> bool:
    """Return True when a CUDA-capable GPU can run models here."""
    global _cached_available
    if _cached_available is not None and not refresh:
        return _cached_available
    try:
        # Configure first (idempotent, cheap after the first call): the
        # DLL scan extends the loader search path, and probing before
        # it would cache a False recorded against the unfixed path.
        from voice_typer.server.nvidia_dll_paths import _configure_nvidia_dll_paths

        _configure_nvidia_dll_paths()
    except Exception:
        log.debug("[DEVICE] NVIDIA DLL configure failed, probing anyway", exc_info=True)
    _cached_available = _probe()
    return _cached_available


def _probe() -> bool:
    """Run the capability checks inside the wall-clock budget."""
    deadline = time.monotonic() + _PROBE_BUDGET_S
    try:
        from voice_typer.server.platform_utils import is_macos

        if is_macos():
            return False
    except Exception:
        log.debug("[DEVICE] platform check failed, assuming no GPU", exc_info=True)
        return False
    try:
        from voice_typer.server.nvidia_dll_paths import _cuda_runtime_available

        if not _cuda_runtime_available():
            return False
    except Exception:
        log.debug("[DEVICE] CUDA DLL probe failed", exc_info=True)
        return False
    if time.monotonic() >= deadline:
        return True
    # NOTE: importlib (not import statements) on purpose, same reason
    # as SystemWhisperEngine.load: static imports would pull
    # ctranslate2 into the frozen sidecar and trip the slim-core ML
    # ratchet (scripts/slim_core_ml_ratchet_check.py).
    import importlib

    try:
        ctranslate2 = importlib.import_module("ctranslate2")
        # Whisper transcribes via ctranslate2, never via onnxruntime: a
        # CUDA device here means GPU transcription works even when the
        # CPU-only onnxruntime wheel (no CUDAExecutionProvider) is
        # installed, so return without consulting ORT below.
        return ctranslate2.get_cuda_device_count() > 0
    except ImportError:
        pass
    except Exception:
        log.debug("[DEVICE] ctranslate2 device count failed", exc_info=True)
        return False
    if time.monotonic() >= deadline:
        return True
    # ORT answers for the Parakeet/Qwen ONNX backends only: Whisper
    # returned above when ctranslate2 is present, so reaching here
    # means ctranslate2 is absent and only ONNX backends remain.
    try:
        ort = importlib.import_module("onnxruntime")
        providers = ort.get_available_providers()
        return "CUDAExecutionProvider" in providers
    except ImportError:
        pass
    except Exception:
        log.debug("[DEVICE] onnxruntime provider check failed", exc_info=True)
    try:
        from voice_typer.server.platform_utils import is_linux

        if is_linux():
            import shutil
            import subprocess

            nvidia_smi = shutil.which("nvidia-smi")
            if nvidia_smi is None:
                return False
            try:
                proc = subprocess.run(
                    [nvidia_smi, "-L"],
                    capture_output=True,
                    timeout=max(0.1, deadline - time.monotonic()),
                )
                return proc.returncode == 0 and bool(proc.stdout.strip())
            except Exception:
                log.debug("[DEVICE] nvidia-smi probe failed", exc_info=True)
                return False
    except Exception:
        log.debug("[DEVICE] linux GPU probe failed", exc_info=True)
        return False
    return True


def publish_device_cpu_fallback(reason: str) -> None:
    """Broadcast a session-scoped GPU->CPU switch to the renderer.

    Emits ``config_changed`` with ``{"device": "cpu"}`` so every
    consumer of the shared config snapshot (sidebar toggle, model
    pages) shifts to CPU without a ``get_config`` round-trip. The
    on-disk config is intentionally untouched: a transient error
    (OOM, missing DLL at first use) must not pin the machine to CPU
    forever; the startup reconciler owns the persisted value.
    """
    try:
        from voice_typer.server import event_bus as _event_bus

        _event_bus.publish({"type": "config_changed", "data": {"device": "cpu"}})
    except Exception:
        log.debug("[DEVICE] config_changed fallback publish failed", exc_info=True)
    log.info("[DEVICE] GPU transcription failed (%s), session continues on CPU", reason)
