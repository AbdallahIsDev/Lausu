"""``IPC_CONFIG_ALLOWLIST``.
Extracted from the original monolithic ``config_validators.py`` (package
  ``voice_typer/server/hotkey_reserved.json``),
* the 9 ``_check_*`` stage helpers that make up :func:`_validate_hotkey`,
orchestrator (``_validate_hotkey``) stays readable. Each helper returns
an error string or ``None``; the first non-``None`` wins, preserving
"""

from __future__ import annotations

import json as _json
from pathlib import Path as _Path

from voice_typer.server.platform_utils import is_macos as _is_macos, is_windows as _is_windows

# OS-reserved shortcuts that must never be assigned

# load the canonical reserved-shortcut table from the
_RESERVED_DATA_PATH = _Path(__file__).resolve().parent.parent / "hotkey_reserved.json"


def _load_reserved_data() -> dict:
    """Load and cache the reserved-hotkey JSON config.

    Returns a dict with keys:
    """
    with _RESERVED_DATA_PATH.open("r", encoding="utf-8") as f:
        return _json.load(f)


_RESERVED_DATA = _load_reserved_data()

# Per-platform reserved shortcuts. Stored in the SAME format as user input
_RESERVED_HOTKEYS: dict[str, set[str]] = {
    platform: set(entries) for platform, entries in _RESERVED_DATA["per_platform_reserved"].items()
}

# Universal window-management shortcuts blocked on EVERY platform.
_UNIVERSAL_RESERVED_HOTKEYS = frozenset(_RESERVED_DATA["universal_reserved"])

# Common Ctrl+<letter> shortcuts that are universally expected by users
_BLOCKED_CTRL_LETTERS = frozenset(_RESERVED_DATA["blocked_ctrl_letters"])

# Modifier keys recognized in the hotkey string (pynput-style, lowercase).
_HOTKEY_MODIFIERS = frozenset(_RESERVED_DATA["modifiers"])


def _platform_key() -> str:
    """Return the platform key for ``_RESERVED_HOTKEYS`` lookup."""
    if _is_windows():
        return "win32"
    if _is_macos():
        return "darwin"
    return "linux"


def _parse_hotkey_parts(hotkey: str) -> list[str]:
    """Parse a hotkey string like ``"<ctrl>+<alt>+v"`` into ``["ctrl","alt","v"]``."""
    from voice_typer.server.hotkey_spec import parse_hotkey

    spec = parse_hotkey(hotkey)
    if spec.is_empty:
        return []
    return list(spec.modifiers) + list(spec.keys)


# ``<win>``, ``<super>`` and ``<cmd>`` are three names for the same physical
# shell key: every listener maps all three to one wire name (the Windows
# hook reports ``Win``, the macOS tap reports ``Cmd``, evdev reports
# ``Super``), so a spec spelling one of them must hit the same table rows.
_SHELL_ALIASES: dict[str, str] = {
    name: "super"
    for name in (
        "super",
        "super_l",
        "super_r",
        "win",
        "win_l",
        "win_r",
        "cmd",
        "cmd_l",
        "cmd_r",
    )
}


def _tokenize_spec(value: str) -> list[str]:
    """Split a spec into lowercase bracket-free tokens, keeping order."""
    tokens: list[str] = []
    for raw in value.split("+"):
        token = raw.replace("<", "").replace(">", "").strip().lower()
        if token:
            tokens.append(token)
    return tokens


def _normalize_spec(value: str) -> str:
    """Bracket-agnostic, case-insensitive, shell-alias-aware spec key.

    Mirrors the renderer's ``normalizeHotkey`` (so both sides reject the
    same shortcuts) and collapses the three shell-key spellings, otherwise
    ``<alt>+space`` or ``<cmd>+m`` slip past a table written as
    ``<alt>+<space>`` / ``<win>+<m>``.
    """
    tokens = _tokenize_spec(value)
    if len(tokens) < 2:
        # Bare modifiers keep their own spelling: ``<cmd_l>`` is a
        # deliberate modifier-only trigger (the native listener can
        # swallow it), not the shell key the table blocks bare.
        return "+".join(tokens)
    return "+".join(_SHELL_ALIASES.get(t, t) for t in tokens)


