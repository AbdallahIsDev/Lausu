"""IPC event types + best-effort publish for the runtime pack family."""

from __future__ import annotations

import logging
from types import ModuleType

log = logging.getLogger(__name__)


OFFLINE_PACK_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "offline_pack_download_started",
        "offline_pack_download_progress",
        "offline_pack_download_completed",
        "offline_pack_download_failed",
        "offline_pack_verified",
        "offline_pack_missing",
        "offline_pack_corrupt",
        "offline_pack_ready",
        "offline_pack_outdated",
        "worker_started",
        "worker_crashed",
        "worker_unloaded",
        "transcribe_offline",
        "transcribe_offline_result",
    }
)


# Stable machine-readable reasons; the renderer maps these to localized copy.
PACK_FAILURE_REASONS: frozenset[str] = frozenset(
    {
        "offline",
        "fetch_failed",
        "manifest_unavailable",
        "rate_limited",
        "disk_full",
        "locked",
        "sha256_mismatch",
        "install_failed",
        "io_error",
        "internal_error",
    }
)


def _publish_event(event_bus: ModuleType | None, event_type: str, payload: dict) -> None:
    """Best-effort publish, swallow errors (the bus is best-effort)."""
    if event_bus is None:
        return
    try:
        event_bus.publish({"type": event_type, "data": payload})
    except Exception:
        log.debug("[PACK] event_bus publish failed for %s", event_type, exc_info=True)


def publish_download_failure(
    event_bus: ModuleType | None,
    version: str,
    reason: str,
    **extra: object,
) -> None:
    """Publish one normalized ``offline_pack_download_failed`` payload."""
    safe_reason = reason if reason in PACK_FAILURE_REASONS else "internal_error"
    _publish_event(
        event_bus,
        "offline_pack_download_failed",
        {"version": version, "reason": safe_reason, **extra},
    )
