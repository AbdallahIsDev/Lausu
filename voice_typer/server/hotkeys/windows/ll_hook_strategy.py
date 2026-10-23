"""WH_KEYBOARD_LL low-level hook strategy for ``WindowsNativeHotkey``."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import queue
import threading
from collections.abc import Callable

from ..base import log
from ..win32_vk import (
    _WHC_KEYBOARD_LL,
    _WM_KEYDOWN,
    _WM_KEYUP,
    _WM_SYSKEYDOWN,
    _WM_SYSKEYUP,
)


def start_hook_callback_worker(self) -> None:
    """Start the dedicated worker thread for LL hook callbacks."""
    if self._hook_callback_thread is not None and self._hook_callback_thread.is_alive():
        return

    def _worker() -> None:
        while True:
            try:
                fn = self._hook_callback_queue.get(timeout=0.5)
            except queue.Empty:
                if self._stop_event.is_set():
                    return
                continue
            if fn is None:
                return
            try:
                fn()
            except Exception:
                log.exception(
                    "[HOTKEY] Hook callback raised in worker thread, "
                    "callback dropped, hotkey still armed for next press"
                )

    self._hook_callback_thread = threading.Thread(target=_worker, daemon=True, name="WinHookCb")
    self._hook_callback_thread.start()


def enqueue_hook_callback(self, fn: Callable[[], None] | None) -> None:
    """Enqueue a callback for the worker thread. Non-blocking."""
    if fn is None:
        return
    try:
        self._hook_callback_queue.put_nowait(fn)
    except queue.Full:
        # raised maxsize from 64 to 256 (4× headroom) so a
        log.error(
            "[HOTKEY] LL hook callback queue full (size=%d), dropping callback. "
            "The hook worker thread may be stuck; hotkey presses will be missed "
            "until it recovers.",
            self._hook_callback_queue.maxsize,
        )


def handle_ll_key_event(self, w_param: int, vk: int, callback: Callable[[], None]) -> bool:
    """Apply one LL-hook key event; return True when it must be swallowed.

    Release matching deliberately ignores the live modifier state: the user may
    let go of Ctrl/Alt before the main key, and the action must still fire once.
    """
    is_down = w_param in (_WM_KEYDOWN, _WM_SYSKEYDOWN)
    is_up = w_param in (_WM_KEYUP, _WM_SYSKEYUP)
    if not (is_down or is_up):
        return False

    is_caps = self._is_caps_lock_hotkey
    is_ptt = self._on_release_callback is not None
    toggle_on_keyup = bool(getattr(self, "_toggle_on_keyup", False))

    if self._vk is not None:
        if vk != self._vk:
            return False
        if is_caps:
            if is_down:
                if not self._modifiers_pressed():
                    return False
                if self._ll_armed:
                    return True  # autorepeat: keep swallowing, never re-fire
                self._ll_armed = True
                log.info("[HOTKEY] Swallowed Caps Lock keydown (suppress OS toggle)")
                if is_ptt:
                    log.info("[HOTKEY FIRED] WH_KEYBOARD_LL Caps Lock keydown (PTT)")
                    self._enqueue_hook_callback(callback)
                return True
            if not self._ll_armed:
                return False
            self._ll_armed = False
            if is_ptt:
                log.info("[HOTKEY] Caps Lock released via WH_KEYBOARD_LL hook (PTT)")
                self._enqueue_hook_callback(self._on_release_callback)
            else:
                log.info("[HOTKEY FIRED] WH_KEYBOARD_LL Caps Lock key-up (toggle)")
                self._enqueue_hook_callback(callback)
            return True

        if is_down:
            if not self._modifiers_pressed():
                return False
            if self._ll_armed:
                return False
            self._ll_armed = True
            if is_ptt:
                log.info("[HOTKEY FIRED] WH_KEYBOARD_LL caught vk=0x%X (PTT)", vk)
                self._enqueue_hook_callback(callback)
            elif toggle_on_keyup:
                pass
            else:
                log.info("[HOTKEY FIRED] WH_KEYBOARD_LL caught vk=0x%X (%s)", vk, self.hotkey_str)
                self._enqueue_hook_callback(callback)
            return False

        if not self._ll_armed:
            return False
        self._ll_armed = False
        if is_ptt:
            log.info("[HOTKEY] Key released via WH_KEYBOARD_LL hook (vk=0x%X)", vk)
            self._enqueue_hook_callback(self._on_release_callback)
        elif toggle_on_keyup:
            log.info("[HOTKEY FIRED] WH_KEYBOARD_LL key-up (toggle, vk=0x%X)", vk)
            self._enqueue_hook_callback(callback)
        return False

    # Modifier-only specs never reach this hook: windows_native.start()
    # routes them to the modifier-only polling loop, which can tell a tap
    # from the start of another shortcut.
    return False


def install_low_level_hook(self, callback) -> bool:
    """Install a WH_KEYBOARD_LL low-level keyboard hook for this hotkey."""
    if not self._user32 or not self._kernel32:
        return False
    try:
        # Start the worker thread BEFORE installing the hook
        self._start_hook_callback_worker()

        # KeyboardProc signature: (nCode, wParam, lParam) -> LRESULT.
        hook_proc = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_int,
            ctypes.wintypes.WPARAM,
            ctypes.wintypes.LPARAM,
        )

        # KBDLLHOOKSTRUCT: vkCode, scanCode, flags, time, dwExtraInfo
        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", ctypes.c_ulong),
                ("scanCode", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        backend = self  # closure reference

        def _hook_proc(n_code, w_param, l_param):
            try:
                if n_code == 0:  # HC_ACTION
                    ks = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    if backend.handle_ll_key_event(w_param, ks.vkCode, callback):
                        return 1  # swallow, do not call CallNextHookEx
            except Exception:
                log.debug("[HOTKEY] LL hook proc error", exc_info=True)
            # Pass to the next hook so we don't break other hooks.
            return backend._user32.CallNextHookEx(backend._hook_handle or 0, n_code, w_param, l_param)

        self._hook_proc = hook_proc(_hook_proc)
        # Set argtypes for SetWindowsHookExW / UnhookWindowsHookEx.
        self._user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            hook_proc,
            ctypes.wintypes.HINSTANCE,
            ctypes.wintypes.DWORD,
        ]
        self._user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK
        self._user32.CallNextHookEx.argtypes = [
            ctypes.wintypes.HHOOK,
            ctypes.c_int,
            ctypes.wintypes.WPARAM,
            ctypes.wintypes.LPARAM,
        ]
        self._user32.CallNextHookEx.restype = ctypes.c_long
        self._user32.UnhookWindowsHookEx.argtypes = [ctypes.wintypes.HHOOK]
        self._user32.UnhookWindowsHookEx.restype = ctypes.c_int

        # hMod must be NULL for a low-level hook (it runs in this process).
        handle = self._user32.SetWindowsHookExW(_WHC_KEYBOARD_LL, self._hook_proc, 0, 0)
        if not handle:
            # previously this log line claimed "(GetLastError)"
            err = self._kernel32.GetLastError()
            self._last_error = err
            log.warning(
                "[HOTKEY] SetWindowsHookExW(WH_KEYBOARD_LL) failed, "
                "GetLastError=%d (0x%X), falling back to RegisterHotKey/polling",
                err,
                err,
            )
            self._hook_proc = None
            return False
        self._hook_handle = handle
        # ``_vk`` is None for a modifier-only hotkey (<alt>, <ctrl>, ...), and
        # ``%X`` on None raises at *emit* time -- inside this try, which then
        # undid a hook that had installed fine and reported it as a failure.
        # Modifier-only specs silently fell back to the polling loop.
        log.info(
            "[HOTKEY] WH_KEYBOARD_LL hook installed (vk=%s)",
            "modifier-only" if self._vk is None else f"0x{self._vk:X}",
        )
        return True
    except Exception:
        log.exception("[HOTKEY] Failed to install WH_KEYBOARD_LL hook")
        self._hook_proc = None
        self._hook_handle = None
        return False
