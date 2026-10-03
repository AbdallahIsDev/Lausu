"""Caps Lock / toggle / push-to-talk fire-point matrix.

Exercises the real subprocess backends (``_handle_line`` wire events) and
the Windows ``WH_KEYBOARD_LL`` hook proc. Pins distinct fire points so a
Caps Lock special-case cannot leak onto other keys and so PTT start/stop
keeps requiring a delivered KEY_UP (see the emit-before-swallow listeners).
"""

from __future__ import annotations

import ctypes
import sys
from unittest.mock import MagicMock

from tests.test_native_hotkeys_autorepeat import (
    _make_linux_backend,
    _make_macos_backend,
)


def _make_windows_hook_backend(monkeypatch, hotkey_str: str):
    """Construct a WindowsHookHotkey with platform stubs in place."""
    from voice_typer.server import native_hotkeys

    monkeypatch.setattr(native_hotkeys, "is_windows", lambda: True)
    monkeypatch.setattr(native_hotkeys, "is_linux", lambda: False)
    monkeypatch.setattr(native_hotkeys, "is_macos", lambda: False)
    monkeypatch.setattr(sys, "platform", "win32")
    from voice_typer.server.native_hotkeys import WindowsHookHotkey

    return WindowsHookHotkey(hotkey_str)


