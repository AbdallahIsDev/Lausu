"""Mouse-button hotkey backend (pynput mouse listener).

The wheel click is a whole trigger: validation refuses modifiers or a
second key, and the mouse listener never reports keyboard state. That is
why this backend answers only for mouse specs, leaving every keyboard
path (native listeners included) untouched.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from .base import HotkeyBackend, log


def _load_mouse():
    """Import seam so tests can supply a fake ``pynput.mouse`` module."""
    from pynput import mouse

    return mouse


class MouseHotkey(HotkeyBackend):
    """Middle-mouse-button hotkey backend."""

    def __init__(self, hotkey_str: str):
        super().__init__(hotkey_str)
        self._listener = None
        self._middle_button = None
        self._callback: Callable[[], None] | None = None
        self._held = False

    def start(self, callback: Callable[[], None]) -> None:
        mouse = _load_mouse()
        self._callback = callback
        self._middle_button = mouse.Button.middle
        self._held = False
        self._listener = mouse.Listener(on_click=self._on_click)
        self._listener.start()
        if not self.is_alive():
            raise RuntimeError(f"mouse listener for {self.hotkey_str!r} is not alive after start")
        log.info("[HOTKEY] Mouse listener started for %r", self.hotkey_str)

    def _invoke(self, callback: Callable[[], None] | None) -> None:
        if callback is None:
            return
        try:
            callback()
        except Exception:
            # A raising callback stops a pynput listener thread outright.
            log.exception("[HOTKEY] mouse hotkey callback raised")

    def _on_click(self, x: int, y: int, button: object, pressed: bool) -> None:
        if button != self._middle_button:
            return
        callback = self._callback
        if callback is None:
            return
        if pressed:
            if self._held:
                return
            self._held = True
            if self._on_release_callback is not None:
                # Push-to-talk starts on press and stops on release.
                self._invoke(callback)
            elif not self._toggle_on_keyup:
                self._invoke(callback)
            return
        if not self._held:
            return
        self._held = False
        if self._on_release_callback is not None:
            self._invoke(self._on_release_callback)
        elif self._toggle_on_keyup:
            self._invoke(callback)

    def stop(self) -> None:
        if self._listener is not None:
            with contextlib.suppress(Exception):
                self._listener.stop()
            self._listener = None
        self._callback = None
        self._held = False

    def is_alive(self) -> bool:
        return self._listener is not None and bool(self._listener.is_alive())

    def diagnose(self) -> str:
        if self._listener is None:
            return "MouseHotkey: no listener registered"
        return (
            f"MouseHotkey\nHotkey: {self.hotkey_str}\nListener alive: {self.is_alive()}"
        )


__all__ = ["MouseHotkey"]
