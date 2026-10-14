"""Reads stay responsive while a slow mutating command holds the dispatch lock.

Regression cover for the startup outage where a multi-second model load
(``large-v3`` ≈ 41s on first dev boot) coincided with ``get_config``
5s renderer timeouts on the Plugins page and a false "Lost connection"
screen. The model loader runs on its own ``ModelLoad`` thread and never
takes ``_dispatch_lock``; pure reads (``_READONLY_COMMANDS``) bypass that
lock in ``DispatcherMixin._dispatch`` and ride the reserved WS readonly
pool. These tests pin the bypass: while a slow mutating handler holds the
lock, ``get_config`` / ``get_status`` / ``get_plugins`` must still
answer immediately instead of queueing behind the holder.
"""

from __future__ import annotations

import threading
import time

from tests.fixtures.ipc_test_helpers import make_ipc_server_with_fakes

# The fake mutating handler holds the dispatch lock this long. Reads must
# finish well inside it; a read that queued behind the lock would take at
# least this long (or hit the 12s ``server.busy`` give-up).
_HOLDER_SLEEP_S = 5.0
# Generous upper bound for a lock-free read (healthy path is milliseconds;
# the margin only absorbs slow CI schedulers, not lock queueing).
_READ_BUDGET_S = 4.0


def _dispatch_slow_mutator_while_holding_lock(server, acquired: threading.Event) -> None:
    """Run a slow mutating command so it holds ``_dispatch_lock``."""
    server._dispatch({"type": "clear_history", "id": "slow"})
    acquired.set()


def test_get_config_answers_while_slow_mutator_holds_dispatch_lock() -> None:
    """``get_config`` bypasses ``_dispatch_lock`` held by a slow mutator."""
    server, _app, _service = make_ipc_server_with_fakes()
    acquired = threading.Event()

    def _slow_clear_history(data, resp):
        acquired.set()
        time.sleep(_HOLDER_SLEEP_S)
        resp["type"] = "result"
        resp["data"] = {}
        return resp

    server._handle_clear_history = _slow_clear_history  # type: ignore[method-assign]
    worker = threading.Thread(target=_dispatch_slow_mutator_while_holding_lock, args=(server, acquired), daemon=True)
    worker.start()
    assert acquired.wait(timeout=10.0), "slow mutating handler never took the dispatch lock"

    started = time.monotonic()
    result = server._dispatch({"type": "get_config", "id": "probe"})
    elapsed = time.monotonic() - started

    assert result is not None
    assert result["type"] == "config"
    assert elapsed < _READ_BUDGET_S, f"get_config queued behind the dispatch lock ({elapsed:.1f}s)"
    worker.join(timeout=10.0)


def test_status_and_plugins_answer_while_slow_mutator_holds_dispatch_lock() -> None:
    """``get_status`` / ``get_plugins`` also bypass a wedged dispatch lock."""
    server, _app, _service = make_ipc_server_with_fakes()
    acquired = threading.Event()

    def _slow_clear_history(data, resp):
        acquired.set()
        time.sleep(_HOLDER_SLEEP_S)
        resp["type"] = "result"
        resp["data"] = {}
        return resp

    server._handle_clear_history = _slow_clear_history  # type: ignore[method-assign]
    worker = threading.Thread(target=_dispatch_slow_mutator_while_holding_lock, args=(server, acquired), daemon=True)
    worker.start()
    assert acquired.wait(timeout=10.0), "slow mutating handler never took the dispatch lock"

    for cmd, ok_type in (("get_status", "status"), ("get_plugins", "plugins")):
        started = time.monotonic()
        result = server._dispatch({"type": cmd, "id": f"probe-{cmd}"})
        elapsed = time.monotonic() - started
        assert result is not None
        assert result["type"] == ok_type, f"{cmd} returned {result!r}"
        assert elapsed < _READ_BUDGET_S, f"{cmd} queued behind the dispatch lock ({elapsed:.1f}s)"
    worker.join(timeout=10.0)
