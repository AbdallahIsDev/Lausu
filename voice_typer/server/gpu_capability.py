"""Single authority for GPU capability: hardware, driver, stack, per backend.

Four states the UI branches on:

* ``no_nvidia_gpu`` — nothing to offer; the GPU control stays hidden.
* ``driver_missing`` — an NVIDIA adapter is installed but the OS driver is
  not; only the vendor installer can fix that.
* ``gpu_present_cuda_missing`` — the driver works, the user-level CUDA
  runtime is absent; this is the state the download modal exists for.
* ``gpu_ready`` — at least one local backend can serve GPU right now.

Per-backend readiness is reported alongside the state because "GPU works"
is not global: CTranslate2 (Whisper) needs cuBLAS/cuDNN, the ONNX backends
need a CUDA-enabled onnxruntime, and Qwen is pinned to CPU by design.

TWO SIGNALS, DELIBERATELY DIFFERENT
-----------------------------------
``cuda_ready`` is the historical "ANY gpu-capable local backend is ready"
value. It is kept for backward compatibility and for the coarse four-state
verdict, but it is NOT a decision signal: on a machine where CTranslate2
sees the GPU and the installed ``onnxruntime`` is the CPU-only wheel,
``cuda_ready`` is True while Parakeet/Qwen cannot serve at all. Gating on
it produced a silent CPU fallback with no route to the CUDA download.

* ``stack_complete`` — EVERY gpu-capable LOCAL backend is ready, i.e. both
  the CTranslate2 path and the ORT path work. This is the signal an
  install must satisfy before the app may persist ``device="cuda"``.
* ``active_backend_gpu_ready`` — the backend named by ``asr_backend`` can
  serve GPU. This is the signal the UI and the ``set_config`` guard use,
  because "GPU is fine for Whisper" says nothing about the engine the user
  actually selected.

``backend_ready(backends, name)`` is the one lookup both of those use.
"""

from __future__ import annotations

import importlib
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

from voice_typer.server.platform_utils import is_linux, is_macos, is_windows

log = logging.getLogger(__name__)

NO_GPU = "no_nvidia_gpu"
DRIVER_MISSING = "driver_missing"
CUDA_MISSING = "gpu_present_cuda_missing"
READY = "gpu_ready"

NVIDIA_DRIVER_URL = "https://www.nvidia.com/en-us/drivers/"

_CACHE_TTL_S = 30.0
_SMI_TIMEOUT_S = 2.0
_GPU_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
_DRIVER_SERVICE_KEY = r"SYSTEM\CurrentControlSet\Services\nvlddmkm"

_lock = threading.Lock()
_cache: dict[str, Any] | None = None
_cache_at = 0.0
_ort_providers: list[str] | None = None


def reset_cache() -> None:
    """Drop cached probe results (tests, and after an install completes)."""
    global _cache, _cache_at, _ort_providers
    with _lock:
        _cache = None
        _cache_at = 0.0
        _ort_providers = None


def snapshot(*, active_backend: str | None = None, refresh: bool = False) -> dict[str, Any]:
    """Full capability report for the renderer (never raises).

    Always emits ``active_backend`` and a BOOLEAN
    ``active_backend_gpu_ready``: a caller that forgets to pass the backend
    gets the conservative whole-stack answer instead of a missing key,
    because a renderer checking ``=== false`` must never read ``undefined``
    as "ready".
    """
    base = _base(refresh=refresh)
    data = dict(base)
    data["download"] = {
        **base["download"],
        "progress": _progress(),
    }
    data["activation"] = _activation()
    backend = active_backend if isinstance(active_backend, str) and active_backend else None
    data["active_backend"] = backend
    data["active_backend_gpu_ready"] = (
        backend_ready(base["backends"], backend) if backend else base["stack_complete"]
    )
    return data


def hardware_present() -> bool:
    """Cheap gate for the sidebar control (cached with the rest of the probe)."""
    return bool(_base(refresh=False)["hardware_present"])


