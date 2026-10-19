"""Drive ``shutdown.cleanup.do_cleanup`` without running real teardowns.

Both shutdown edge-case suites need the real cleanup body (shutdown
bookkeeping ordering) with the plan phases stubbed out, plus a real
cancellation registry so the discard mark is observable.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any
from unittest.mock import MagicMock

from voice_typer.server.recording_controller import RecordingController


def make_cancelled_registry_recording() -> Any:
    """A real ``RecordingController`` shell with only the cancel registry.

    ``_mark_cycle_cancelled`` resolves its helpers lazily via the class
    ``__getattr__``, so no ``__init__`` (and no recorder/models wiring) is
    needed.
    """
    recording = RecordingController.__new__(RecordingController)
    recording._cancelled_cycle_ids = OrderedDict()
    recording._cancelled_cycle_ids_lock = threading.Lock()
    return recording


def make_quiet_cleanup_controller(app: Any, *, order: list[str] | None = None) -> Any:
    """A controller whose sequenced/parallel shutdown phases are no-ops.

    When ``order`` is passed, the WS drain appends ``"drain"`` so callers
    can pin that shutdown bookkeeping lands before any teardown phase.
    """
    controller = MagicMock(name="shutdown_controller")
    controller._app = app
    controller._quit_lock = threading.Lock()
    controller._recorder_teardown_done = threading.Event()
    controller._recorder_force_closed = False
    controller._build_sequenced_plan = MagicMock(return_value=None)
    controller._build_parallel_plan = MagicMock(return_value=None)
    controller._run_plan = MagicMock(return_value=frozenset())
    controller._late_bookend_tray_stop = MagicMock()
    if order is None:
        controller._drain_ws_dispatch_pool = MagicMock()
    else:
        controller._drain_ws_dispatch_pool = MagicMock(side_effect=lambda *a: order.append("drain"))
    return controller


__all__ = ["make_cancelled_registry_recording", "make_quiet_cleanup_controller"]
