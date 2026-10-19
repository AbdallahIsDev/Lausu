"""Clipboard snapshot restore registry + delayed/immediate restore impls."""

from __future__ import annotations

import atexit
import contextlib
import threading
from typing import Any

from voice_typer.server import clipboard as _cb
from voice_typer.server.clipboard.fingerprint import clipboard_holds, text_fingerprint

# When paste() schedules a daemon-thread restore, it also appends an
_pending_restores: list[tuple[Any, Any, str, float]] = []
_pending_restores_lock = threading.Lock()
_MAX_PENDING_RESTORES = 8


def _flush_pending_restores(reason: str) -> int:
    """Claim + restore every pending snapshot now (best-effort; returns how
    many were restored).

    Gate 3: only a clipboard PROVABLY holding something else is left alone
    (an unreadable clipboard cannot belong to a newer cycle). Shared by the
    atexit handler and the graceful-shutdown flush so the two paths cannot
    drift apart.
    """
    with _pending_restores_lock:
        items = list(_pending_restores)
        _pending_restores.clear()
    restored = 0
    for _cm, snapshot, pasted_text, delay in items:
        try:
            if clipboard_holds(text_fingerprint(pasted_text)) is not False:
                snapshot.restore()
                restored += 1
                _cb.log.info(
                    "[CLIPBOARD-AUDIT] %s: restored snapshot (delay was %.3fs)",
                    reason,
                    delay,
                )
            else:
                _cb.log.debug(
                    "[CLIPBOARD-AUDIT] %s: skip restore (clipboard changed, expected=%d chars)",
                    reason,
                    len(pasted_text),
                )
        except Exception:
            _cb.log.exception("[CLIPBOARD] %s restore failed", reason)
    return restored


def _force_restore_pending_at_exit() -> None:
    """atexit handler, force-restore any pending snapshots."""
    _flush_pending_restores("Atexit")


def restore_pending_before_shutdown() -> int:
    """Run the pending restores synchronously during a graceful quit.

    The delayed-restore daemon dies with the process and the quit paths
    end in ``os._exit`` (atexit skipped), so teardown itself must run the
    restore; the caller wraps this in a bounded timeout.
    """
    return _flush_pending_restores("Shutdown")


# Register the atexit handler once at module import. Idempotent guard
_ATEXIT_REGISTERED = False
if not _ATEXIT_REGISTERED:
    try:
        atexit.register(_force_restore_pending_at_exit)
        _ATEXIT_REGISTERED = True
    except RuntimeError:  # pragma: no cover, atexit.register only fails if interpreter is shutting down
        # ``RuntimeError`` is raised when atexit hooks fire during
        pass


def _delayed_restore_impl(
    manager: Any,
    snapshot: Any,
    pasted_text: str,
    delay: float,
    pending_entry: Any = None,
) -> None:
    """Restore a snapshot after a delay. Runs on a daemon thread."""
    try:
        _cb.time.sleep(delay)

        # claim the pending_entry under the lock BEFORE
        if pending_entry is not None:
            try:
                with _pending_restores_lock:
                    try:
                        _pending_restores.remove(pending_entry)
                    except ValueError:
                        # Entry was already claimed by atexit (or
                        _cb.log.debug(
                            "[CLIPBOARD-AUDIT] Pending entry already claimed by atexit, skipping daemon restore"
                        )
                        return  #  short-circuit
            except Exception:  # pragma: no cover, catastrophic lock failure
                _cb.log.exception("[CLIPBOARD] Failed to claim pending restore entry, proceeding with restore")
                # Continue with restore anyway (best-effort). The

        # Gate 3: restore the saved user clipboard only while it still
        # holds exactly our text; a newer cycle's content stays untouched.
        if clipboard_holds(text_fingerprint(pasted_text)) is True:
            snapshot.restore()
            _cb.log.info(
                "[CLIPBOARD-AUDIT] Restored snapshot after %.3fs delay",
                delay,
            )
        else:
            _cb.log.debug(
                "[CLIPBOARD-AUDIT] Restore skipped, clipboard changed or unreadable (expected=%d chars)",
                len(pasted_text),
            )
    except Exception:
        _cb.log.exception("[CLIPBOARD] Delayed restore failed")
    finally:
        # proceeding with restore. Without this defensive remove,
        try:
            manager._last_copied_text = ""
        except Exception:  # pragma: no cover, attribute access broken
            _cb.log.debug("[CLIPBOARD] Failed to clear _last_copied_text", exc_info=True)
        if pending_entry is not None:
            with _pending_restores_lock, contextlib.suppress(ValueError):
                _pending_restores.remove(pending_entry)


def _restore_now_impl(manager: Any, snapshot: Any) -> None:
    """Restore a snapshot immediately (no paste keystroke, no delay)."""
    if snapshot is None:
        return
    try:
        snapshot.restore()
        _cb.log.info("[CLIPBOARD-AUDIT] Restored snapshot immediately (no paste)")
    except Exception:
        _cb.log.exception("[CLIPBOARD] Immediate restore failed")
    finally:
        # Clear the cached
        try:
            manager._last_copied_text = ""
        except Exception:  # pragma: no cover, attribute access broken
            _cb.log.debug(
                "[CLIPBOARD] Failed to clear _last_copied_text in restore_now",
                exc_info=True,
            )


__all__ = [
    "_ATEXIT_REGISTERED",
    "_MAX_PENDING_RESTORES",
    "_delayed_restore_impl",
    "_flush_pending_restores",
    "_force_restore_pending_at_exit",
    "_pending_restores",
    "_pending_restores_lock",
    "_restore_now_impl",
    "restore_pending_before_shutdown",
]
