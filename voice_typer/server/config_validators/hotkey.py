"""Hotkey validators: reserved-shortcut table plus the delivery/alias contract.

The shared vocabulary lives in ``voice_typer/server/hotkey_reserved.json``;
this module loads it and exposes one ``(code, message)`` verdict so the
renderer can mirror the same decisions from the byte-identical copy.
"""

from __future__ import annotations

import json as _json
from pathlib import Path as _Path

from voice_typer.server.platform_utils import is_macos as _is_macos, is_windows as _is_windows

_RESERVED_DATA_PATH = _Path(__file__).resolve().parent.parent / "hotkey_reserved.json"


def _load_reserved_data() -> dict:
    """Load the reserved-hotkey JSON config (single source of truth)."""
    with _RESERVED_DATA_PATH.open("r", encoding="utf-8") as f:
        return _json.load(f)


_RESERVED_DATA = _load_reserved_data()

# Per-platform reserved shortcuts, compared after canonicalization.
_RESERVED_HOTKEYS: dict[str, set[str]] = {
    platform: set(entries) for platform, entries in _RESERVED_DATA["per_platform_reserved"].items()
}

# Universal window-management shortcuts blocked on EVERY platform.
_UNIVERSAL_RESERVED_HOTKEYS = frozenset(_RESERVED_DATA["universal_reserved"])

# Common Ctrl+<letter> shortcuts that are universally expected by users.
_BLOCKED_CTRL_LETTERS = frozenset(_RESERVED_DATA["blocked_ctrl_letters"])

# Modifier spellings recognized in a hotkey string (pynput-style, lowercase).
_HOTKEY_MODIFIERS = frozenset(_RESERVED_DATA["modifiers"])

# Non-modifier spellings and the per-platform delivery matrix.
_KEY_ALIASES: dict[str, str] = dict(_RESERVED_DATA["key_aliases"])
_KEY_VOCABULARY: dict[str, dict] = dict(_RESERVED_DATA["keys"])


def _platform_key() -> str:
    """Return the platform key for ``_RESERVED_HOTKEYS`` lookup."""
    if _is_windows():
        return "win32"
    if _is_macos():
        return "darwin"
    return "linux"


def _parse_hotkey_parts(hotkey: str) -> list[str]:
    """Parse a hotkey string into canonical ``[modifiers..., keys...]``."""
    from voice_typer.server.hotkey_spec import parse_hotkey

    spec = parse_hotkey(hotkey)
    if spec.is_empty:
        return []
    return list(spec.modifiers) + list(spec.keys)


def _tokenize_spec(value: str) -> list[str]:
    """Split a spec into lowercase bracket-free tokens, keeping order."""
    tokens: list[str] = []
    for raw in value.split("+"):
        token = raw.replace("<", "").replace(">", "").strip().lower()
        if token:
            tokens.append(token)
    return tokens


def _normalize_spec(value: str) -> str:
    """Canonical bracketed spec shared with the renderer and the parser.

    Alias spellings collapse first, so ``<cmd_l>``, ``<win>`` and ``<super>``
    cannot slip past a table written as ``<cmd>``, and a bare modifier keeps
    its canonical name.
    """
    from voice_typer.server.hotkey_spec import parse_hotkey

    return parse_hotkey(value).to_spec_string()


_UNIVERSAL_RESERVED_NORMALIZED: frozenset[str] = frozenset(
    _normalize_spec(entry) for entry in _UNIVERSAL_RESERVED_HOTKEYS
)
_RESERVED_NORMALIZED: dict[str, frozenset[str]] = {
    platform: frozenset(_normalize_spec(entry) for entry in entries) for platform, entries in _RESERVED_HOTKEYS.items()
}


def _check_basic_shape(value: object) -> tuple[str | None, str | None]:
    """Stage 1: type / length / emptiness guards."""
    if not isinstance(value, str):
        return "not_string", f"must be a string, got {type(value).__name__}"
    if len(value) > 256:
        return "too_long", "exceeds maximum length 256"
    if not value.strip():
        return "empty", "must not be empty"
    return None, None


def _check_universal_reserved(normalized: str) -> tuple[str | None, str | None]:
    """Stage 2: OS / common-app shortcuts blocked on EVERY platform."""
    if normalized in _UNIVERSAL_RESERVED_NORMALIZED:
        return "reserved_universal", "reserved, conflicts with operating system or common app shortcuts"
    return None, None


