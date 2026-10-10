"""Shared native backend pool for the hotkey dispatcher.

Split out of ``voice_typer.server.hotkey_dispatcher`` (one concern per
file). The facade keeps the class, the public names and every
monkeypatch seam; this module owns the moved bodies only.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

from voice_typer.server.branding import APP_NAME
from voice_typer.server.hotkeys import HotkeyBackend
from voice_typer.server.i18n import t as i18n_t
from voice_typer.server.tray_hotkey import format_hotkey_label

log = logging.getLogger("voice_typer.server.hotkey_dispatcher")


class HotkeyPoolMixin:
    """Shared native backend pool for ``HotkeyDispatcher``.

    Host-state contract: the declarations below are attributes
    the facade ``__init__`` (or a sibling mixin) owns.

    The TYPE_CHECKING stubs name sibling-mixin methods this
    class calls through the composed ``HotkeyDispatcher``.
    """

    _app: Any
    _esc_callback: Any
    _esc_spec: str | None
    _repaste_callback: Any
    _repaste_spec: str | None
    _resyncing_aux: bool
    _shared_backend: HotkeyBackend | None
    _shared_backend_pool: dict[str, HotkeyBackend]

    if TYPE_CHECKING:
        def register_esc(self) -> None: ...
        def register_repaste(self) -> None: ...


    def _native_of(self, backend: HotkeyBackend | None) -> Any:
        """Return the wrapped ``SubprocessHotkeyBackend`` if ``backend``
        is a ``_NativeBackendAdapter``, else ``None``.

        The adapter (``voice_typer.server.hotkeys.native_adapter``)
        stores the native backend on ``self._native``. We access it
        via ``getattr`` so this method works for ANY backend that
        follows the same adapter pattern (and silently returns
        ``None`` for legacy backends like ``PynputHotkey`` /
        ``WaylandHotkey`` / ``WindowsNativeHotkey`` that don't support
        extra matchers, those fall back to the per-role subprocess
        model).

        This deliberately accesses a private attribute (``_native``)
        on a class owned by another module; the alternative (adding a
        public getter to ``_NativeBackendAdapter``) is out of scope
        for this refactor's owned-file list.
        """
        if backend is None:
            return None
        # When the backend is a ``_NativeBackendAdapter`` that
        if getattr(backend, "_state", None) in ("FALLBACK", "FAILED"):
            return None
        native = getattr(backend, "_native", None)
        if native is None:
            return None
        # Duck-type: the native backend must support the pooling API.
        if not hasattr(native, "add_extra_matcher"):
            return None
        return native

    def _shared_native(self) -> Any:
        """Return the shared backend's native ``SubprocessHotkeyBackend``,
        or ``None`` if the shared backend is unset or doesn't support
        the pooling API (legacy backend in play)."""
        return self._native_of(self._shared_backend)

    def _pool_aux_into_shared(
        self,
        role: str,
        spec: str,
        callback: Any,
        aux_backend: HotkeyBackend | None,
    ) -> bool:
        """Register ``(role, spec, callback)`` as an extra matcher on
        the shared backend AND mark ``aux_backend`` as delegated (so
        its own ``start()`` skips spawning).

        Returns True if the role was pooled onto the shared backend;
        False if pooling is unavailable (no shared backend, or the
        shared backend's native doesn't support extra matchers) and
        the caller should fall back to the per-role subprocess model.

        Safe to call multiple times for the same role —
        :meth:`add_extra_matcher` is idempotent on ``role`` (replaces
        the parsed spec, preserves callbacks), and the
        ``set_role_*`` methods overwrite the previous value.
        """
        shared_native = self._shared_native()
        if shared_native is None:
            return False
        try:
            shared_native.add_extra_matcher(role, spec)
            shared_native.set_role_callback(role, callback)
            # Mark the aux backend as delegated so its start() skips
            aux_native = self._native_of(aux_backend)
            if aux_native is not None:
                aux_native._delegated = True
            # DEBUG: the caller's per-role "[HOTKEY] ... registered"
            log.debug(
                "[HOTKEY] Pooled %s into shared backend, separate %s backend is delegated (no subprocess)",
                format_hotkey_label(spec),
                role,
            )
            return True
        except Exception:
            # Partial install (e.g. add succeeded, set_role_callback
            with contextlib.suppress(Exception):
                shared_native.remove_extra_matcher(role)
            log.debug(
                "[HOTKEY] Failed to pool %s into shared backend, falling back to per-role subprocess",
                role,
                exc_info=True,
            )
            return False

    def _repool_aux_into_shared(self) -> None:
        """Re-register any existing ESC / repaste extra matchers
        against the CURRENT shared backend.

        Called from :meth:`_create_and_start_main_backend` after a new
        shared backend is installed (e.g. by :meth:`restart` swapping
        the dictation backend). Without this, a restart would leave
        the ESC / repaste extra matchers on the OLD (stopped) shared
        backend and the roles would silently stop firing.

        Idempotent, safe to call when no aux backends are registered
        (no-op) or when the shared backend doesn't support pooling
        (no-op).
        """
        shared_native = self._shared_native()
        if shared_native is None:
            return
        if self._esc_spec is not None and self._esc_callback is not None:
            try:
                shared_native.add_extra_matcher("esc", self._esc_spec)
                shared_native.set_role_callback("esc", self._esc_callback)
            except Exception:
                log.debug("[HOTKEY] Failed to re-pool ESC after shared-backend swap", exc_info=True)
        if self._repaste_spec is not None and self._repaste_callback is not None:
            try:
                shared_native.add_extra_matcher("repaste", self._repaste_spec)
                shared_native.set_role_callback("repaste", self._repaste_callback)
            except Exception:
                log.debug("[HOTKEY] Failed to re-pool repaste after shared-backend swap", exc_info=True)

    def _remove_shared_extra_matcher(self, role: str) -> None:
        """Remove the pooled extra matcher ``role`` from the shared
        backend without stopping the shared subprocess.

        Called from every role-teardown path:
        - :meth:`unregister_esc` (settings disable)
        - the ESC / repaste disable branches in :meth:`register`
        - the empty-config and validation-reject branches of
          :meth:`register_repaste`
        - the pool-then-start failure paths in :meth:`register_esc` /
          :meth:`register_repaste`

        The shared backend stays alive, only the role's matcher is
        dropped. Without this, the role keeps firing its callback
        (e.g. ESC keeps cancelling dictation after
        ``esc_cancel_enabled`` is turned off via settings).

        No-op when the role was never pooled (legacy per-role
        subprocess model, or no shared backend) —
        ``SubprocessHotkeyBackend.remove_extra_matcher`` is safe to
        call for an unknown role.
        """

        shared_native = self._shared_native()
        if shared_native is None:
            return
        with contextlib.suppress(Exception):
            shared_native.remove_extra_matcher(role)

    def _handle_shared_native_state_changed(self, state: str) -> None:
        """Re-sync the aux (ESC / repaste) backends when the
         shared backend's ``_NativeBackendAdapter`` swaps native ↔ legacy.

         When the adapter's native subprocess permanently fails and it
         swaps to a legacy backend (``FALLBACK`` state), the pooled
         ``"esc"`` / ``"repaste"`` extra matchers live on the DEAD native
        , the legacy backend that actually receives events knows nothing
         about those roles, so the delegated aux backends silently stop
         firing. Re-registering the active aux roles re-runs the pooling
         decision: with ``_shared_native()`` now reporting ``None`` for a
         FALLBACK adapter (see :meth:`_native_of`), each role falls back
         to its own per-role subprocess and keeps working. On recovery
         back to ``NATIVE``, the same re-registration re-pools the roles
         onto the recovered native, avoiding a double-fire (per-role
         subprocess + extra matcher both matching).

         Guarded by ``_resyncing_aux`` so a recursive swap (the role's
         own native also failing, re-firing this hook from inside
         ``register_esc``) cannot loop forever.
        """
        if self._resyncing_aux:
            return
        self._resyncing_aux = True
        try:
            if self._esc_spec is not None and self._esc_callback is not None:
                self.register_esc()
            if self._repaste_spec is not None and self._repaste_callback is not None:
                self.register_repaste()
        except Exception:
            log.debug(
                "[HOTKEY] Aux role re-sync after shared-backend state=%r failed",
                state,
                exc_info=True,
            )
        finally:
            self._resyncing_aux = False

    def _maybe_warn_wayland_caps_lock(self, hotkey_str: str) -> None:
        """surface a tray notification if the user bound Caps Lock
        on Wayland. See ``factory.py`` for the matching log.warning.

        The factory detects the condition at register time and logs it;
        this method mirrors the warning via the tray's safety channel so
        the user actually sees it. Idempotent, calling it multiple times
        for the same hotkey re-surfaces the same notification, which is
        acceptable (the user may have dismissed the first one).
        """
        try:
            from voice_typer.server.platform_utils import is_wayland_session

            if not is_wayland_session():
                return
            if not hotkey_str or "caps_lock" not in hotkey_str.lower():
                return
            with contextlib.suppress(Exception):
                self._app.tray.notify_safety(
                    APP_NAME,
                    i18n_t("notify.hotkey_dispatcher.wayland_caps_lock"),
                )
        except Exception:
            log.debug("[HOTKEY] _maybe_warn_wayland_caps_lock failed", exc_info=True)

    def _track_pooled_backend(self, spec: str, backend: HotkeyBackend) -> None:
        """Record ``backend`` in ``_shared_backend_pool`` under ``spec``.

        Called AFTER a backend's ``start()`` succeeds so the pool only
        ever contains live backends. If an entry already exists for
        ``spec`` (e.g. a stale entry from a backend that's about to be
        stopped), it is overwritten, the caller has just installed a
        fresh backend for that spec.
        """
        self._shared_backend_pool[spec] = backend

    def _untrack_pooled_backend(self, backend: HotkeyBackend | None) -> None:
        """Remove ``backend`` from ``_shared_backend_pool`` by identity.

        Called when a backend is stopped (via :meth:`stop_all`,
        :meth:`restart`, :meth:`unregister_esc`, or the teardown paths
        in :meth:`register_esc` / :meth:`register_repaste` /
        :meth:`register`) so the pool never returns a dead backend.
        Identity comparison (``is``) is used instead of spec lookup
        because the same spec may have been re-registered under a new
        backend instance, we only want to drop the OLD instance.
        """
        if backend is None:
            return
        for spec, pooled in list(self._shared_backend_pool.items()):
            if pooled is backend:
                del self._shared_backend_pool[spec]
                log.debug(
                    "[HOTKEY] Untracked pooled backend for spec %r (remaining pool size=%d)",
                    spec,
                    len(self._shared_backend_pool),
                )

    def get_active_backend_count(self) -> int:
        """Return the number of DISTINCT native backends currently
        tracked in ``_shared_backend_pool``.

        This is the count of live hotkey subprocesses owned by this
        dispatcher. On the full-pooling path (native
        ``SubprocessHotkeyBackend`` selected) with three DIFFERENT
        specs, this is 1, the dictation backend's subprocess hosts
        the ESC and repaste extra matchers, and the ESC / repaste
        backends are delegated (no subprocess of their own). When
        pooling is unavailable (legacy backend) or specs collide, the
        count reflects the actual subprocess count.
        """
        # Purge any dead entries before reporting so the count reflects
        for spec, pooled in list(self._shared_backend_pool.items()):
            if not pooled.is_alive():
                del self._shared_backend_pool[spec]
        return len(self._shared_backend_pool)
