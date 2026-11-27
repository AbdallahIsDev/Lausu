"""Backend-event to app-action dispatch for the hotkey dispatcher.

Split out of ``voice_typer.server.hotkey_dispatcher`` (one concern per
file). The facade keeps the class, the public names and every
monkeypatch seam; this module owns the moved bodies only.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import TYPE_CHECKING, Any

from voice_typer.server.hotkeys import HotkeyBackend
from voice_typer.server.keyboard_ownership import keyboard_ownership

log = logging.getLogger("voice_typer.server.hotkey_dispatcher")


def no_active_engine(app: Any) -> bool:
    """True when no local model, cloud backend or browser plugin can transcribe."""
    from voice_typer.server import internal_plugin_hook

    cfg = getattr(app, "config", None)
    if cfg is None:
        return False
    if internal_plugin_hook.plugin_display_name(app):
        return False
    return not (getattr(cfg, "model_size", "") or getattr(cfg, "asr_backend", "") == "cloud")


def notify_no_active_engine(app: Any, caller: str = "HOTKEY") -> None:
    """One localized notice for every user-facing start entry."""
    from voice_typer.server import event_bus
    from voice_typer.server.branding import APP_NAME
    from voice_typer.server.i18n import t

    message = t("notify.model_manager.no_model_selected")
    log.info("[%s] no active engine; dictation not started", caller)
    try:
        event_bus.publish(
            {
                "type": "notification",
                "data": {
                    "title": APP_NAME,
                    "message": message,
                    "duration_ms": 0,
                    "critical": False,
                },
            }
        )
    except Exception:
        log.debug("[%s] in-app no-engine notification failed", caller, exc_info=True)
    try:
        app.tray.notify(message)
    except Exception:
        log.debug("[%s] no-engine notification failed", caller, exc_info=True)


class HotkeyDispatchMixin:
    """Backend-event to app-action dispatch.

    Host-state contract: the declarations below are attributes
    the facade ``__init__`` (or a sibling mixin) owns.

    The TYPE_CHECKING stubs name sibling-mixin methods this
    class calls through the composed ``HotkeyDispatcher``.
    """

    _app: Any
    _esc_backend: HotkeyBackend | None
    _esc_pending_capture_exit_event: threading.Event

    if TYPE_CHECKING:

        def _shared_native(self) -> Any: ...
        def _start_ptt_safety_timer(self) -> None: ...
        def _cancel_ptt_safety_timer(self) -> None: ...

    def _make_dictation_callback(self):
        """Create a dictation hotkey callback that respects keyboard ownership.

        HOTKEY- the dictation callback previously called
        ``app.toggle_dictation`` directly with NO ownership check. This meant
        that pressing any key during a hotkey capture session (e.g. re-assigning
        the current hotkey, or capturing a new key like Tab) would immediately
        trigger recording: because the OS-level listener sees the same keypress
        the frontend capture handler sees, and there was no guard.

        This mirrors the ESC callback's ownership check ( at line
        ~142): if the frontend is in hotkey capture mode
        (``is_hotkey_capture_active()`` returns True), the dictation callback
        is a no-op. This fixes sub-tasks 2.4 (Race A) and 2.5 entirely.
        """

        def _dictation_callback() -> None:
            # guard against hotkey callbacks firing during
            if getattr(self._app, "_shutting_down", False):
                log.debug("[HOTKEY] dictation ignored, app shutting down")
                return
            if keyboard_ownership().is_hotkey_capture_active():
                log.debug("[HOTKEY] dictation ignored, frontend hotkey capture active")
                return
            if self._no_active_engine():
                return
            if getattr(self._app.config, "recording_mode", "toggle") == "push_to_talk":
                self._start_ptt_safety_timer()
            self._force_caps_lock_off_before_dictation()
            from voice_typer.server import dictation_origin

            with dictation_origin.user_action("hotkey"):
                self._app.toggle_dictation()

        return _dictation_callback

    def _no_active_engine(self) -> bool:
        """Refuse the hotkey when neither a model nor a plugin owns dictation."""
        if no_active_engine(self._app):
            notify_no_active_engine(self._app)
            return True
        return False

    def _force_caps_lock_off_before_dictation(self) -> None:
        """Clear a leftover Caps Lock ON state before a dictation starts.

        Caps Lock doubles as the dictation key, so its OS toggle is unreachable
        by hand and a state that is ON (set before the app started, by another
        keyboard, or by a remote session) capitalizes everything the user types
        around the dictation. The native listener ignores injected input, so
        this synthetic toggle reaches the OS even while the hook is armed.
        """
        try:
            hotkey = str(getattr(self._app.config, "hotkey", "") or "")
        except Exception:
            return
        if "caps_lock" not in hotkey.lower():
            return
        try:
            import ctypes

            from voice_typer.server import hotkeys as _hotkeys_pkg
            from voice_typer.server.hotkeys.windows.caps_lock_suppressor import (
                force_caps_lock_off,
            )

            if not _hotkeys_pkg.is_windows():
                return
            force_caps_lock_off(ctypes.windll.user32)
        except Exception:
            log.debug("[HOTKEY] caps-lock clear before dictation failed (non-fatal)", exc_info=True)

    def _make_ptt_release_callback(self):
        """Wrap the PTT stop so the safety timer is canceled on key-up."""

        def _release_callback() -> None:
            self._cancel_ptt_safety_timer()
            self._app._stop_dictation()

        return _release_callback

    def _make_repaste_callback(self):
        """Create a repaste hotkey callback that respects keyboard ownership.

        HOTKEY- same defense-in-depth as the dictation
        callback. Prevents the repaste hotkey from firing during capture.
        """

        def _repaste_callback() -> None:
            # shutdown guard (see _dictation_callback).
            if getattr(self._app, "_shutting_down", False):
                log.debug("[HOTKEY] repaste ignored, app shutting down")
                return
            if keyboard_ownership().is_hotkey_capture_active():
                log.debug("[HOTKEY] repaste ignored, frontend hotkey capture active")
                return
            self._app.repaste_last()

        return _repaste_callback

    def _on_esc_release(self) -> None:
        """Release callback fired on key-up.

        Installed by ``_esc_callback`` when ``is_hotkey_capture_active()``
        is True. On key-up, this resets keyboard ownership and pushes
        ``hotkey_capture_cancel`` so the frontend exits capture mode.

        The cancelRecording guard in HotkeyPicker.tsx
        (``if (!recordingRef.current) return;``) prevents duplicate
        ``onCaptureEnd`` calls when both this backend push AND the
        frontend's own DOM key-up handler fire for the same ESC release.

        The check-then-clear is still technically racy (a
        concurrent ``.set()`` from the ESC listener between the
        ``is_set()`` read and the ``clear()`` write would be lost),
        but ``threading.Event`` is the canonical primitive for this
        pattern and the race window is sub-microsecond, far shorter
        than the human reaction time between two ESC presses.  The
        previous plain-bool implementation had the SAME race window
        plus an additional race against the IPC disconnect worker
        (which ``= False``'d the bool without consulting the listener
        thread).  The Event eliminates the second race; the first is
        tolerable (a second ESC press within the same microsecond
        would re-arm the flag and the next release would fire the
        cancel again, idempotent via ``keyboard_ownership().reset()``).
        """
        # Check-then-clear on the pending-capture-exit Event.
        if not self._esc_pending_capture_exit_event.is_set():
            return
        self._esc_pending_capture_exit_event.clear()

        log.info("[HOTKEY] ESC released during hotkey capture, canceling capture")

        # Reset keyboard ownership so subsequent keys
        keyboard_ownership().set_owner("normal", reason="esc released during capture")

        # Keep the legacy alias in sync with the canonical owner so readers
        self._app._esc_cancel_paused = False

        # Push an event so the frontend exits capture mode.
        from voice_typer.server import event_bus

        event_bus.publish({"type": "hotkey_capture_cancel"})

        # Reset the release callback so it doesn't fire again
        if self._esc_backend is not None:
            with contextlib.suppress(Exception):
                self._esc_backend.set_on_release(None)
        # Also clear the shared backend's ESC release callback so
        shared_native = self._shared_native()
        if shared_native is not None:
            with contextlib.suppress(Exception):
                shared_native.set_role_on_release("esc", None)
