"""Cheap pre-mic answer: can the local ASR provider actually serve a press?

Uses the same model, pack and native-runtime resolvers as the load path, but
never creates a backend, opens a worker socket or downloads anything. Every
probe is best-effort: an unreadable filesystem or an unavailable resolver must
FAIL OPEN (a debug line, never a refusal and never an exception on the press
path). A refusal is only returned for a clean, readable "missing" verdict.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from types import ModuleType
from typing import Any

log = logging.getLogger(__name__)

ENV_TRANSCRIBE_LIBRARY = "TRANSCRIBE_LIBRARY"
LIBRARY_BASENAME = "transcribe.dll" if os.name == "nt" else "libtranscribe.so"
_WORKER_BASENAMES = ("lausu-worker.exe", "lausu-worker")


def resolve_native_runtime_dir(
    *,
    module_globals: dict[str, object] | None = None,
    sys_module: ModuleType | None = None,
) -> Path | None:
    """ONE resolver for the shipped native runtime directory.

    Both the worker's library loader and this pre-mic probe call this function,
    so they cannot disagree about where ``transcribe.dll`` lives. It reads only
    env/filesystem facts and lives in the sidecar-safe server package: importing
    it never loads a DLL and never pulls in the worker-only runner module.
    """
    from voice_typer.server.media_ingest.ffmpeg_binaries import (
        _shipped_dirs,
        bundled_bin_dir,
        is_frozen_build,
    )

    override = os.environ.get(ENV_TRANSCRIBE_LIBRARY, "").strip()
    if override:
        candidate = Path(override).expanduser()
        return candidate.parent if candidate.is_file() else None
    for directory in _shipped_dirs():
        for candidate in (directory, directory / "transcribe-cpp"):
            if (candidate / LIBRARY_BASENAME).is_file():
                return candidate
    if not is_frozen_build(module_globals=module_globals, sys_module=sys_module):
        bundled = bundled_bin_dir(module_globals=module_globals, sys_module=sys_module)
        return bundled if (bundled / LIBRARY_BASENAME).is_file() else None
    return None


def _worker_is_available() -> bool:
    """True when a worker exists even without an offline pack.

    A dev host runs the worker from PYTHONPATH (`[WORKER-DEV]`) and the full
    (non-slim) installer bundles the worker exe beside the host. Both are
    working local setups with NO pack. The relayed worker port is the live
    proof for the dev case; the exe probe covers a cold full install.
    """
    from voice_typer.server.media_ingest.ffmpeg_binaries import bundled_bin_dir

    try:
        base = bundled_bin_dir()
        if any((base / name).is_file() for name in _WORKER_BASENAMES):
            return True
    except Exception:
        log.debug("[READINESS] bundled-worker probe failed", exc_info=True)
    try:
        from voice_typer.server.worker_client import get_shared_client

        return get_shared_client().port is not None
    except Exception:
        log.debug("[READINESS] worker-port probe failed", exc_info=True)
        return False


def local_asr_problem(config: Any) -> str | None:
    """Return the actionable reason key, or ``None`` when local ASR is ready.

    This is the single decision function for the pre-mic local readiness gate.
    Unknowns fail open: only a clean "missing" verdict becomes a refusal.
    """
    # Only the canonical Config has real filesystem truth; test doubles stay
    # ready so unit tests do not depend on this machine's pack install.
    from voice_typer.server.config import Config as _ConfigCls

    if not isinstance(config, _ConfigCls):
        return None

    from voice_typer.server.model_registry import NO_MODEL_SIZE

    size = str(getattr(config, "model_size", "") or "")
    if not size or size == NO_MODEL_SIZE:
        return "no_model_selected"

    try:
        from voice_typer.server.tray_models import is_active_model_downloaded

        if not is_active_model_downloaded(config):
            return "model_not_downloaded"
    except Exception:
        log.debug("[READINESS] model probe failed", exc_info=True)

    # The pack is one way to ship the worker, not the only one: dev/source and
    # the full installer bundle it without a pack. Probe errors never refuse.
    try:
        from voice_typer.server.service import update_check

        pack_present = update_check._local_offline_pack_version() is not None
    except Exception:
        log.debug("[READINESS] offline pack probe failed", exc_info=True)
        pack_present = True
    if not pack_present and not _worker_is_available():
        return "offline_pack_missing"

    try:
        if resolve_native_runtime_dir() is None:
            return "local_runtime_missing"
    except Exception:
        log.debug("[READINESS] native runtime probe failed", exc_info=True)
    return None


# Internal seam for app-wiring tests only: they exercise start/stop/callback
# plumbing with a real Config but no installed pack. Production never rebinds
# this name; the default is the real probe above.
readiness_probe = local_asr_problem

__all__ = [
    "ENV_TRANSCRIBE_LIBRARY",
    "LIBRARY_BASENAME",
    "local_asr_problem",
    "readiness_probe",
    "resolve_native_runtime_dir",
]