def _check_platform_reserved(normalized: str, platform: str) -> tuple[str | None, str | None]:
    """Stage 3: per-platform OS-reserved shortcuts."""
    if normalized in _RESERVED_NORMALIZED.get(platform, frozenset()):
        return "reserved_platform", f"reserved by operating system ({platform})"
    return None, None


def _check_modifier_order(value: str) -> tuple[str | None, str | None]:
    """Stage 4: a combo mixing keys and modifiers must END with the key."""
    tokens = _tokenize_spec(value)
    if len(tokens) < 2:
        return None, None
    non_mods = [t for t in tokens if t not in _HOTKEY_MODIFIERS]
    if non_mods and tokens[-1] in _HOTKEY_MODIFIERS:
        return (
            "modifier_order",
            f"a combo must end with its key, e.g. <ctrl>+<alt>+{non_mods[0]} (got {tokens[-1]} last)",
        )
    return None, None


def _check_single_alphanumeric(parts: list[str]) -> tuple[str | None, str | None]:
    """Stage 5: reject a standalone single letter/digit."""
    if len(parts) == 1:
        sole = parts[0]
        if len(sole) == 1 and sole.isalnum():
            return (
                "single_alnum",
                f"single letters and digits can't be used as hotkeys, '{sole}' would interfere with typing",
            )
    return None, None


def _check_multi_non_modifier(parts: list[str]) -> tuple[str | None, str | None]:
    """Stage 6: reject combos with MORE than one non-modifier key."""
    if not parts:
        return "no_keys", "hotkey has no keys"
    non_mods = [p for p in parts if p not in _HOTKEY_MODIFIERS]
    if len(non_mods) > 1:
        return "multiple_keys", f"hotkey must have exactly one non-modifier key (got {len(non_mods)})"
    return None, None


def _check_altgr(parts: list[str]) -> tuple[str | None, str | None]:
    """Stage 7: AltGr is reported as Alt by every listener, so it cannot match."""
    if "alt_gr" in parts:
        return (
            "altgr",
            "AltGr is reported as Alt by the keyboard listener, so an AltGr shortcut can't fire. Use Alt instead.",
        )
    return None, None


def _check_fn_platform(parts: list[str], platform: str) -> tuple[str | None, str | None]:
    """Stage 8: Fn/Globe is only reportable by the macOS event tap."""
    if "fn" in parts and platform != "darwin":
        return "fn_platform", "Fn is only available on macOS"
    return None, None


def _check_os_shell_combos(parts: list[str], platform: str) -> tuple[str | None, str | None]:
    """Stage 9: shell-key combos (Windows) and Cmd+<letter> (macOS)."""
    if "cmd" not in parts:
        return None, None
    if platform == "win32":
        return "shell_combo", "Windows key combinations are reserved by the OS shell"
    if platform == "darwin":
        for key in parts:
            if len(key) == 1 and key.isalpha():
                return "shell_combo", f"Cmd+{key.upper()} is reserved by macOS / common apps"
    return None, None


def _check_alt_shift(parts: list[str], platform: str) -> tuple[str | None, str | None]:
    """Stage 10: Alt+Shift block (Windows language switching)."""
    if platform == "win32" and "alt" in parts and "shift" in parts:
        non_mods = [p for p in parts if p not in _HOTKEY_MODIFIERS]
        if not non_mods:
            return "alt_shift", "Alt+Shift is reserved by Windows for language switching"
    return None, None


def _check_ctrl_letter(parts: list[str]) -> tuple[str | None, str | None]:
    """Stage 11: Ctrl+<common-letter> block (Copy/Paste/Undo/Save/etc.)."""
    if "ctrl" in parts:
        non_mods = [p for p in parts if p not in _HOTKEY_MODIFIERS]
        modifiers_non_ctrl = [p for p in parts if p in _HOTKEY_MODIFIERS and p != "ctrl"]
        if not modifiers_non_ctrl:
            for nm in non_mods:
                if nm in _BLOCKED_CTRL_LETTERS:
                    return "ctrl_letter", f"Ctrl+{nm.upper()} is a reserved application shortcut"
    return None, None