# Normalised lookups: the tables are written in canonical bracketed form
# (``<alt>+<space>``) while specs arrive pynput-style (``<alt>+space``),
# so both sides go through ``_normalize_spec`` before comparison.
_UNIVERSAL_RESERVED_NORMALIZED: frozenset[str] = frozenset(
    _normalize_spec(entry) for entry in _UNIVERSAL_RESERVED_HOTKEYS
)
_RESERVED_NORMALIZED: dict[str, frozenset[str]] = {
    platform: frozenset(_normalize_spec(entry) for entry in entries)
    for platform, entries in _RESERVED_HOTKEYS.items()
}


def _check_basic_shape(value: object) -> str | None:
    """Stage 1: type / length / emptiness guards (shared by all hotkeys)."""
    if not isinstance(value, str):
        return f"must be a string, got {type(value).__name__}"
    if len(value) > 256:
        return "exceeds maximum length 256"
    if not value.strip():
        return "must not be empty"
    return None


def _check_universal_reserved(normalized: str) -> str | None:
    """Stage 2: OS / common-app shortcuts blocked on EVERY platform."""
    if normalized in _UNIVERSAL_RESERVED_NORMALIZED:
        return "reserved, conflicts with operating system or common app shortcuts"
    return None


def _check_platform_reserved(normalized: str, platform: str) -> str | None:
    """Stage 3: per-platform OS-reserved shortcuts."""
    if normalized in _RESERVED_NORMALIZED.get(platform, frozenset()):
        return f"reserved by operating system ({platform})"
    return None


def _check_modifier_order(value: str) -> str | None:
    """Stage 5b: a combo mixing keys and modifiers must END with the key.

    ``<ctrl>+<alt>+v`` is the canonical form; ``<ctrl>+v+<alt>`` is the
    same chord typed in the wrong order and would otherwise be accepted
    here while the renderer rejects it (the renderer's
    ``mustEndWithNonModifier`` rule).
    """
    tokens = _tokenize_spec(value)
    if len(tokens) < 2:
        return None
    non_mods = [t for t in tokens if t not in _HOTKEY_MODIFIERS]
    if non_mods and tokens[-1] in _HOTKEY_MODIFIERS:
        return f"a combo must end with its key, e.g. <ctrl>+<alt>+{non_mods[0]} (got {tokens[-1]} last)"
    return None


def _check_single_alphanumeric(parts: list[str]) -> str | None:
    """Stage 4: reject a standalone single letter/digit."""
    if len(parts) == 1:
        sole = parts[0]
        if len(sole) == 1 and sole.isalnum():
            return f"single letters and digits can't be used as hotkeys, '{sole}' would interfere with typing"
    return None


def _check_multi_non_modifier(parts: list[str]) -> str | None:
    """Stage 5: reject combos with MORE than one non-modifier key."""
    if not parts:
        return "hotkey has no keys"
    non_mods = [p for p in parts if p not in _HOTKEY_MODIFIERS]
    if len(non_mods) > 1:
        return f"hotkey must have exactly one non-modifier key (got {len(non_mods)})"
    return None


def _check_os_shell_combos(parts: list[str], platform: str, normalized_tokens: list[str]) -> str | None:
    """Stage 6: shell-key combos (Windows) and Cmd+<letter> (macOS).

    ``normalized_tokens`` carries the shell-alias-collapsed spelling, so
    ``<cmd>+e`` on Windows and ``<win>+e`` on macOS are caught even though
    each is spelled with the other platform's name.
    """
    has_shell = "super" in normalized_tokens
    if has_shell and platform == "win32":
        return "Windows key combinations are reserved by the OS shell"
    if has_shell and platform == "darwin" and len(parts) > 1:
        non_mods = [p for p in parts if p not in _HOTKEY_MODIFIERS]
        for nm in non_mods:
            if len(nm) == 1 and nm.isalpha():
                return f"Cmd+{nm.upper()} is reserved by macOS / common apps"
    return None


