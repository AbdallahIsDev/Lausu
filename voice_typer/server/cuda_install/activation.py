"""Activate a finished install: prove the stack, then persist ``cuda``.

Runs in the respawned sidecar before ``reconcile_configured_device``. The
requested device only flips once a local backend actually reports GPU
readiness, so a broken install leaves the app on CPU with a recorded reason
instead of a GPU pill that cannot serve (C-UI-15).
"""

from __future__ import annotations

import contextlib
import importlib
import logging
import os
import sys
from typing import Any

from voice_typer.server.cuda_install import state
from voice_typer.server.cuda_install.paths import ensure_install_on_sys_path

log = logging.getLogger(__name__)

REASON_NOT_READY = "gpu_not_ready"
REASON_PERSIST_FAILED = "persist_failed"


def apply_pending_activation(app: Any) -> bool:
    """Switch to GPU when the pending install proves ready. Returns True on switch."""
    record = state.read()
    if record is None or record.get("state") != state.PENDING:
        return False
    ensure_install_on_sys_path()
    _reset_probes()
    from voice_typer.server import gpu_capability

    backend = getattr(app.config, "asr_backend", None)
    snapshot = gpu_capability.snapshot(
        active_backend=backend if isinstance(backend, str) else None,
        refresh=True,
    )
    # `stack_complete` — every gpu-capable LOCAL backend ready — is the
    # acceptance signal, not the historical `cuda_ready` ("any backend").
    # A CUDA wheel set that fixes CTranslate2 but leaves the CPU-only
    # onnxruntime in place would otherwise pass on Whisper alone and
    # persist `cuda` for a Parakeet user who can only fall back to CPU.
    if not snapshot.get("stack_complete"):
        state.write_failure(REASON_NOT_READY)
        log.warning(
            "[CUDA] installed stack is not complete (state=%s, active=%s ready=%s); "
            "staying on CPU",
            snapshot.get("state"),
            backend,
            snapshot.get("active_backend_gpu_ready"),
        )
        return False

    lock = getattr(app, "_config_mutation_lock", None)
    with contextlib.ExitStack() as stack:
        if lock is not None:
            stack.enter_context(lock)
        app.config.device = "cuda"
        try:
            saved = app.config.save()
        except Exception:
            saved = False
    if not saved:
        state.write_failure(REASON_PERSIST_FAILED)
        log.error("[CUDA] stack is ready but persisting device=cuda FAILED")
        return False

    state.clear()
    _publish_device("cuda")
    log.info("[CUDA] activation complete: device=cuda (stack verified)")
    return True


def acknowledge() -> None:
    """Clear a failed activation record once the user has seen the reason."""
    state.clear()


def _reset_probes() -> None:
    """Drop every cached CUDA verdict recorded before the install existed.

    Three caches have to die here, and the third is the subtle one:

    * ``device_caps`` memoises one boolean per process;
    * ``nvidia_dll_paths`` memoises the loader-search-path scan;
    * ``gpu_capability`` memoises the ORT provider list **and** the whole
      snapshot (30 s TTL), so a ``gpu_ready``/``cuda_missing`` verdict
      computed before the wheels landed would otherwise survive the
      install for the rest of the process.

    ``sys.modules`` is the fourth, and it is the one that actually broke
    the switch: ``device_caps._probe`` imports ``onnxruntime`` through
    ``importlib`` (see ``device_caps.py``), and the sidecar pre-warms that
    probe on a background thread from ``ipc/entrypoint.py`` long before
    this runs. The CPU-only wheel therefore wins the module name for the
    whole process, and every later ``importlib.import_module(
    "onnxruntime")`` returns that cached module no matter what is on
    ``sys.path``. Evicting the stale entry is what lets the freshly
    prepended install directory resolve.
    """
    if os.environ.get("CUDA_VISIBLE_DEVICES") == "":
        os.environ.pop("CUDA_VISIBLE_DEVICES", None)
    _evict_stale_onnxruntime()
    try:
        from voice_typer.server import device_caps

        device_caps.reset_cache()
    except Exception:
        log.debug("[CUDA] device_caps reset failed", exc_info=True)
    try:
        from voice_typer.server import nvidia_dll_paths

        nvidia_dll_paths.reset_configuration()
    except Exception:
        log.debug("[CUDA] nvidia DLL reconfigure failed", exc_info=True)
    try:
        from voice_typer.server import gpu_capability

        gpu_capability.reset_cache()
    except Exception:
        log.debug("[CUDA] gpu_capability reset failed", exc_info=True)


def _evict_stale_onnxruntime() -> None:
    """Drop an ``onnxruntime`` imported from outside the CUDA install.

    No-op when the install directory is not on ``sys.path`` (nothing to
    resolve to) or when ORT is not imported yet. Only the CUDA install's
    own copy is kept, so a re-import resolves the GPU wheel.
    """
    try:
        from voice_typer.server.cuda_install.paths import install_dir

        target = str(install_dir().resolve())
    except Exception:
        return
    if not any(_same_dir(entry, target) for entry in sys.path):
        return
    stale = [
        name
        for name, module in list(sys.modules.items())
        if (name == "onnxruntime" or name.startswith("onnxruntime."))
        and not _module_under(module, target)
    ]
    if not stale:
        return
    for name in stale:
        sys.modules.pop(name, None)
    # The directory may have appeared after the last import attempt; drop
    # the finder caches so the next import actually stats it.
    importlib.invalidate_caches()
    log.info(
        "[CUDA] evicted %d stale onnxruntime module(s) imported before the install",
        len(stale),
    )


def _same_dir(entry: str, target: str) -> bool:
    try:
        return os.path.normcase(os.path.abspath(entry)) == os.path.normcase(target)
    except Exception:
        return False


def _module_under(module: Any, target: str) -> bool:
    origin = getattr(module, "__file__", None)
    if not isinstance(origin, str) or not origin:
        return False
    try:
        return os.path.normcase(os.path.abspath(origin)).startswith(
            os.path.normcase(target) + os.sep
        )
    except Exception:
        return False


def _publish_device(device: str) -> None:
    try:
        from voice_typer.server import event_bus

        event_bus.publish({"type": "config_changed", "data": {"device": device}})
    except Exception:
        log.debug("[CUDA] config_changed publish failed", exc_info=True)
