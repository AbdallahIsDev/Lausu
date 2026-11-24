"""Compute-device capability probe (CPU vs GPU) + fallback broadcast.

Single-purpose module: answers "can this machine run models on GPU?"
fast enough for startup and every ``get_config`` call. Results are
cached per process; GPUs don't hot-plug, so one probe is enough.

The verdict comes from the shipped speech runtime contract, not from a
Python inference wheel: the worker's runner publishes its supported
backends (``cpu`` / ``vulkan`` / ``cuda``) in ``contract.json`` beside the
native library. An unreadable contract is UNVERIFIED and keeps the app on
CPU rather than persisting a GPU setting the runtime cannot serve.
"""

from __future__ import annotations

import json
import logging
import time

log = logging.getLogger(__name__)

# Total wall-clock budget for one probe. The ctypes DLL check is
# microseconds; the contract read is one small local file.
_PROBE_BUDGET_S = 0.9

_cached_available: bool | None = None
_last_probe_unverified: bool = False


def reset_cache() -> None:
    """Drop the cached probe result (tests only)."""
    global _cached_available, _last_probe_unverified
    _cached_available = None
    _last_probe_unverified = False


def is_gpu_unverified() -> bool:
    """True when the last probe could not read the runtime backend contract."""
    return _last_probe_unverified


def gpu_available(*, refresh: bool = False) -> bool:
    """Return True when a GPU-capable speech runtime is available here."""
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


def _runner_backends() -> set[str] | None:
    """Read the backends published by the shipped speech runtime contract."""
    try:
        from voice_typer.worker.asr_runner.runner import library_dir

        directory = library_dir()
        if directory is None:
            return None
        contract = directory / "contract.json" if directory.is_dir() else directory.parent / "contract.json"
        data = json.loads(contract.read_text(encoding="utf-8"))
        backends = data.get("backends")
        if not isinstance(backends, list):
            return None
        return {str(backend).strip().lower() for backend in backends}
    except Exception:
        log.debug("[DEVICE] speech runtime contract unreadable", exc_info=True)
        return None


def _probe() -> bool:
    """Run the capability checks inside the wall-clock budget."""
    global _last_probe_unverified
    _last_probe_unverified = False
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
        _last_probe_unverified = True
        return False
    backends = _runner_backends()
    if backends is None:
        _last_probe_unverified = True
        log.warning("[DEVICE] GPU UNVERIFIED: speech runtime contract unavailable, keeping CPU")
        return False
    return bool(backends & {"vulkan", "cuda"})


def publish_device_cpu_fallback(reason: str) -> None:
    """Broadcast a session-scoped GPU->CPU switch to the renderer.

    Emits ``config_changed`` with ``{"device": "cpu", "active_device": "cpu"}``
    so every consumer of the shared config snapshot (sidebar toggle, model
    pages) shifts to CPU without a ``get_config`` round-trip. The
    on-disk config is intentionally untouched: a transient error
    (OOM, missing DLL at first use) must not pin the machine to CPU
    forever; the startup reconciler owns the persisted value.
    """
    try:
        from voice_typer.server import event_bus as _event_bus

        _event_bus.publish({"type": "config_changed", "data": {"device": "cpu", "active_device": "cpu"}})
    except Exception:
        log.debug("[DEVICE] config_changed fallback publish failed", exc_info=True)
    log.info("[DEVICE] GPU transcription failed (%s), session continues on CPU", reason)
