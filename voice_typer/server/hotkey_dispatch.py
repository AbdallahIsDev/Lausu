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
            self._app.toggle_dictation()

        return _dictation_callback

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
