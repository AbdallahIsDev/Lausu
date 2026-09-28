"""Focused-element text-input detection for the auto-paste gate.

One question: is the focused UI element a text input? Contract, same
on every platform:

* confirmed text input → return True (paste may proceed)
* confirmed non-text control (button, label, password field, ...) →
  return False (skip the paste keystroke; the transcription stays on
  the clipboard)
* detection unavailable or role unrecognized → return True (fail
  open) so users who currently get auto-paste are not regressed

Password fields are already blocked fail-closed by :mod:`.validation`;
the password roles checked here are defense in depth.

Cross-module references go through ``_pkg.NAME`` at call time so test
patches on the package propagate (same pattern as :mod:`.validation`).
"""

from __future__ import annotations

import contextlib
from typing import Any  # noqa: F401  (used in type hints)

# Call-time _pkg lookups (C-ARCH-2): package is partial at module load.
import voice_typer.server.clipboard_target_safety as _pkg

# macOS AXRole values that accept typed/pasted text.
_MACOS_TEXT_ROLES: frozenset[str] = frozenset(
    {
        "AXTextField",
        "AXTextArea",
        "AXComboBox",
        "AXWebArea",
        "AXSearchField",
    }
)

# AXRole values that are definitely NOT text inputs.
_MACOS_NON_TEXT_ROLES: frozenset[str] = frozenset(
    {
        "AXButton",
        "AXCheckBox",
        "AXRadioButton",
        "AXStaticText",
        "AXImage",
        "AXLink",
        "AXSlider",
        "AXIncrementor",
        "AXPopUpButton",
        "AXMenu",
        "AXMenuBar",
        "AXMenuItem",
        "AXMenuBarItem",
        "AXTab",
        "AXTabGroup",
        "AXToolbar",
        "AXScrollBar",
        "AXProgressIndicator",
        "AXDisclosureTriangle",
        "AXValueIndicator",
        "AXWindow",
    }
)

# UIA_ControlTypePropertyId = 30003. Verified against
# UIAutomationClient.h: ComboBox=50003, Edit=50004, Document=50030.
_WIN_TEXT_CONTROL_TYPES: frozenset[int] = frozenset({50003, 50004, 50030})

# UIA control types that are definitely NOT text inputs.
_WIN_NON_TEXT_CONTROL_TYPES: frozenset[int] = frozenset(
    {
        50000,  # Button
        50001,  # Calendar
        50002,  # CheckBox
        50005,  # Hyperlink
        50006,  # Image
        50007,  # ListItem
        50008,  # List
        50009,  # Menu
        50010,  # MenuBar
        50011,  # MenuItem
        50012,  # ProgressBar
        50013,  # RadioButton
        50014,  # ScrollBar
        50015,  # Slider
        50016,  # Spinner
        50017,  # StatusBar
        50018,  # Tab
        50019,  # TabItem
        50020,  # Text (static label)
        50021,  # ToolBar
        50022,  # ToolTip
        50023,  # Tree
        50024,  # TreeItem
        50027,  # Thumb
        50028,  # DataGrid
        50029,  # DataItem
        50031,  # SplitButton
        50032,  # Window
        50034,  # Header
        50035,  # HeaderItem
        50037,  # TitleBar
        50038,  # Separator
        50039,  # SemanticZoom
        50040,  # AppBar
    }
)


def _warn_text_focus_unavailable(detail: str) -> None:
    """Log once per process that text-focus detection is unavailable."""
    if not _pkg._TEXT_FOCUS_UNAVAILABLE_WARNED:
        _pkg._TEXT_FOCUS_UNAVAILABLE_WARNED = True
        _pkg._log().warning(
            "[CLIPBOARD] Text-field focus detection unavailable (%s), "
            "failing open (auto-paste still allowed)",
            detail,
        )
    else:
        _pkg._log().debug("[CLIPBOARD] Text-field focus detection unavailable (%s), failing open", detail)


def _macos_focused_ax_role() -> str | None:
    """Return the frontmost app's focused AXRole, or None if undetectable."""
    try:
        import AppKit
        import ApplicationServices
    except ImportError:
        _warn_text_focus_unavailable("pyobjc not installed")
        return None
    try:
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        if workspace is None:
            return None
        front_app = workspace.frontmostApplication()
        if front_app is None:
            return None
        pid = front_app.processIdentifier()
        if pid is None or pid <= 0:
            return None
        app_elem = ApplicationServices.AXUIElementCreateApplication(pid)
        if app_elem is None:
            return None
        focused = _pkg._ax_result_value(
            ApplicationServices.AXUIElementCopyAttributeValue(app_elem, "AXFocusedUIElement", None)
        )
        if focused is None:
            return None
        role = _pkg._ax_result_value(
            ApplicationServices.AXUIElementCopyAttributeValue(focused, "AXRole", None)
        )
        return role if isinstance(role, str) else None
    except Exception:
        _pkg._log().debug("[CLIPBOARD] macOS focused AXRole fetch failed, failing open", exc_info=True)
        return None


