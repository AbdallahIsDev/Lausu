"""Hotkey backend restart and shutdown for the hotkey dispatcher.

Split out of ``voice_typer.server.hotkey_dispatcher`` (one concern per
file). The facade keeps the class, the public names and every
monkeypatch seam; this module owns the moved bodies only.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from voice_typer.server.branding import APP_NAME
from voice_typer.server.hotkeys import HotkeyBackend
from voice_typer.server.i18n import t as i18n_t

log = logging.getLogger("voice_typer.server.hotkey_dispatcher")


class HotkeyLifecycleMixin:
    """Backend restart and shutdown.

    Host-state contract: the declarations below are attributes
    the facade ``__init__`` (or a sibling mixin) owns.

    The TYPE_CHECKING stubs name sibling-mixin methods this
    class calls through the composed ``HotkeyDispatcher``.
    """

    _app: Any
    _esc_callback: Any
    _esc_spec: str | None
    _hotkey_backend: HotkeyBackend | None
    _repaste_callback: Any
    _repaste_spec: str | None
    _shared_backend: HotkeyBackend | None
    _shared_backend_pool: dict[str, HotkeyBackend]

    if TYPE_CHECKING:
        def _cancel_ptt_safety_timer(self) -> None: ...
        def _create_and_start_main_backend(self, hotkey_str: str) -> HotkeyBackend: ...
        def _untrack_pooled_backend(self, backend: HotkeyBackend | None) -> None: ...


    def restart(self, hotkey: str) -> None:
        """Re-register the global hotkey after settings change.

        validate hotkey before mutating config.

        stop the OLD backend BEFORE starting the NEW one.
        Previously ``register()`` brought up the new backend first and
        the old backend was only stopped AFTER ``register()`` returned
        success, leaving a window where BOTH backends were running on
        platforms that permit multiple global-hotkey registrations
        (pynput on Linux/X11, Wayland). Both fired the dictation
        callback on the same keypress → double-toggle. Stopping the
        old backend first eliminates the window.

        Fallback restore on failure: if ``register()`` fails (e.g. the
        new hotkey spec is invalid or the OS rejects it because
        another app claimed it), the OLD backend's hotkey spec is
        restored to ``app.config.hotkey`` and a fresh backend is
        created with the OLD spec so the user is never left without a
        working dictation hotkey. This preserves the  user-facing
        contract ("restart failure keeps the previous hotkey working")
        while eliminating the double-backend window.

        on failure, ``register()`` already shows the tray
        notification naming the rejected hotkey; we don't duplicate
        it here. If fallback restore ALSO fails, the user is left
        without a hotkey and a separate ERROR-level log line is
        emitted so operators can diagnose.
        """
        app = self._app
        from voice_typer.server.config_validators import _validate_hotkey

        validation_error = _validate_hotkey(hotkey)
        if validation_error is not None:
            log.warning("[HOTKEY] restart(%r) rejected: %s", hotkey, validation_error)
            with contextlib.suppress(Exception):
                app.tray.notify(
                    APP_NAME,
                    i18n_t(
                        "notify.hotkey_dispatcher.invalid_hotkey",
                        hotkey=hotkey,
                        validation_error=validation_error,
                    ),
                )
            return
        # capture the OLD hotkey spec BEFORE mutating
        old_hotkey_str = app.config.hotkey
        old_backend = self._hotkey_backend

        app.config.hotkey = hotkey
        if not app.config.save():
            log.warning("[HOTKEY] config.save() returned False, hotkey change may not persist")
            app.tray.notify(
                APP_NAME,
                i18n_t("notify.hotkey_dispatcher.save_failed"),
            )

        # stop the OLD backend BEFORE calling register()
        if old_backend is not None:
            # Untrack from the per-spec pool BEFORE stopping so the
            self._untrack_pooled_backend(old_backend)
            try:
                old_backend.stop()
            except Exception:
                log.exception("[HOTKEY] Failed to stop previous backend before restart")
            self._hotkey_backend = None

        # ``register()`` ALSO calls ``register_esc()`` +
        try:
            new_backend = self._create_and_start_main_backend(hotkey)
            self._hotkey_backend = new_backend
            register_ok = True
        except Exception as exc:
            register_ok = False
            log.warning(
                "[HOTKEY] restart register failed for %r: %s",
                hotkey,
                exc,
            )
            # mirror ``register()``'s tray notification on failure so
            with contextlib.suppress(Exception):
                app.tray.notify(
                    APP_NAME,
                    i18n_t("notify.hotkey_dispatcher.register_failed", hotkey=hotkey),
                )

        if register_ok:
            # new backend installed, old backend already stopped above.
            pass
        else:
            # registration failed. The OLD backend was already stopped,
            if old_backend is not None:
                log.warning(
                    "[HOTKEY] restart failed; restoring previous hotkey %r",
                    old_hotkey_str,
                )
                app.config.hotkey = old_hotkey_str
                with contextlib.suppress(Exception):
                    app.config.save()
                try:
                    self._hotkey_backend = self._create_and_start_main_backend(old_hotkey_str)
                except Exception:
                    log.exception(
                        "[HOTKEY] Failed to restore previous backend (hotkey=%r), "
                        "user is left without a dictation hotkey",
                        old_hotkey_str,
                    )
                    with contextlib.suppress(Exception):
                        app.tray.notify(
                            APP_NAME,
                            i18n_t(
                                "notify.hotkey_dispatcher.restore_failed",
                                hotkey=old_hotkey_str,
                            ),
                        )
            else:
                # No OLD backend to restore, register() failure leaves
                log.warning("[HOTKEY] restart did not install a new backend, no previous backend to restore")

        app.tray.set_hotkey(app.config.hotkey)

    def stop_all(self) -> None:
        """Stop all hotkey backends (called during app shutdown).

        each backend's ``stop()`` runs in a worker thread under
        a hard 3s budget shared across all three backends. Previously
        ``stop_all`` called ``backend.stop()`` sequentially with no
        timeout, a single hung native backend (Win32
        ``UnregisterHotKey`` + listener-thread join, Wayland
        ``wl_display`` teardown, pynput listener join) could block the
        shutdown sequence for up to ~15s (3 backends × 5s join each).
        Backends that miss the 3s budget are leaked (their worker
        thread keeps running) and a warning is logged; every native
        listener thread is a daemon, so process exit still terminates
        it. ``stop()`` failures inside the budget are swallowed (logged
        at debug) so a poisoned backend doesn't abort the rest of
        shutdown, same contract as before.

        Implementation note: we do NOT use the ``with`` block on the
        ``ThreadPoolExecutor`` because ``__exit__`` calls
        ``shutdown(wait=True)`` which would block until every submitted
        future completes, defeating the 3s budget. Instead we call
        ``shutdown(wait=False, cancel_futures=True)`` so already-running
        workers are left to finish (or hang) in the background and the
        method returns as soon as ``concurrent.futures.wait`` does.
        """
        backend_attrs = ("_hotkey_backend", "_esc_backend", "_repaste_backend")
        live_attrs = [a for a in backend_attrs if getattr(self, a) is not None]
        if live_attrs:
            # NOT using ``with``: see docstring: ``__exit__`` would
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(live_attrs))
            try:
                futures = {pool.submit(self._stop_one_backend, a): a for a in live_attrs}
                done, not_done = concurrent.futures.wait(futures, timeout=3.0)
                for fut in not_done:
                    log.warning(
                        "[HOTKEY] %s did not stop within 3s budget, proceeding anyway",
                        futures[fut],
                    )
                # Surface any exception raised by a completed stop so
                for fut in done:
                    exc = fut.exception()
                    if exc is not None:
                        log.debug(
                            "[HOTKEY] %s stop() raised: %r",
                            futures[fut],
                            exc,
                            exc_info=True,
                        )
            finally:
                # drops any not-yet-started submissions (defensive —
                pool.shutdown(wait=False, cancel_futures=True)
        # clear the spec trackers so a post-shutdown register()
        self._esc_spec = None
        self._repaste_spec = None
        # Clear the stashed ESC / repaste callbacks and the shared
        self._esc_callback = None
        self._repaste_callback = None
        self._shared_backend = None
        # of the three role attributes, defensive).
        self._shared_backend_pool.clear()
        # cancel any armed PTT safety timer so a hot-restart
        self._cancel_ptt_safety_timer()

    def _stop_one_backend(self, backend_attr: str) -> None:
        """stop a single backend and clear its attribute.

        Runs inside a ``concurrent.futures.ThreadPoolExecutor`` worker
        so a hung ``stop()`` cannot block the 3s budget in
        :meth:`stop_all`. ``stop()`` failures are swallowed (logged at
        debug) so a poisoned backend doesn't abort the rest of shutdown.
        The attribute is cleared UNCONDITIONALLY after ``stop()`` returns
        or raises, the post-stop code paths (and the test suite) treat
        ``None`` as "no backend", so leaving a partially-stopped backend
        in place would be worse than a clean None.
        """
        backend = getattr(self, backend_attr)
        if backend is None:
            return
        # Untrack from the per-spec pool BEFORE stopping so the count
        self._untrack_pooled_backend(backend)
        try:
            backend.stop()
        except Exception:
            log.debug("[HOTKEY] Failed to stop %s", backend_attr, exc_info=True)
        setattr(self, backend_attr, None)
