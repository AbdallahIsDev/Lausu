"""Global hotkey registration and role teardown.

Split out of ``voice_typer.server.hotkey_dispatcher`` (one concern per
file). The facade keeps the class, the public names and every
monkeypatch seam; this module owns the moved bodies only.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import TYPE_CHECKING, Any

from voice_typer.server.branding import APP_NAME
from voice_typer.server.config import DEFAULT_HOTKEY
from voice_typer.server.hotkeys import HotkeyBackend
from voice_typer.server.i18n import t as i18n_t
from voice_typer.server.keyboard_ownership import keyboard_ownership
from voice_typer.server.tray_hotkey import format_hotkey_label

log = logging.getLogger("voice_typer.server.hotkey_dispatcher")


def _facade():
    """The facade module, read at call time so patches on it are honored."""
    from voice_typer.server import hotkey_dispatcher as module

    return module

_BACKEND_KIND_LABELS = {
    "_NativeBackendAdapter": "native",
    "WindowsNativeHotkey": "native-poll",
    "PynputHotkey": "pynput",
    "WaylandHotkey": "wayland",
}

def _backend_kind_label(backend) -> str:
    name = type(backend).__name__
    return _BACKEND_KIND_LABELS.get(name, name.lstrip("_"))


class HotkeyRegistrationMixin:
    """Global hotkey registration and role teardown.

    Host-state contract: the declarations below are attributes
    the facade ``__init__`` (or a sibling mixin) owns.

    The TYPE_CHECKING stubs name sibling-mixin methods this
    class calls through the composed ``HotkeyDispatcher``.
    """

    _app: Any
    _esc_backend: HotkeyBackend | None
    _esc_callback: Any
    _esc_pending_capture_exit_event: threading.Event
    _esc_spec: str | None
    _hotkey_backend: HotkeyBackend | None
    _repaste_backend: HotkeyBackend | None
    _repaste_callback: Any
    _repaste_spec: str | None
    _shared_backend: HotkeyBackend | None
    _shared_backend_pool: dict[str, HotkeyBackend]

    if TYPE_CHECKING:
        def _handle_shared_native_state_changed(self, state: str) -> None: ...
        def _make_dictation_callback(self): ...
        def _make_repaste_callback(self): ...
        def _maybe_warn_wayland_caps_lock(self, hotkey_str: str) -> None: ...
        def _on_esc_release(self) -> None: ...
        def _pool_aux_into_shared(
            self, role: str, spec: str, callback: Any, aux_backend: HotkeyBackend | None
        ) -> bool: ...
        def _remove_shared_extra_matcher(self, role: str) -> None: ...
        def _repool_aux_into_shared(self) -> None: ...
        def _shared_native(self) -> Any: ...
        def _start_ptt_safety_timer(self) -> None: ...
        def _track_pooled_backend(self, spec: str, backend: HotkeyBackend) -> None: ...
        def _untrack_pooled_backend(self, backend: HotkeyBackend | None) -> None: ...


    def register(self, skip_aux: bool = False) -> bool:
        """Register global hotkey using the platform-appropriate backend.

        when registration fails (typically because another app
        has already claimed the same hotkey via Win32 ``RegisterHotKey``
        or X11 grab), surface a tray notification that names the hotkey
        so the user can pick a different one in Settings.

        USER-REQUESTED FIX: in toggle mode, the dictation toggle fires on
        key-UP (release), not key-down, so a press-and-hold cannot start
        then immediately stop recording. This is wired via
        ``set_toggle_on_keyup(True)`` for the main dictation hotkey in
        toggle mode; push-to-talk keeps start-on-press / stop-on-release.

         (atomic register): ``self._hotkey_backend`` is assigned the
        NEW backend only AFTER ``start()`` succeeds. If ``create_hotkey_backend``
        or ``start()`` raises, the OLD backend (if any) is left in place
        so the user is never left without a working hotkey. This is the
        building block ``restart()`` relies on for its atomicity.

        Returns:
            True if a new backend was successfully created, wired, and
            started (and assigned to ``self._hotkey_backend``); False if
            any step failed (the OLD backend, if any, is left running).
            Callers that ignore the return value (the historical
            contract) continue to work unchanged.
        """
        app = self._app
        hotkey_str = app.config.hotkey

        #  (partial, session-4): validate the configured hotkey
        from voice_typer.server.config_validators import _validate_hotkey

        validation_error = _validate_hotkey(hotkey_str)
        if validation_error is not None:
            log.warning(
                "[HOTKEY] configured hotkey %r rejected (%s), falling back to default <caps_lock>",
                hotkey_str,
                validation_error,
            )
            hotkey_str = DEFAULT_HOTKEY  # platform default (see config._default_hotkey_for_platform)
            app.config.hotkey = hotkey_str

        log.info("[HOTKEY] Registering: %s -> toggle_dictation", format_hotkey_label(hotkey_str))

        success = False
        try:
            new_backend = self._create_and_start_main_backend(hotkey_str)
            # assign only after start() succeeded. A failure
            self._hotkey_backend = new_backend
            success = True
        except Exception as exc:
            # name the hotkey in the notification so the user
            log.warning("[HOTKEY] Registration FAILED -- %s: %s", hotkey_str, exc)
            log.debug("Hotkey registration error", exc_info=True)
            app.tray.notify(
                APP_NAME,
                i18n_t("notify.hotkey_dispatcher.register_failed", hotkey=hotkey_str),
            )

        # Feature: ESC to cancel -- register ESC hotkey when enabled
        if not skip_aux:
            if app.config.esc_cancel_enabled:
                esc_already_alive = (
                    self._esc_backend is not None
                    and self._esc_backend.is_alive()
                    and self._esc_spec == "<esc>"
                )
                if not esc_already_alive:
                    self.register_esc()
            elif self._esc_backend is not None:
                # Untrack from the per-spec pool BEFORE stopping so the
                self._untrack_pooled_backend(self._esc_backend)
                with contextlib.suppress(Exception):
                    self._esc_backend.stop()
                self._esc_backend = None
                self._esc_spec = None
                # Remove the pooled extra matcher from the shared backend
                self._remove_shared_extra_matcher("esc")
                self._esc_callback = None

            # Feature: Repaste hotkey
            if app.config.repaste_hotkey:
                repaste_already_alive = (
                    self._repaste_backend is not None
                    and self._repaste_backend.is_alive()
                    and self._repaste_spec == app.config.repaste_hotkey
                )
                if not repaste_already_alive:
                    self.register_repaste()
            elif self._repaste_backend is not None:
                # Untrack from the per-spec pool BEFORE stopping (see
                self._untrack_pooled_backend(self._repaste_backend)
                with contextlib.suppress(Exception):
                    self._repaste_backend.stop()
                self._repaste_backend = None
                self._repaste_spec = None
                # Remove the pooled extra matcher from the shared backend
                self._remove_shared_extra_matcher("repaste")
                self._repaste_callback = None

        return success

    def _create_and_start_main_backend(self, hotkey_str: str) -> HotkeyBackend:
        """Create, wire up, and start the main dictation hotkey backend.

        Shared by :meth:`register` (first-time setup) and :meth:`restart`
        (hot-swap). Returns the new backend on success; raises on failure
        so the caller can decide whether to install it as the active
        backend (atomic swap pattern).

        - ``create_hotkey_backend`` (factory) selects the best platform
          backend; can raise on spec parse errors or missing native
          binary paths.
        - ``start(callback)`` launches the listener thread; can raise if
          the OS rejects the hotkey (e.g. Win32 ``RegisterHotKey`` fails
          because another app already claimed it).

        Wiring applied to the new backend before ``start()``:
        - ``_tray`` attribute (/): so the backend can show
          permission / fallback / recovery notifications.
        - ``set_toggle_on_keyup(True)`` in toggle mode: so the toggle
          fires on key-UP and a press-and-hold cannot start-then-stop
          recording.
        - ``set_on_release(app._stop_dictation)`` in push-to-talk mode.

        Per-spec pool: if a backend with the same ``hotkey_str`` is
        already tracked in ``_shared_backend_pool`` and is still alive,
        it is returned as-is (no factory call, no second ``start()``).
        This collapses the rare case where two roles share the same spec
        (e.g. dictation and repaste both bound to ``<f2>``) into a
        single native subprocess. The backend is added to the pool
        AFTER ``start()`` succeeds so a failed start does not leave a
        stale entry.
        """
        app = self._app
        # Per-spec pool fast path: if a backend for this exact spec is
        pooled = self._shared_backend_pool.get(hotkey_str)
        if pooled is not None:
            if pooled.is_alive():
                log.info(
                    "[HOTKEY] Reusing pooled backend for %s (active pool size=%d), no new subprocess spawned",
                    format_hotkey_label(hotkey_str),
                    len(self._shared_backend_pool),
                )
                # Re-install as the shared backend so any subsequent
                self._shared_backend = pooled
                self._repool_aux_into_shared()
                return pooled
            # Stale entry, drop it so the factory path below can
            self._shared_backend_pool.pop(hotkey_str, None)
        # pass role="dictation" so the WaylandHotkey backend (if
        new_backend: HotkeyBackend = _facade().create_hotkey_backend(hotkey_str, role="dictation")
        log.debug("[HOTKEY] Backend created: %s", _backend_kind_label(new_backend))
        # give the backend a reference to the tray so
        with contextlib.suppress(AttributeError, TypeError):
            new_backend._tray = app.tray
        # wire the ``_NativeBackendAdapter``'s native↔legacy
        with contextlib.suppress(AttributeError, TypeError):
            new_backend._on_state_change_callback = self._handle_shared_native_state_changed
        # surface a tray notification when the user binds Caps
        self._maybe_warn_wayland_caps_lock(hotkey_str)
        # PTT safety timeout, if a recording started via
        if app.config.recording_mode == "push_to_talk":
            self._start_ptt_safety_timer()
        # USER-REQUESTED FIX: in toggle mode, fire the toggle on key-up
        if app.config.recording_mode == "toggle":
            with contextlib.suppress(AttributeError, TypeError):
                new_backend.set_toggle_on_keyup(True)
        new_backend.start(self._make_dictation_callback())
        # P1: Push-to-talk mode -- set release callback
        if app.config.recording_mode == "push_to_talk":
            new_backend.set_on_release(app._stop_dictation)
        log.info(
            "[HOTKEY] Registration OK: %s (backend=%s, alive=%s)",
            format_hotkey_label(hotkey_str),
            _backend_kind_label(new_backend),
            new_backend.is_alive(),
        )
        # Track in the per-spec pool AFTER start() succeeded so a
        self._track_pooled_backend(hotkey_str, new_backend)
        # Install as the shared backend and re-pool any aux backends
        self._shared_backend = new_backend
        self._repool_aux_into_shared()
        return new_backend

    def register_esc(self) -> None:
        """Register the ESC hotkey for cancelling dictation.

        the ESC callback is wrapped to consult the
        KeyboardOwnership singleton. If the frontend is in hotkey
        capture mode (``is_hotkey_capture_active()`` returns True),
        the ESC callback defers to key-up instead of acting
        immediately on key-down. This matches how regular hotkey
        capture works (assignment happens on key-up / release).

        When the user presses ESC during hotkey
        capture, the key-down sets a pending flag and installs a
        release callback on the ESC backend. The actual ownership
        reset and ``hotkey_capture_cancel`` event are pushed on
        key-up, when the user releases the finger. This eliminates
        the "cancel on press" behavior the user reported as
        feeling unresponsive.

        Per-spec pool: the ESC backend is tracked in
        ``_shared_backend_pool`` under ``"<esc>"`` after ``start()``
        succeeds, and untracked when stopped. The fast-path reuse
        (returning the existing backend instead of calling the
        factory) is NOT implemented for ESC because the ESC callback
        differs from the dictation callback, reusing a dictation
        backend (rare case where the user bound dictation to ESC)
        would cause both callbacks to fire on the same keypress.
        The full refactor (see module docstring TODO) solves this
        via role-tagged wire events.
        """
        # Stop any existing backend first
        if self._esc_backend:
            self._untrack_pooled_backend(self._esc_backend)
            with contextlib.suppress(Exception):
                self._esc_backend.stop()
            self._esc_backend = None
            self._esc_spec = None

        # Clear any stale pending-capture-exit signal before arming the
        # ESC release callback.
        self._esc_pending_capture_exit_event.clear()

        try:
            # pass role="esc" so the WaylandHotkey backend (if
            self._esc_backend = _facade().create_hotkey_backend("<esc>", role="esc")
            # prefer the event-driven WM_HOTKEY message loop over
            with contextlib.suppress(AttributeError, TypeError):
                self._esc_backend._prefer_message_loop_first = True

            def _esc_callback() -> None:
                # shutdown guard (see _dictation_callback).
                if getattr(self._app, "_shutting_down", False):
                    log.debug("[HOTKEY] ESC ignored, app shutting down")
                    return
                # centralized ownership check.
                if keyboard_ownership().is_hotkey_capture_active():
                    log.info("[HOTKEY] ESC pressed during hotkey capture, waiting for key-up")
                    # Set the pending flag and install
                    self._esc_pending_capture_exit_event.set()
                    # Route the release callback through the shared
                    shared_native = self._shared_native()
                    if shared_native is not None:
                        with contextlib.suppress(Exception):
                            shared_native.set_role_on_release("esc", self._on_esc_release)
                    if self._esc_backend is not None:
                        self._esc_backend.set_on_release(self._on_esc_release)
                    return
                self._app._cancel_dictation()

            # Stash the callback so :meth:`_repool_aux_into_shared`
            self._esc_callback = _esc_callback
            # Pool ESC into the shared backend (one subprocess for all
            _esc_pooled = self._pool_aux_into_shared("esc", "<esc>", _esc_callback, self._esc_backend)
            try:
                self._esc_backend.start(_esc_callback)
            except Exception:
                # Pool-then-start failure: if the extra matcher was
                if _esc_pooled:
                    self._remove_shared_extra_matcher("esc")
                    self._esc_callback = None
                raise
            self._esc_spec = "<esc>"
            # Track in the per-spec pool AFTER start() succeeded so a
            self._track_pooled_backend("<esc>", self._esc_backend)
            log.info(
                "[HOTKEY] ESC cancel registered%s",
                " (pooled into shared backend)" if _esc_pooled else "",
            )
        except Exception:
            # null the failed backend reference so a subsequent
            if self._esc_backend is not None:
                self._untrack_pooled_backend(self._esc_backend)
                with contextlib.suppress(Exception):
                    self._esc_backend.stop()
            self._esc_backend = None
            self._esc_spec = None
            log.warning("[HOTKEY] ESC cancel hotkey registration failed")
            # surface the failure to the user via the tray's
            with contextlib.suppress(Exception):
                self._app.tray.notify_safety(
                    APP_NAME,
                    i18n_t("notify.hotkey_dispatcher.esc_register_failed"),
                )

    def unregister_esc(self) -> None:
        """Unregister the ESC hotkey."""
        if self._esc_backend:
            self._untrack_pooled_backend(self._esc_backend)
            with contextlib.suppress(Exception):
                self._esc_backend.stop()
            self._esc_backend = None
            self._esc_spec = None
            # Also remove the pooled "esc" extra matcher from the shared
            self._remove_shared_extra_matcher("esc")
            # Clear the stashed callback so a later shared-backend swap
            self._esc_callback = None
            log.info("[HOTKEY] ESC cancel hotkey unregistered")

    def register_repaste(self) -> None:
        """Register the repaste hotkey.

        Teardown contract: stopping a previous repaste backend never
        stops the shared dictation backend. When the new
        ``repaste_hotkey`` is empty (config cleared / rejected), the
        pooled extra matcher is removed from the shared backend so the
        old combo stops firing. Replacing a live repaste with a new
        spec re-uses the role-keyed ``add_extra_matcher`` path (no
        remove needed).
        """
        if self._repaste_backend:
            self._untrack_pooled_backend(self._repaste_backend)
            with contextlib.suppress(Exception):
                self._repaste_backend.stop()
            self._repaste_backend = None
            self._repaste_spec = None
        if not self._app.config.repaste_hotkey:
            # Empty config (cleared in Settings, or set_config wrote
            self._remove_shared_extra_matcher("repaste")
            self._repaste_callback = None
            return
        # validate the configured repaste hotkey BEFORE
        from voice_typer.server.config_validators import _validate_hotkey

        validation_error = _validate_hotkey(self._app.config.repaste_hotkey)
        if validation_error is not None:
            log.warning(
                "[HOTKEY] configured repaste_hotkey %r rejected (%s), "
                "disabling repaste (not resetting to <caps_lock> to avoid "
                "conflict with the main dictation hotkey)",
                self._app.config.repaste_hotkey,
                validation_error,
            )
            self._app.config.repaste_hotkey = ""
            # Same teardown as the empty-config branch: the previous
            self._remove_shared_extra_matcher("repaste")
            self._repaste_callback = None
            return
        try:
            # pass role="repaste" so the WaylandHotkey backend
            self._repaste_backend = _facade().create_hotkey_backend(
                self._app.config.repaste_hotkey, role="repaste"
            )
            # same WM_HOTKEY-preference flag as the ESC backend
            with contextlib.suppress(AttributeError, TypeError):
                self._repaste_backend._prefer_message_loop_first = True
            _repaste_cb = self._make_repaste_callback()
            # Stash the callback so :meth:`_repool_aux_into_shared`
            self._repaste_callback = _repaste_cb
            # Pool repaste into the shared backend (one subprocess
            _repaste_pooled = self._pool_aux_into_shared(
                "repaste",
                self._app.config.repaste_hotkey,
                _repaste_cb,
                self._repaste_backend,
            )
            try:
                self._repaste_backend.start(_repaste_cb)
            except Exception:
                # Pool-then-start failure: remove the matcher already
                if _repaste_pooled:
                    self._remove_shared_extra_matcher("repaste")
                    self._repaste_callback = None
                raise
            self._repaste_spec = self._app.config.repaste_hotkey
            # Track in the per-spec pool AFTER start() succeeded
            self._track_pooled_backend(self._app.config.repaste_hotkey, self._repaste_backend)
            log.info(
                "[HOTKEY] Repaste registered: %s%s",
                format_hotkey_label(self._app.config.repaste_hotkey),
                " (pooled into shared backend)" if _repaste_pooled else "",
            )
        except Exception:
            # null the failed backend reference so a
            if self._repaste_backend is not None:
                self._untrack_pooled_backend(self._repaste_backend)
                with contextlib.suppress(Exception):
                    self._repaste_backend.stop()
            self._repaste_backend = None
            self._repaste_spec = None
            log.warning("[HOTKEY] Repaste hotkey registration failed")
            # surface the failure to the user via the tray's
            with contextlib.suppress(Exception):
                self._app.tray.notify_safety(
                    APP_NAME,
                    i18n_t("notify.hotkey_dispatcher.repaste_register_failed"),
                )