def _is_text_field_focused_macos() -> bool:
    """True if the macOS focused element is a text input (or undetectable)."""
    role = _macos_focused_ax_role()
    if role is None:
        return True
    if role == "AXSecureTextField":
        return False
    if role in _MACOS_TEXT_ROLES:
        return True
    return role not in _MACOS_NON_TEXT_ROLES


def _linux_role_sets(pyatspi: Any) -> tuple[frozenset[Any], frozenset[Any], Any | None]:
    """Resolve AT-SPI text / non-text role sets and the password role."""

    def _role(name: str) -> Any:
        return getattr(pyatspi, name, None)

    text_names = (
        "ROLE_ENTRY",
        "ROLE_TEXT",
        "ROLE_TERMINAL",
        "ROLE_DOCUMENT_FRAME",
        "ROLE_TEXT_LEAF",
    )
    non_text_names = (
        "ROLE_PUSH_BOX",
        "ROLE_CHECK_BOX",
        "ROLE_RADIO_BUTTON",
        "ROLE_LABEL",
        "ROLE_STATIC",
        "ROLE_IMAGE",
        "ROLE_MENU_BAR",
        "ROLE_MENU",
        "ROLE_MENU_ITEM",
        "ROLE_SCROLL_BAR",
        "ROLE_SLIDER",
        "ROLE_PROGRESS_BAR",
        "ROLE_TOOL_BAR",
        "ROLE_TOOL_TIP",
        "ROLE_TAB",
        "ROLE_TAB_LIST",
        "ROLE_TREE",
        "ROLE_TREE_ITEM",
        "ROLE_WINDOW_FRAME",
        "ROLE_FRAME",
        "ROLE_SEPARATOR",
        "ROLE_FILLER",
    )
    text = frozenset(r for r in (_role(n) for n in text_names) if r is not None)
    non_text = frozenset(r for r in (_role(n) for n in non_text_names) if r is not None)
    return text, non_text, _role("ROLE_PASSWORD_TEXT")


def _is_text_field_focused_linux() -> bool:
    """True if the Linux AT-SPI focused element is a text input (or undetectable)."""
    try:
        import pyatspi
    except ImportError:
        _warn_text_focus_unavailable("pyatspi not installed")
        return True
    try:
        state_focused = getattr(pyatspi, "STATE_FOCUSED", 1 << 10)
        _pkg._PYATSPI_STATE_FOCUSED = state_focused
        desktop = pyatspi.Registry.getDesktop(0)
        if desktop is None:
            return True
        focused = _pkg._find_focused_atspi_accessible(desktop, state_focused, max_depth=10)
        if focused is None:
            return True
        role = focused.getRole()
        text_roles, non_text_roles, password_role = _linux_role_sets(pyatspi)
        if password_role is not None and role == password_role:
            return False
        if role in text_roles:
            return True
        return role not in non_text_roles
    except Exception:
        _pkg._log().debug("[CLIPBOARD] Linux text-field focus check failed, failing open", exc_info=True)
        return True


def _is_text_field_focused_windows(focused: Any = None) -> bool:
    """True if the Windows UIA focused element is a text input (or undetectable)."""
    if not _pkg.is_windows():
        return True
    try:
        import comtypes
    except ImportError:
        _warn_text_focus_unavailable("comtypes not installed")
        return True
    try:
        owns_com = focused is None
        if owns_com:
            comtypes.CoInitialize()
        try:
            if focused is None:
                focused = _pkg._get_uia_focused_element()
            if focused is None:
                return True
            control_type = focused.GetCurrentPropertyValue(30003)
            if control_type in _WIN_TEXT_CONTROL_TYPES:
                return True
            if _pkg._is_content_editable(focused):
                return True
            return control_type not in _WIN_NON_TEXT_CONTROL_TYPES
        finally:
            if owns_com:
                with contextlib.suppress(Exception):
                    comtypes.CoUninitialize()
    except Exception:
        _pkg._log().debug("[CLIPBOARD] Windows text-field focus check failed, failing open", exc_info=True)
        return True


def _is_text_field_focused() -> bool:
    """Platform dispatch. Never raises: undetectable focus fails open."""
    try:
        if _pkg.is_windows():
            return _is_text_field_focused_windows()
        if _pkg.is_macos():
            return _is_text_field_focused_macos()
        if _pkg.is_linux():
            return _is_text_field_focused_linux()
        return True
    except Exception:
        _pkg._log().debug("[CLIPBOARD] text-field focus dispatch failed, failing open", exc_info=True)
        return True


__all__ = [
    "_is_text_field_focused",
    "_is_text_field_focused_linux",
    "_is_text_field_focused_macos",
    "_is_text_field_focused_windows",
]
