"""Teardown helper for the microphone volume guard watcher."""

from __future__ import annotations

import logging

# ``_run_with_timeout`` is looked up DYNAMICALLY from
from voice_typer.server import shutdown_controller as _sc  # noqa: F401


def _run_with_timeout(*args, **kwargs):
    return _sc._run_with_timeout(*args, **kwargs)


log = logging.getLogger(__name__)


def teardown_mic_guard(controller) -> None:
    """Stop the mic-guard watcher thread before the process exits."""
    app = controller._app
    guard = getattr(app, "_mic_guard", None)
    if guard is None:
        return
    try:
        _run_with_timeout("mic_guard_stop", guard.stop, timeout=5.0)
    except Exception:
        log.debug("[CLEANUP] mic guard stop failed", exc_info=True)


__all__ = ["teardown_mic_guard"]
