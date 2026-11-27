"""Shutdown for the unified lifecycle: cancel loads, stop runtimes."""

from __future__ import annotations

import logging

from . import idle, loading, registry

log = logging.getLogger(__name__)


def shutdown_all() -> None:
    loading.cancel_loads()
    idle.shutdown()
    for kind in registry.kinds():
        policy = registry.get(kind)
        if policy is None:
            continue
        try:
            policy.unload()
        except Exception:
            log.debug("[LIFECYCLE] %s shutdown unload failed", kind, exc_info=True)
    loading.join_loaders(timeout_s=1.0)


__all__ = ["shutdown_all"]