class TestCapsLockToggleOnKeyup:
    """Case 1: Caps Lock + toggle_on_keyup fires once on KEY_DOWN."""

    def test_keydown_fires_once_keyup_does_not_double(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        assert fired == ["toggle"]
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle"], f"KEY_UP must not double-toggle, got {fired}"

    def test_same_contract_on_windows_hook_backend(self, monkeypatch):
        b = _make_windows_hook_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle"]

    def test_same_contract_on_macos_backend(self, monkeypatch):
        b = _make_macos_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle"]


class TestCapsLockPushToTalk:
    """Case 2: Caps Lock + PTT starts on KEY_DOWN, stops on KEY_UP."""

    def test_keydown_starts_keyup_stops(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))
        b._handle_line("KEY_DOWN:CapsLock")
        assert started == ["start"]
        assert stopped == []
        b._handle_line("KEY_UP:CapsLock")
        assert started == ["start"]
        assert stopped == ["stop"], f"KEY_UP must stop PTT, got {stopped}"

    def test_keyup_stop_requires_delivered_keyup(self, monkeypatch):
        """If KEY_UP never arrives (unpatched listener), PTT cannot stop.

        The listeners must emit KEY_UP before swallow; this pins the
        consumer side of that contract.
        """
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))
        b._handle_line("KEY_DOWN:CapsLock")
        assert started == ["start"]
        assert stopped == [], "no KEY_UP yet, PTT still held"

    def test_fresh_press_after_release_restarts(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        assert started == ["start", "start"]
        assert stopped == ["stop", "stop"]

    def test_ptt_takes_precedence_over_toggle_on_keyup(self, monkeypatch):
        """When both flags are set, PTT owns the edge pair (start/stop)."""
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        assert started == ["start"]
        assert stopped == ["stop"]


class TestAutorepeatDoesNotRefire:
    """Case 3: a second KEY_DOWN without KEY_UP does not re-fire."""

    def test_caps_toggle_autorepeat_suppressed(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_DOWN:CapsLock")
        assert fired == ["toggle"], f"autorepeat must not re-toggle, got {fired}"

    def test_caps_ptt_autorepeat_does_not_restarts(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        assert started == ["start"]
        assert stopped == ["stop"]


class TestCapsLockLegacyToggle:
    """Case 4: Caps Lock + legacy toggle fires once on KEY_DOWN."""

    def test_legacy_toggle_fires_on_keydown(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        # toggle_on_keyup stays False (legacy).
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        assert fired == ["toggle"]
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle"], f"legacy toggle ignores KEY_UP, got {fired}"

    def test_legacy_toggle_autorepeat_suppressed(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_DOWN:CapsLock")
        assert fired == ["toggle"]


class TestNonCapsToggleOnKeyupUnaffected:
    """Case 5: Caps special-case must not leak onto ordinary keys."""

    def test_f2_toggle_on_keyup_fires_on_keyup_only(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<f2>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:F2")
        assert fired == [], "F2 must defer toggle to KEY_UP"
        b._handle_line("KEY_UP:F2")
        assert fired == ["toggle"]

    def test_f2_ptt_still_start_stop(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<f2>")
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))
        b._handle_line("KEY_DOWN:F2")
        b._handle_line("KEY_UP:F2")
        assert started == ["start"]
        assert stopped == ["stop"]

    def test_caps_with_modifiers_is_not_caps_only_special_case(self, monkeypatch):
        """`<ctrl>+<caps_lock>` keeps ordinary toggle_on_keyup semantics."""
        b = _make_linux_backend(monkeypatch, "<ctrl>+<caps_lock>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("MOD_DOWN:Ctrl")
        b._handle_line("KEY_DOWN:CapsLock")
        assert fired == [], "combo must defer toggle to KEY_UP"
        b._handle_line("KEY_UP:CapsLock")
        assert fired == ["toggle"]


class TestWindowsLLHookCapsPath:
    """Case 6: WindowsNativeHotkey LL-hook Caps Lock fires toggle on key-up."""

    def _install_hook(self, callback):
        from voice_typer.server.hotkeys import WindowsNativeHotkey
        from voice_typer.server.hotkeys.win32_vk import _VK_CAPITAL

        backend = WindowsNativeHotkey("<caps_lock>")
        backend._user32 = MagicMock()
        backend._kernel32 = MagicMock()
        backend._user32.SetWindowsHookExW.return_value = 0xDEADBEEF
        backend._user32.CallNextHookEx.return_value = 0
        backend._is_caps_lock_hotkey = True
        backend._vk = _VK_CAPITAL
        backend._modifiers_pressed = lambda: True
        fired: list[object] = []
        backend._enqueue_hook_callback = lambda fn: fired.append(fn)  # type: ignore[method-assign]
        assert backend._install_low_level_hook(callback)
        return backend, fired

    def _key_event_struct(self, vk: int):
        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", ctypes.c_ulong),
                ("scanCode", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        ks = KBDLLHOOKSTRUCT()
        ks.vkCode = vk
        return ks

    def test_caps_keyup_fires_toggle_and_swallows(self):
        from voice_typer.server.hotkeys.win32_vk import (
            _VK_CAPITAL,
            _WM_KEYDOWN,
            _WM_KEYUP,
        )

        toggle = MagicMock(name="toggle")
        backend, fired = self._install_hook(toggle)
        ks = self._key_event_struct(_VK_CAPITAL)
        addr = ctypes.addressof(ks)

        # KEY_DOWN is swallowed so the OS Caps state does not toggle; no fire.
        assert backend._hook_proc(0, _WM_KEYDOWN, addr) == 1
        assert fired == []

        # KEY_UP fires the toggle exactly once and is swallowed.
        assert backend._hook_proc(0, _WM_KEYUP, addr) == 1
        assert fired == [toggle]

    def test_non_caps_keyup_does_not_use_caps_path(self):
        """F2 on the LL hook with toggle_on_keyup still fires on key-up,
        but through the ordinary branch (not the Caps swallow path)."""
        from voice_typer.server.hotkeys import WindowsNativeHotkey
        from voice_typer.server.hotkeys.win32_vk import _WM_KEYDOWN, _WM_KEYUP

        vk_f2 = 0x71
        backend = WindowsNativeHotkey("<f2>")
        backend._user32 = MagicMock()
        backend._kernel32 = MagicMock()
        backend._user32.SetWindowsHookExW.return_value = 0xDEADBEEF
        backend._user32.CallNextHookEx.return_value = 0
        backend._is_caps_lock_hotkey = False
        backend._vk = vk_f2
        backend._modifiers_pressed = lambda: True
        backend.set_toggle_on_keyup(True)
        fired: list[object] = []
        backend._enqueue_hook_callback = lambda fn: fired.append(fn)  # type: ignore[method-assign]
        callback = MagicMock(name="toggle")
        assert backend._install_low_level_hook(callback)

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", ctypes.c_ulong),
                ("scanCode", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        ks = KBDLLHOOKSTRUCT()
        ks.vkCode = vk_f2
        addr = ctypes.addressof(ks)

        # F2 key-down is NOT swallowed (ordinary key) and does not fire
        # under toggle_on_keyup.
        assert backend._hook_proc(0, _WM_KEYDOWN, addr) == 0
        assert fired == []
        # F2 key-up fires the toggle (ordinary branch).
        assert backend._hook_proc(0, _WM_KEYUP, addr) == 0
        assert fired == [callback]


class TestNativeMatchingCapsFlags:
    """Case 7: matching requires empty modifiers + is_caps_lock + toggle."""

    def test_parsed_caps_lock_flags(self):
        from voice_typer.server.native_hotkeys import parse_hotkey_spec

        parsed = parse_hotkey_spec("<caps_lock>")
        assert parsed is not None
        assert parsed["modifiers"] == set()
        assert parsed["main_key"] == "CapsLock"
        assert parsed["is_caps_lock"] is True

    def test_special_case_needs_empty_modifiers_and_no_ptt(self, monkeypatch):
        """toggle_on_keyup Caps-only with on_release set must use PTT edges."""
        b = _make_linux_backend(monkeypatch, "<caps_lock>")
        b.set_toggle_on_keyup(True)
        started: list[str] = []
        stopped: list[str] = []
        b._callback = lambda: started.append("start")  # noqa: E731
        b.set_on_release(lambda: stopped.append("stop"))
        b._handle_line("KEY_DOWN:CapsLock")
        b._handle_line("KEY_UP:CapsLock")
        assert started == ["start"]
        assert stopped == ["stop"], "PTT path must own both edges"

    def test_special_case_requires_is_caps_lock(self, monkeypatch):
        b = _make_linux_backend(monkeypatch, "<space>")
        b.set_toggle_on_keyup(True)
        fired: list[str] = []
        b._callback = lambda: fired.append("toggle")  # noqa: E731
        b._handle_line("KEY_DOWN:Space")
        assert fired == []
        b._handle_line("KEY_UP:Space")
        assert fired == ["toggle"]
