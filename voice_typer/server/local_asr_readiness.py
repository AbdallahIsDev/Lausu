"""Cheap pre-mic answer: can the local ASR provider actually serve a press?

Uses the same model, pack and native-runtime resolvers as the load path, but
never creates a backend, opens a worker socket or downloads anything.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def local_asr_problem(config: Any) -> str | None:
    """Return the actionable reason key, or ``None`` when local ASR is ready."""
    # Only the canonical Config has real filesystem truth; test doubles stay
    # ready so unit tests do not depend on this machine's pack install.
    from voice_typer.server.config import Config as _ConfigCls

    if not isinstance(config, _ConfigCls):
        return None

    from voice_typer.server.model_registry import NO_MODEL_SIZE
    from voice_typer.server.tray_models import is_active_model_downloaded

    size = str(getattr(config, "model_size", "") or "")
    if not size or size == NO_MODEL_SIZE:
        return "no_model_selected"
    if not is_active_model_downloaded(config):
        return "model_not_downloaded"

    from voice_typer.server.service import update_check

    try:
        if update_check._local_offline_pack_version() is None:
            return "offline_pack_missing"
    except Exception:
        log.debug("[READINESS] offline pack probe failed", exc_info=True)
        return "offline_pack_missing"

    from voice_typer.worker.asr_runner.runner import library_dir

    try:
        if library_dir() is None:
            return "local_runtime_missing"
    except Exception:
        log.debug("[READINESS] native runtime probe failed", exc_info=True)
        return "local_runtime_missing"
    return None


# Internal seam for app-wiring tests only: they exercise start/stop/callback
# plumbing with a real Config but no installed pack. Production never rebinds
# this name; the default is the real probe above.
readiness_probe = local_asr_problem

__all__ = ["local_asr_problem", "readiness_probe"]
