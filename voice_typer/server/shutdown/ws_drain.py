"""WS dispatch + encode pool drain (extracted from ``shutdown_controller``)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from voice_typer.server._timeout_utils import _run_parallel_with_timeout
from voice_typer.server.sidecar_ws_internals.encode_pool import shutdown_encode_pool

log = logging.getLogger("voice_typer.server.shutdown_controller")

# Early-bookend item budgets. Each envelope is a BACKSTOP for a drain whose
# inner join cannot be interrupted, so it must clear that join by >=1s: at
# ~0.5s both expire in the same CPU stall and the generic warning wins.
_ENVELOPE_MARGIN_S = 0.5
_WS_DISPATCH_JOIN_S = 4.5
_WS_DISPATCH_BUDGET_S = 6.0
_WS_READONLY_JOIN_S = 2.5
_WS_READONLY_BUDGET_S = 4.0
_WS_ENCODE_JOIN_S = 1.8
_WS_ENCODE_BUDGET_S = 3.0


def _join_budget(start: float, envelope: float) -> float:
    """Seconds an inner join may run without outliving its own envelope.

    Derived from the item's own start so a drain queued behind a busy
    worker cannot overrun the envelope that bounds it. ``start <= 0``
    means the start is unknown: the envelope alone still applies.
    """
    now = time.monotonic()
    origin = start if start > 0.0 else now
    return max(0.0, origin + envelope - _ENVELOPE_MARGIN_S - now)


def _on_own_pool_worker(prefix: str) -> bool:
    """True when this thread is a worker of the pool being drained.

    ``ThreadPoolExecutor.shutdown(wait=True)`` never returns while the
    calling thread is one of the pool's own workers (quit() runs on a
    dispatch-pool worker for tray-menu/``shutdown`` commands); the join
    would burn its whole timeout and always warn. Callers skip the
    blocking join in that case (pending futures were already cancelled).
    """
    return threading.current_thread().name.startswith(prefix)


def _live_pool_workers(pool: object) -> list:
    """List of a pool's still-alive worker threads.

    May raise on a broken pool object; every caller guards (the
    summary reports ``unavailable``, the initiator check is fail-closed
    ``False``).
    """
    workers = list(getattr(pool, "_threads", None) or set())
    return [t for t in workers if t.is_alive()]


def _stuck_worker_summary(pool: object) -> str:
    """Best-effort one-line description of a pool's still-alive workers.

    Appended to drain-timeout warnings so the next occurrence names the
    stuck handler instead of just burning the timeout silently. Capped
    at 3 workers × 8 frames with filenames (the call SITE is what
    distinguishes a nested-quit stall from a download stall); never
    raises.
    """
    try:
        import sys as _sys
        import traceback as _traceback

        alive = _live_pool_workers(pool)
        if not alive:
            return "no live pool workers (handler finished, thread reaping)"
        frames = _sys._current_frames()
        parts: list[str] = []
        for worker in alive[:3]:
            stack = frames.get(getattr(worker, "ident", None) or -1)
            if stack is None:
                parts.append(f"{worker.name} (no stack)")
                continue
            calls = _traceback.extract_stack(stack)[-8:]
            location = " <- ".join(f"{f.filename.split('/')[-1]}:{f.name}:{f.lineno}" for f in calls)
            parts.append(f"{worker.name} at {location}")
        extra = f" (+{len(alive) - 3} more)" if len(alive) > 3 else ""
        return "; ".join(parts) + extra
    except Exception:
        return "unavailable"


def _initiator_is_sole_worker(controller, pool: object) -> bool:
    """True when quit runs ON this pool's only live worker.

    The initiator can never finish (it is executing the shutdown) so a
    blocking ``shutdown(wait=True)`` join could only burn its timeout.
    Pending futures were already cancelled; with no other live worker
    there is no in-flight work left to drain for.
    """
    try:
        initiator = getattr(controller, "_quit_initiator", None)
        if initiator is None or not initiator.is_alive():
            return False
        alive = _live_pool_workers(pool)
        return len(alive) == 1 and alive[0] is initiator
    except Exception:
        return False


def _initiator_on_workers(prefix: str, controller) -> bool:
    """True when the quit initiator is a worker of the named pool."""
    try:
        initiator = getattr(controller, "_quit_initiator", None)
        return initiator is not None and initiator.name.startswith(prefix)
    except Exception:
        return False


def _wait_for_pool_drain(pool: object, initiator: object, timeout: float) -> None:
    """Wait until no pool worker besides the initiator is alive (bounded).

    A blocking ``pool.shutdown(wait=True)`` join can never finish while
    the initiator itself is a pool worker (quit arrived as a dispatched
    command): the join waits for the very thread running the cleanup,
    burning the whole budget every quit. Idle workers exit on their own
    once the pool is shut down; genuinely busy ones still get the full
    budget here, so in-flight work keeps its protection.
    """
    deadline = time.monotonic() + timeout
    while True:
        others = [t for t in _live_pool_workers(pool) if t is not initiator]
        if not others:
            return
        if time.monotonic() >= deadline:
            return
        time.sleep(0.05)


def drain_ws_dispatch_pool(controller, app) -> None:
    """Early bookend: stop the IPC server + drain the WS dispatch + encode pools."""
    # Single-summary noise contract: the per-pool shutdown debugs used to
    # emit one line each on every quit; they now append here and flush as
    # one line at the end of the drain.
    _closed: list[str] = []
    _closed_lock = threading.Lock()

    def _mark_closed(name: str) -> None:
        with _closed_lock:
            _closed.append(name)

    try:
        ipc_server = getattr(app, "_ipc_server", None)
        ws_pool = getattr(ipc_server, "_ws_dispatch_pool", None) if ipc_server is not None else None

        early_items: list[tuple[str, Callable[[], object], float]] = []
        if ipc_server is not None:
            # PERF-SHUTDOWN-002: the stop hook alone can take up to ~3s
            # (graceful-close bound), so the outer budget must exceed
            # it or every slow close warns falsely. Typical stop is ms.
            early_items.append(("ipc_server.stop", ipc_server.stop, 4.0))

        if ws_pool is not None and hasattr(ws_pool, "shutdown"):

            def _drain_ws_pool() -> None:
                start = time.monotonic()
                # ``shutdown(wait=False, cancel_futures=True)`` only
                ws_pool.shutdown(wait=False, cancel_futures=True)
                _mark_closed("dispatch")
                if _initiator_is_sole_worker(controller, ws_pool):
                    log.debug(
                        "[SHUTDOWN] WS dispatch drain skipping blocking join "
                        "(quit runs on its sole live worker; the join could only time out)"
                    )
                    return
                if _on_own_pool_worker("sidecar-ws-dispatch"):
                    log.debug(
                        "[SHUTDOWN] WS dispatch drain skipping blocking join "
                        "(shutdown runs on a pool worker; the join could only time out)"
                    )
                    return
                initiator = getattr(controller, "_quit_initiator", None)
                join_timeout = min(_WS_DISPATCH_JOIN_S, _join_budget(start, _WS_DISPATCH_BUDGET_S))
                if isinstance(initiator, threading.Thread) and _initiator_on_workers("sidecar-ws-dispatch", controller):
                    # Quit runs on a pool worker (dispatched shutdown
                    # command): a stock shutdown(wait=True) join would wait
                    # for the initiator itself and burn the whole budget
                    # every quit. Wait for the OTHER workers only.

                    def _wait_for_others() -> None:
                        _wait_for_pool_drain(ws_pool, initiator, join_timeout)

                    join_thread = threading.Thread(
                        target=_wait_for_others,
                        daemon=True,
                    )
                else:
                    join_thread = threading.Thread(
                        target=ws_pool.shutdown,
                        kwargs={"wait": True},
                        daemon=True,
                    )
                join_thread.start()
                # Deliberately UNDER this item's envelope (see
                # ``_join_budget``): the join must lose the race so the
                # warning below is the one that lands.
                join_thread.join(timeout=join_timeout)
                if join_thread.is_alive():
                    log.warning(
                        "[SHUTDOWN] ws_dispatch_pool did not drain within "
                        "its %.1fs join (%.1fs budget), proceeding anyway; "
                        "stuck: %s",
                        join_timeout,
                        _WS_DISPATCH_BUDGET_S,
                        _stuck_worker_summary(ws_pool),
                    )

            early_items.append(("ws_dispatch_pool.drain", _drain_ws_pool, _WS_DISPATCH_BUDGET_S))

        readonly_pool = getattr(ipc_server, "_ws_readonly_pool", None) if ipc_server is not None else None
        if readonly_pool is not None and hasattr(readonly_pool, "shutdown"):

            def _drain_readonly_pool() -> None:
                start = time.monotonic()
                # Same drain discipline as the main dispatch pool: readonly
                # workers are short-lived status reads, so a tight budget.
                readonly_pool.shutdown(wait=False, cancel_futures=True)
                _mark_closed("readonly")
                if _initiator_is_sole_worker(controller, readonly_pool):
                    log.debug(
                        "[SHUTDOWN] WS readonly drain skipping blocking join "
                        "(quit runs on its sole live worker; the join could only time out)"
                    )
                    return
                if _on_own_pool_worker("sidecar-ws-readonly"):
                    log.debug(
                        "[SHUTDOWN] WS readonly drain skipping blocking join "
                        "(shutdown runs on a pool worker; the join could only time out)"
                    )
                    return
                join_timeout = min(_WS_READONLY_JOIN_S, _join_budget(start, _WS_READONLY_BUDGET_S))
                join_thread = threading.Thread(
                    target=readonly_pool.shutdown,
                    kwargs={"wait": True},
                    daemon=True,
                )
                join_thread.start()
                # The join must exceed the longest expected handler stall
                # (a 2s WS send to a dead peer) and stay well inside the
                # envelope (see ``_join_budget``).
                join_thread.join(timeout=join_timeout)
                if join_thread.is_alive():
                    log.warning(
                        "[SHUTDOWN] ws_readonly_pool did not drain within its %.1fs join "
                        "(%.1fs budget), proceeding anyway; stuck: %s",
                        join_timeout,
                        _WS_READONLY_BUDGET_S,
                        _stuck_worker_summary(readonly_pool),
                    )

            early_items.append(("ws_readonly_pool.drain", _drain_readonly_pool, _WS_READONLY_BUDGET_S))

        encode_pool = getattr(ipc_server, "_ws_encode_pool", None)
        if encode_pool is not None and hasattr(encode_pool, "shutdown"):

            def _drain_encode_pool() -> None:
                start = time.monotonic()
                # The WS frame-encode pool must be drained for the same
                shutdown_encode_pool(ipc_server)
                _mark_closed("encode")
                if _initiator_is_sole_worker(controller, encode_pool):
                    log.debug(
                        "[SHUTDOWN] WS encode drain skipping blocking join "
                        "(quit runs on its sole live worker; the join could only time out)"
                    )
                    return
                if _on_own_pool_worker("sidecar-ws-encode"):
                    log.debug(
                        "[SHUTDOWN] WS encode drain skipping blocking join "
                        "(shutdown runs on a pool worker; the join could only time out)"
                    )
                    return
                join_timeout = min(_WS_ENCODE_JOIN_S, _join_budget(start, _WS_ENCODE_BUDGET_S))
                join_thread = threading.Thread(
                    target=encode_pool.shutdown,
                    kwargs={"wait": True},
                    daemon=True,
                )
                join_thread.start()
                # Encode work is pure CPU: a tight join, well inside the
                # envelope (see ``_join_budget``).
                join_thread.join(timeout=join_timeout)
                if join_thread.is_alive():
                    log.warning(
                        "[SHUTDOWN] ws_encode_pool did not drain within its %.1fs join "
                        "(%.1fs budget), proceeding anyway; stuck: %s",
                        join_timeout,
                        _WS_ENCODE_BUDGET_S,
                        _stuck_worker_summary(encode_pool),
                    )

            # Early + bounded: encodes are pure CPU
            early_items.append(("ws_encode_pool.drain", _drain_encode_pool, _WS_ENCODE_BUDGET_S))

        # Stop the worker-hop reconnect loop before draining: once the
        # worker is gone the client's backoff retries only spam WARNs
        # until process exit. Best-effort and creation-free (returns
        # False when no client was ever created in this process).
        try:
            from voice_typer.server import worker_client as _worker_client_mod

            if _worker_client_mod.close_shared_client():
                _mark_closed("worker client (reconnect loop stopped)")
        except Exception:
            log.debug("[SHUTDOWN] worker client close failed", exc_info=True)

        if early_items:
            _run_parallel_with_timeout(early_items)

        with _closed_lock:
            shut = sorted(set(_closed))
        if shut:
            log.debug("[SHUTDOWN] WS shutdown complete (cancel_futures=True): %s", ", ".join(shut))

        # explicit ``threading.Event`` coordination between the WS
        if ipc_server is not None:
            ws_drained_event = getattr(ipc_server, "_ws_drained_event", None)
            if ws_drained_event is not None:
                # Skip the 2s wait when the WS pool is already idle
                ws_inflight = getattr(ipc_server, "_ws_inflight_count", 0)
                if ws_inflight == 0:
                    log.debug("[SHUTDOWN] ws_drained_event.wait skipped (no in-flight WS handlers)")
                elif ws_inflight <= 1 and _initiator_on_workers("sidecar-ws-dispatch", controller):
                    # The only possible in-flight handler is quit itself
                    # (running on a dispatch worker); the event cannot
                    # fire until quit returns, so waiting could only warn.
                    log.debug(
                        "[SHUTDOWN] ws_drained_event.wait skipped (sole in-flight handler is quit itself)"
                    )
                else:
                    drained = ws_drained_event.wait(timeout=2.0)
                    if not drained:
                        in_flight = getattr(ipc_server, "_ws_inflight_count", 0)
                        # drain-timeout branch, log at WARNING and
                        log.warning(
                            "[SHUTDOWN] WS dispatch drain Event did not "
                            "fire in 2s, %s in-flight handlers may race DB "
                            "teardown; proceeding with cleanup (the in-flight "
                            "write may silently fail)",
                            in_flight,
                        )
    except Exception:
        log.debug(
            "[SHUTDOWN] early bookend (ipc_server.stop + WS drain) failed",
            exc_info=True,
        )


__all__ = ["drain_ws_dispatch_pool"]
