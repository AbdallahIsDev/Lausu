"""Shared Win32 SendInput keyboard-injection helpers."""

from __future__ import annotations

import ctypes
from typing import Any

# Fixed-width field types, NOT ctypes.wintypes aliases: wintypes DWORD/LONG
# are c_ulong/c_long (8 bytes on LP64 Linux/macOS, 4 on Windows), which
# inflated this model to 56 B off-Windows. The Win32 ABI is 40 B on x64.
_WORD = ctypes.c_ushort
_DWORD = ctypes.c_uint32
_LONG = ctypes.c_int32

# ULONG_PTR is pointer-sized: 4 bytes on 32-bit Windows, 8 bytes on
_ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32


class KEYBDINPUT(ctypes.Structure):
    """Win32 ``KEYBDINPUT``: payload for a keyboard INPUT event.

    See https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-keybdinput
    """

    _fields_ = (
        ("wVk", _WORD),
        ("wScan", _WORD),
        ("dwFlags", _DWORD),
        ("time", _DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    )
    # by a synthetic press. Matches the Win32 constant and the legacy
    KEYUP = 0x0002


class MOUSEINPUT(ctypes.Structure):
    """Win32 ``MOUSEINPUT``: the largest ``INPUT`` union member.

    Only its size matters here (the app never synthesizes mouse
    input): without it the union collapses to ``KEYBDINPUT`` (24 B),
    ``INPUT`` shrinks to 32 B instead of the real 40 B on x64, and
    ``SendInput`` rejects every call (returns 0, no toggle ever lands).
    """

    _fields_ = (
        ("dx", _LONG),
        ("dy", _LONG),
        ("mouseData", _DWORD),
        ("dwFlags", _DWORD),
        ("time", _DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    )


class InputUnion(ctypes.Union):
    """Win32 ``INPUT`` union, only the keyboard branch is populated."""

    _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT))


class INPUT(ctypes.Structure):
    """Win32 ``INPUT`` structure (keyboard variant).

    See https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-input
    """

    _fields_ = (
        ("type", _DWORD),
        # The C struct has an anonymous union here; ctypes requires a
        ("ki", InputUnion),
    )
    # ``INPUT_KEYBOARD`` = 1, selects the ``ki`` union member.
    KEYBOARD = 1


def _build_keyboard_input(vk: int, scan: int, flags: int) -> INPUT:
    """Build a single Win32 ``INPUT`` struct for a keyboard event."""
    return INPUT(
        INPUT.KEYBOARD,
        InputUnion(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)),
    )


def _send_keyboard_event(user32: Any, vk: int, scan: int, flags: int) -> int:
    """Send a single keyboard event via the modern ``SendInput`` API.

    Returns the number of events successfully inserted into the input
    """
    inp = _build_keyboard_input(vk, scan, flags)
    events = (INPUT * 1)(inp)
    # ``user32`` is typed ``Any`` (ctypes WinDLL), so ``SendInput``
    return int(user32.SendInput(1, ctypes.byref(events), ctypes.sizeof(INPUT)))


__all__ = [
    "INPUT",
    "InputUnion",
    "KEYBDINPUT",
    "MOUSEINPUT",
    "_build_keyboard_input",
    "_send_keyboard_event",
]
