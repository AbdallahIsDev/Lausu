"""Post-ready optional preload, gated by Fast Startup and physical memory.

The local ASR load stays unconditional in ``_phases_late.py``; this module
only touches OPTIONAL kinds that have no dedicated startup hook.
"""

from __future__ import annotations

import logging
import threading

from . import loading, memory, registry

log = logging.getLogger(__name__)


def prewarm_optional_at_startup(app: object) -> None:
    registry.bind_app(app)
    config = getattr(app, "config", None)
    if config is None:
        return
    from .idle import apply_idle_setting

    apply_idle_setting(getattr(config, "model_idle_unload_minutes", 0))
    if not bool(getattr(config, "fast_startup", False)):
        log.debug("[LIFECYCLE] optional startup preload skipped (fast_startup off)")
        return

    def _run() -> None:
        for kind in registry.ordered_kinds():
            policy = registry.get(kind)
            if policy is None or policy.residency != "optional" or policy.dedicated_startup:
                continue
            try:
                if not policy.applicable(config):
                    continue
            except Exception:
                log.debug("[LIFECYCLE] %s applicability check failed", kind, exc_info=True)
                continue
            if not memory.memory_fits(policy):
                try:
                    readable = memory.available_physical_bytes() is not None
                except Exception:
                    readable = False
                reason = "insufficient memory" if readable else "memory unavailable"
                log.info("[LIFECYCLE] %s startup preload skipped (%s)", kind, reason)
                continue
            loading.load_one(policy, config)

    thread = threading.Thread(target=_run, name="model-lifecycle-startup", daemon=True)
    # daemon=True: a slow optional preload must never delay app quit (RACE-016).
    thread.start()


__all__ = ["prewarm_optional_at_startup"]
