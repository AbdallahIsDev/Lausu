"""WS dispatch + encode pool drain (extracted from ``shutdown_controller``)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from voice_typer.server._timeout_utils import _run_parallel_with_timeout
from voice_typer.server.sidecar_ws_internals.encode_pool import shutdown_encode_pool

log = logging.getLogger("voice_typer.server.shutdown_controller")


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
                join_thread = threading.Thread(
                    target=ws_pool.shutdown,
                    kwargs={"wait": True},
                    daemon=True,
                )
                join_thread.start()
                # 4.5s, deliberately UNDER this item's 5.0s parallel
                join_thread.join(timeout=4.5)
                if join_thread.is_alive():
                    # Name BOTH bounds honestly (mirrors the encode-pool
                    log.warning(
                        "[SHUTDOWN] ws_dispatch_pool did not drain within "
                        "its 4.5s join (5.0s budget), proceeding anyway; "
                        "stuck: %s",
                        _stuck_worker_summary(ws_pool),
                    )

            early_items.append(("ws_dispatch_pool.drain", _drain_ws_pool, 5.0))

        readonly_pool = getattr(ipc_server, "_ws_readonly_pool", None) if ipc_server is not None else None
        if readonly_pool is not None and hasattr(readonly_pool, "shutdown"):

            def _drain_readonly_pool() -> None:
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
                join_thread = threading.Thread(
                    target=readonly_pool.shutdown,
                    kwargs={"wait": True},
                    daemon=True,
                )
                join_thread.start()
                # Inner must exceed the longest expected handler stall
                # (a 2s WS send to a dead peer); outer must exceed inner.
                join_thread.join(timeout=2.5)
                if join_thread.is_alive():
                    log.warning(
                        "[SHUTDOWN] ws_readonly_pool did not drain within its 2.5s join, "
                        "proceeding anyway; stuck: %s",
                        _stuck_worker_summary(readonly_pool),
                    )

            early_items.append(("ws_readonly_pool.drain", _drain_readonly_pool, 3.0))

        encode_pool = getattr(ipc_server, "_ws_encode_pool", None)
        if encode_pool is not None and hasattr(encode_pool, "shutdown"):

            def _drain_encode_pool() -> None:
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
                join_thread = threading.Thread(
                    target=encode_pool.shutdown,
                    kwargs={"wait": True},
                    daemon=True,
                )
                join_thread.start()
                # 1.8s inner join, deliberately UNDER this item's 2.0s
                join_thread.join(timeout=1.8)
                if join_thread.is_alive():
                    # Name BOTH bounds honestly: the inner join is 1.8s
                    log.warning(
                        "[SHUTDOWN] ws_encode_pool did not drain within its 1.8s join (2.0s budget), "
                        "proceeding anyway; stuck: %s",
                        _stuck_worker_summary(encode_pool),
                    )

            # Early + bounded (~2s): encodes are pure CPU
            early_items.append(("ws_encode_pool.drain", _drain_encode_pool, 2.0))

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