def _base(*, refresh: bool) -> dict[str, Any]:
    global _cache, _cache_at
    now = time.monotonic()
    with _lock:
        if not refresh and _cache is not None and now - _cache_at < _CACHE_TTL_S:
            return _cache
    probed = _probe()
    with _lock:
        _cache = probed
        _cache_at = now
    return probed


def _probe() -> dict[str, Any]:
    gpus = _nvidia_smi_gpus()
    driver = bool(gpus) or _driver_present()
    hardware = bool(gpus) or driver or _adapter_present()
    if not hardware:
        state = NO_GPU
    elif not driver:
        state = DRIVER_MISSING
    else:
        state = None  # decided after the backend probe
    backends = _backends(probe_ready=state is None)
    # "Any backend" (historical, coarse state verdict only).
    cuda_ready = any(b["gpu_ready"] for b in backends if b["gpu_capable"])
    # "Every gpu-capable LOCAL backend" — the honest "the stack works" signal.
    # Whisper-ready must never mask a CPU-only onnxruntime (and vice versa).
    local_capable = [b for b in backends if b["gpu_capable"] and b["local"]]
    stack_complete = bool(local_capable) and all(b["gpu_ready"] for b in local_capable)
    if state is None:
        state = READY if cuda_ready else CUDA_MISSING
    download = _download_info(hardware)
    return {
        "state": state,
        "hardware_present": hardware,
        "driver_present": driver,
        "gpu_names": gpus,
        "cuda_ready": cuda_ready,
        "stack_complete": stack_complete,
        "backends": backends,
        "download": download,
        "driver_url": NVIDIA_DRIVER_URL,
    }


def _backends(*, probe_ready: bool) -> list[dict[str, Any]]:
    whisper_ready = False
    ort_ready = False
    if probe_ready:
        try:
            from voice_typer.server import device_caps

            whisper_ready = device_caps.gpu_available()
        except Exception:
            log.debug("[GPU] whisper CUDA probe failed", exc_info=True)
        ort_ready = _ort_cuda_available()
    whisper_detail = "ready" if whisper_ready else ("cuda_missing" if probe_ready else "no_gpu")
    ort_detail = "ready" if ort_ready else ("cuda_missing" if probe_ready else "no_gpu")
    return [
        {
            "name": "whisper",
            "local": True,
            "gpu_capable": True,
            "gpu_ready": whisper_ready,
            "detail": whisper_detail,
        },
        {
            "name": "parakeet",
            "local": True,
            "gpu_capable": True,
            "gpu_ready": ort_ready,
            "detail": ort_detail,
        },
        # The Qwen engine pins its ONNX session to CPU; offering GPU there
        # would be a switch that can never take effect.
        {
            "name": "qwen",
            "local": True,
            "gpu_capable": False,
            "gpu_ready": False,
            "detail": "cpu_only_backend",
        },
        {
            "name": "cloud",
            "local": False,
            "gpu_capable": False,
            "gpu_ready": False,
            "detail": "not_local",
        },
    ]


def backend_ready(backends: list[dict[str, Any]], name: str) -> bool:
    """True when the named backend can serve GPU right now.

    The single lookup behind ``active_backend_gpu_ready``; a backend that is
    not listed (or is not ``gpu_capable``) answers ``False`` rather than
    guessing, so a typo'd backend name fails closed.
    """
    for entry in backends:
        if entry.get("name") == name:
            return bool(entry.get("gpu_ready"))
    return False


def _download_info(hardware: bool) -> dict[str, Any]:
    from voice_typer.server.cuda_install.manifest import (
        artifacts_for_current_runtime,
        total_bytes,
    )

    artifacts = artifacts_for_current_runtime()
    if not is_windows():
        supported = False
        reason = "unsupported_platform"
    elif not artifacts:
        supported = False
        reason = "unsupported_python"
    else:
        supported = True
        reason = None
    installed = False
    if artifacts:
        from voice_typer.server.cuda_install import installer

        try:
            installed = installer.is_installed(artifacts)
        except Exception:
            installed = False
    return {
        "supported": supported and hardware,
        "reason": reason if hardware else "no_gpu",
        "total_bytes": total_bytes(artifacts),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "installed": installed,
    }


