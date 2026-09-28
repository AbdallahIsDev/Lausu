"""Dictation worker-path gate (ADR-0025 C5, sites 1+2).

One purpose only: decide whether a batch dictation may use the
runtime-pack worker instead of in-process inference. The policy stays
here so the pipeline branch stays a thin caller.
"""

from __future__ import annotations

import logging
from typing import Any

from voice_typer.server.log_rate_limit import log_rate_limited

log = logging.getLogger(__name__)


def _is_cloud_backend(backend: object) -> bool:
    """True when ``backend`` is a cloud (network) engine.

    Name check first: test doubles share the class name without sharing
    the import, and the import itself must never block a caller.
    """
    if type(backend).__name__ == "CloudEngine":
        return True
    try:
        from voice_typer.server.cloud_engines import CloudEngine

        return isinstance(backend, CloudEngine)
    except Exception:  # noqa: BLE001, import must never block a caller
        return False


def worker_path_for_backend(backend: object) -> tuple[bool, str]:
    """True only when ``backend``'s work may move to the pack worker.

    Backend-object form of the gate for callers that hold an engine but
    no app (media ingest). Same three legs and reasons as
    :func:`worker_path_available`, single implementation (E7).
    """
    if _is_cloud_backend(backend):
        # WHY: cloud audio must never be re-routed to the offline worker.
        log_rate_limited(log, logging.INFO, "[WORKER-PATH] gate off: cloud backend", key="worker-path:cloud")
        return False, "cloud_backend"
    try:
        from voice_typer.server.service import update_check

        pack_present = update_check._local_offline_pack_version() is not None
    except Exception:
        # WHY: mirror the transcribe_offline fail-safe, degrade instead of queueing blindly.
        log_rate_limited(log, logging.DEBUG, "[WORKER-PATH] gate off: pack check failed", exc_info=True)
        return False, "pack_check_failed"
    if not pack_present:
        log_rate_limited(
            log, logging.INFO, "[WORKER-PATH] gate off: offline pack missing", key="worker-path:pack-missing"
        )
        return False, "offline_pack_missing"
    try:
        from voice_typer.server import worker_client

        port = worker_client.get_shared_client().port
    except Exception:
        log_rate_limited(log, logging.DEBUG, "[WORKER-PATH] gate off: worker client unreadable", exc_info=True)
        return False, "worker_unknown"
    if port is None:
        log_rate_limited(log, logging.INFO, "[WORKER-PATH] gate off: no worker port", key="worker-path:no-port")
        return False, "worker_no_port"
    return True, "ok"


def worker_path_available(app: Any) -> tuple[bool, str]:
    """True only when a batch dictation for ``app`` may use the worker.

    App form of the gate for callers that hold models but resolve the
    backend per cycle (dictation pipeline). Resolves the active backend
    once, then delegates to :func:`worker_path_for_backend` (E7: one
    gate, two call shapes).
    """
    try:
        active = app.models.active_transcriber()
    except Exception:
        log_rate_limited(log, logging.DEBUG, "[WORKER-PATH] gate off: backend unreadable", exc_info=True)
        return False, "backend_unknown"
    return worker_path_for_backend(active)