def _check_alt_shift(parts: list[str], platform: str) -> str | None:
    """Stage 7: Alt+Shift block (Windows language switching)."""
    if platform == "win32":
        non_mods = [p for p in parts if p not in _HOTKEY_MODIFIERS]
        has_alt = any(p.startswith("alt") for p in parts)
        has_shift = any(p.startswith("shift") for p in parts)
        if has_alt and has_shift and not non_mods:
            return "Alt+Shift is reserved by Windows for language switching"
    return None


def _check_ctrl_letter(parts: list[str]) -> str | None:
    """Stage 8: Ctrl+<common-letter> block (Copy/Paste/Undo/Save/etc.)."""
    has_ctrl = any(p.startswith("ctrl") for p in parts)
    if has_ctrl:
        non_mods = [p for p in parts if p not in _HOTKEY_MODIFIERS]
        modifiers_non_ctrl = [p for p in parts if p in _HOTKEY_MODIFIERS and not p.startswith("ctrl")]
        if not modifiers_non_ctrl:
            for nm in non_mods:
                if nm in _BLOCKED_CTRL_LETTERS:
                    return f"Ctrl+{nm.upper()} is a reserved application shortcut"
    return None


def _check_shift_letter(parts: list[str]) -> str | None:
    """Stage 9: Shift+<letter> block (interferes with capitalization)."""
    has_shift = any(p.startswith("shift") for p in parts)
    if has_shift:
        non_mods = [p for p in parts if p not in _HOTKEY_MODIFIERS]
        modifiers_non_shift = [p for p in parts if p in _HOTKEY_MODIFIERS and not p.startswith("shift")]
        if not modifiers_non_shift:
            for nm in non_mods:
                if len(nm) == 1 and (nm.isalpha() or nm.isdigit()):
                    return f"Shift+{nm.upper()} interferes with text capitalization or symbol input"
    return None


def _validate_hotkey(value: object) -> str | None:
    """Validate a hotkey string against the reserved-shortcut denylist.

    Returns ``None`` if valid, or a human-readable error string if invalid.
    """
    if (err := _check_basic_shape(value)) is not None:
        return err
    # `_check_basic_shape` already rejected non-strings above, but pyrefly
    if not isinstance(value, str):
        return f"must be a string, got {type(value).__name__}"

    parts = _parse_hotkey_parts(value)
    if not parts:
        return "hotkey has no keys"

    # Strip leading/trailing whitespace BEFORE lowercasing so a padded
    normalized = value.strip().lower()
    normalized_spec = _normalize_spec(value)
    normalized_tokens = normalized_spec.split("+") if normalized_spec else []

    # Stages run in priority order; the first rejection wins.
    for check in (
        lambda: _check_universal_reserved(normalized_spec),
        lambda: _check_platform_reserved(normalized_spec, _platform_key()),
        lambda: _check_single_alphanumeric(parts),
        lambda: _check_multi_non_modifier(parts),
        lambda: _check_modifier_order(normalized),
        lambda: _check_os_shell_combos(parts, _platform_key(), normalized_tokens),
        lambda: _check_alt_shift(parts, _platform_key()),
        lambda: _check_ctrl_letter(parts),
        lambda: _check_shift_letter(parts),
    ):
        if (err := check()) is not None:
            return err

    return None


__all__ = [
    # Reserved-shortcut table
    "_RESERVED_DATA_PATH",
    "_load_reserved_data",
    "_RESERVED_DATA",
    "_RESERVED_HOTKEYS",
    "_UNIVERSAL_RESERVED_HOTKEYS",
    "_BLOCKED_CTRL_LETTERS",
    "_HOTKEY_MODIFIERS",
    # Platform helpers
    "_platform_key",
    "_parse_hotkey_parts",
    "_tokenize_spec",
    "_normalize_spec",
    "_SHELL_ALIASES",
    # Stage helpers (9 stages)
    "_check_basic_shape",
    "_check_universal_reserved",
    "_check_platform_reserved",
    "_check_single_alphanumeric",
    "_check_multi_non_modifier",
    "_check_modifier_order",
    "_check_os_shell_combos",
    "_check_alt_shift",
    "_check_ctrl_letter",
    "_check_shift_letter",
    # Main validator
    "_validate_hotkey",
]