def _progress() -> dict[str, Any]:
    try:
        from voice_typer.server.cuda_install.service import get_service

        return get_service().snapshot()
    except Exception:
        return {
            "status": "idle",
            "artifact": None,
            "artifact_index": 0,
            "artifact_count": 0,
            "bytes_done": 0,
            "bytes_total": 0,
            "percent": 0.0,
            "speed_bps": 0,
            "eta_seconds": None,
            "error": None,
        }


def _activation() -> dict[str, Any] | None:
    try:
        from voice_typer.server.cuda_install import state

        record = state.read()
    except Exception:
        return None
    if record is None:
        return None
    return {"state": record.get("state"), "reason": record.get("reason")}


# ---- hardware / driver probes ------------------------------------------------


def _nvidia_smi_path() -> str | None:
    if not (is_windows() or is_linux()):
        return None
    found = shutil.which("nvidia-smi")
    if found:
        return found
    if is_windows():
        root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        candidate = os.path.join(root, "System32", "nvidia-smi.exe")
        if os.path.isfile(candidate):
            return candidate
    return None


def _nvidia_smi_gpus() -> list[str]:
    """GPU names reported by ``nvidia-smi -L`` (empty when unavailable)."""
    path = _nvidia_smi_path()
    if not path:
        return []
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if is_windows() else 0
    try:
        proc = subprocess.run(
            [path, "-L"],
            capture_output=True,
            text=True,
            timeout=_SMI_TIMEOUT_S,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("GPU")]


def _driver_present() -> bool:
    if is_macos():
        return False
    if _nvidia_smi_gpus():
        return True
    if is_windows():
        return _windows_driver_service_present()
    return os.path.isfile("/proc/driver/nvidia/version")


def _adapter_present() -> bool:
    if is_windows():
        return _windows_nvidia_adapter_present()
    if is_linux():
        return _linux_nvidia_pci_present()
    return False


def _windows_nvidia_adapter_present() -> bool:
    """An NVIDIA display adapter is enumerated by the OS (driver may be absent)."""
    try:
        import winreg
    except ImportError:
        return False
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _GPU_CLASS_KEY)
    except OSError:
        return False
    with root:
        index = 0
        while True:
            try:
                subkey = winreg.EnumKey(root, index)
            except OSError:
                return False
            index += 1
            try:
                with winreg.OpenKey(root, subkey) as key:
                    for value_name in ("DriverDesc", "ProviderName"):
                        try:
                            value, _kind = winreg.QueryValueEx(key, value_name)
                        except OSError:
                            continue
                        if isinstance(value, str) and "nvidia" in value.lower():
                            return True
            except OSError:
                continue


def _windows_driver_service_present() -> bool:
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _DRIVER_SERVICE_KEY):
            return True
    except OSError:
        return False


def _linux_nvidia_pci_present() -> bool:
    base = "/sys/bus/pci/devices"
    try:
        entries = os.listdir(base)
    except OSError:
        return False
    for name in entries:
        try:
            with open(os.path.join(base, name, "vendor"), encoding="ascii") as handle:
                if handle.read().strip().lower() == "0x10de":
                    return True
        except OSError:
            continue
    return False


def _ort_cuda_available() -> bool:
    global _ort_providers
    if _ort_providers is not None:
        return "CUDAExecutionProvider" in _ort_providers
    providers: list[str] = []
    try:
        from voice_typer.server.cuda_install.paths import ensure_install_on_sys_path

        ensure_install_on_sys_path()
        # importlib keeps onnxruntime out of the sidecar's static module graph
        # (same reason device_caps probes through importlib).
        ort = importlib.import_module("onnxruntime")
        providers = [str(p) for p in ort.get_available_providers()]
    except Exception:
        log.debug("[GPU] onnxruntime provider probe failed", exc_info=True)
    _ort_providers = providers
    return "CUDAExecutionProvider" in providers