def _check_shift_letter(parts: list[str]) -> tuple[str | None, str | None]:
    """Stage 12: Shift+<letter> block (interferes with capitalization)."""
    if "shift" in parts:
        non_mods = [p for p in parts if p not in _HOTKEY_MODIFIERS]
        modifiers_non_shift = [p for p in parts if p in _HOTKEY_MODIFIERS and p != "shift"]
        if not modifiers_non_shift:
            for nm in non_mods:
                if len(nm) == 1 and (nm.isalpha() or nm.isdigit()):
                    return (
                        "shift_letter",
                        f"Shift+{nm.upper()} interferes with text capitalization or symbol input",
                    )
    return None, None


def _check_key_delivery(keys: list[str], platform: str) -> tuple[str | None, str | None]:
    """Stage 13: the current listener must actually deliver the key."""
    for key in keys:
        meta = _KEY_VOCABULARY.get(key)
        if meta is None:
            return "unknown_key", f"unknown key '{key}'"
        if platform not in meta["platforms"]:
            return "key_not_delivered", f"'{key}' is not delivered by the {platform} keyboard listener"
    return None, None


def _check_push_to_talk(value: object) -> tuple[str | None, str | None]:
    """Push-to-talk needs a key that reports a release after its press."""
    if not isinstance(value, str) or not value.strip():
        return None, None

    from voice_typer.server.hotkey_spec import parse_hotkey

    spec = parse_hotkey(value)
    if not spec.keys:
        return (
            "ptt_modifier_only",
            "Push-to-talk needs a key that reports a release; a modifier-only shortcut only works in toggle mode",
        )
    if "caps_lock" in spec.keys:
        return (
            "ptt_caps_lock",
            "Caps Lock can't be used for push-to-talk: macOS never reports its release",
        )
    return None, None


def _validate_hotkey_code(value: object) -> tuple[str | None, str | None]:
    """Return ``(error_code, message)``; both ``None`` means valid."""
    err = _check_basic_shape(value)
    if err[0] is not None:
        return err
    assert isinstance(value, str)

    parts = _parse_hotkey_parts(value)
    if not parts:
        return "no_keys", "hotkey has no keys"

    from voice_typer.server.hotkey_spec import parse_hotkey

    spec = parse_hotkey(value)
    normalized_spec = spec.to_spec_string()
    platform = _platform_key()

    for check in (
        lambda: _check_universal_reserved(normalized_spec),
        lambda: _check_platform_reserved(normalized_spec, platform),
        lambda: _check_modifier_order(value),
        lambda: _check_single_alphanumeric(parts),
        lambda: _check_multi_non_modifier(parts),
        lambda: _check_altgr(parts),
        lambda: _check_fn_platform(parts, platform),
        lambda: _check_os_shell_combos(parts, platform),
        lambda: _check_alt_shift(parts, platform),
        lambda: _check_ctrl_letter(parts),
        lambda: _check_shift_letter(parts),
        lambda: _check_key_delivery(list(spec.keys), platform),
    ):
        code, message = check()
        if code is not None:
            return code, message

    return None, None


def _validate_hotkey(value: object) -> str | None:
    """Validate a hotkey string; return ``None`` when valid, else a message."""
    return _validate_hotkey_code(value)[1]


__all__ = [
    "_RESERVED_DATA_PATH",
    "_load_reserved_data",
    "_RESERVED_DATA",
    "_RESERVED_HOTKEYS",
    "_UNIVERSAL_RESERVED_HOTKEYS",
    "_BLOCKED_CTRL_LETTERS",
    "_HOTKEY_MODIFIERS",
    "_KEY_ALIASES",
    "_KEY_VOCABULARY",
    "_platform_key",
    "_parse_hotkey_parts",
    "_tokenize_spec",
    "_normalize_spec",
    "_check_basic_shape",
    "_check_universal_reserved",
    "_check_platform_reserved",
    "_check_modifier_order",
    "_check_single_alphanumeric",
    "_check_multi_non_modifier",
    "_check_altgr",
    "_check_fn_platform",
    "_check_os_shell_combos",
    "_check_alt_shift",
    "_check_ctrl_letter",
    "_check_shift_letter",
    "_check_key_delivery",
    "_check_push_to_talk",
    "_validate_hotkey_code",
    "_validate_hotkey",
]
