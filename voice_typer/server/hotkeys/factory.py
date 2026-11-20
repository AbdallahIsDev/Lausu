"""Cross-platform hotkey backend selection."""

import sys

from voice_typer.server import hotkeys as _hotkeys_pkg
from voice_typer.server.hotkey_spec import MOUSE_BUTTONS, parse_hotkey
from voice_typer.server.platform_utils import is_wayland_session
from voice_typer.server.tray_hotkey import format_hotkey_label

from .base import HotkeyBackend, log
from .mouse_backend import MouseHotkey
from .native_adapter import _NativeBackendAdapter
from .pynput_backend import PynputHotkey
from .wayland import WaylandHotkey
from .windows_native import WindowsNativeHotkey


# See pynput_backend.py for the rationale.
def is_windows() -> bool:
    return _hotkeys_pkg.is_windows()


def is_linux() -> bool:
    return _hotkeys_pkg.is_linux()


def create_hotkey_backend(hotkey_str: str, role: str | None = None) -> HotkeyBackend:
    """Pick a hotkey backend for ``hotkey_str``.

    Selection: native subprocess -> mouse listener -> Windows polling
    (~125 Hz via ``Sleep(8)``) -> Wayland socket -> pynput. Mouse-button
    specs route to the mouse listener first; keyboard specs try native
    before the platform fallbacks. ``role`` keeps per-backend resources
    distinct.
    """
    # Keyboard listeners never see mouse buttons, so mouse specs need a dedicated listener.
    if any(key in MOUSE_BUTTONS for key in parse_hotkey(hotkey_str).keys):
        if is_linux() and is_wayland_session():
            log.warning(
                "[HOTKEY] Wayland may not deliver global mouse clicks; "
                "the middle-button hotkey can stay silent in a native Wayland session"
            )
        log.info(
            "[HOTKEY] %s uses a mouse button -> MouseHotkey (role=%s)",
            format_hotkey_label(hotkey_str),
            role,
        )
        return MouseHotkey(hotkey_str)

    try:
        from voice_typer.server.native_hotkeys import create_native_backend

        native = create_native_backend(hotkey_str)
        if native is not None:
            # Adapt the native backend to the HotkeyBackend interface.
            log.debug(
                "[HOTKEY] Using native %s backend for %s (role=%s)",
                type(native).__name__,
                format_hotkey_label(hotkey_str),
                role,
            )
            # Forward role so the adapter can propagate it to a legacy fallback.
            return _NativeBackendAdapter(native, role=role)
    except Exception as exc:
        # A missing native backend is an expected fallback, hence the broad catch.
        log.info(
            "[HOTKEY] Native backend unavailable (%s); falling back to legacy",
            exc,
        )

    if is_windows():
        log.info(
            "[HOTKEY] Platform is win32 -> using WindowsNativeHotkey (legacy "
            "polling, native binary not built or unavailable)"
        )
        return WindowsNativeHotkey(hotkey_str)

    if is_linux() and is_wayland_session():
        # Wayland has no standard global-hotkey protocol, so delivery is not guaranteed.
        log.warning(
            "[HOTKEY] Wayland detected, global hotkeys may not work. "
            "Consider installing wlr-which-key or using the evdev backend "
            "(requires input group)."
        )
        # Caps Lock cannot be suppressed on Wayland; warn before relying on it.
        if hotkey_str and "caps_lock" in hotkey_str.lower():
            log.warning(
                "[HOTKEY] On Wayland, Caps Lock cannot be suppressed, "
                "your text will be capitalized. Bind Alt or a function "
                "key instead, or remap Caps Lock via your compositor's "
                "settings."
            )
        log.info(
            "[HOTKEY] Wayland detected -> using WaylandHotkey (Unix socket, legacy, role=%r)",
            role,
        )
        # Forward role so each backend gets its own socket filename.
        return WaylandHotkey(hotkey_str, role=role)

    log.info("[HOTKEY] Platform is %s -> using PynputHotkey (legacy)", sys.platform)
    return PynputHotkey(hotkey_str)
