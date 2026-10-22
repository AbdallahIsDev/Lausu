"""Canonical hotkey spec parser, the single source of truth."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_RESERVED_DATA_PATH = Path(__file__).resolve().parent / "hotkey_reserved.json"
_RESERVED_DATA = json.loads(_RESERVED_DATA_PATH.read_text(encoding="utf-8"))


def _canonical_modifier(alias: str) -> str:
    """Collapse an alias spelling; L/R and shell names are indistinguishable on the wire."""
    base = alias[:-2] if alias.endswith(("_l", "_r")) else alias
    if base == "control":
        return "ctrl"
    if base in ("altgr", "alt_gr", "right_alt", "ralt"):
        return "alt_gr"
    if base == "globe":
        return "fn"
    if base in ("win", "super", "cmd"):
        return "cmd"
    if base == "option":
        return "alt"
    return base


MODIFIER_ALIASES: dict[str, str] = {alias: _canonical_modifier(alias) for alias in _RESERVED_DATA["modifiers"]}
KEY_ALIASES: dict[str, str] = dict(_RESERVED_DATA["key_aliases"])


@dataclass(frozen=True)
class HotkeySpec:
    """Parsed hotkey specification."""

    modifiers: tuple[str, ...]
    keys: tuple[str, ...]
    is_modifier_only: bool
    is_empty: bool

    @property
    def main_key(self) -> str | None:
        """First non-modifier key, or ``None`` if there are none."""
        return self.keys[0] if self.keys else None

    def to_spec_string(self) -> str:
        """Convert back to pynput-style string: ``'<ctrl>+<alt>+v'``."""
        parts = [f"<{m}>" for m in self.modifiers] + [f"<{k}>" for k in self.keys]
        return "+".join(parts)


def parse_hotkey(spec: str) -> HotkeySpec:
    """Parse a pynput-style hotkey string into a :class:`HotkeySpec`."""
    if not spec:
        return HotkeySpec(modifiers=(), keys=(), is_modifier_only=False, is_empty=True)

    parts: list[str] = []
    for raw in spec.split("+"):
        part = raw.replace("<", "").replace(">", "").strip().lower()
        if part:
            parts.append(part)

    if not parts:
        return HotkeySpec(modifiers=(), keys=(), is_modifier_only=False, is_empty=True)

    modifiers: list[str] = []
    keys: list[str] = []
    for part in parts:
        if part in MODIFIER_ALIASES:
            mod = MODIFIER_ALIASES[part]
            if mod not in modifiers:
                modifiers.append(mod)
        else:
            key = KEY_ALIASES.get(part, part)
            if key not in keys:
                keys.append(key)

    # Sort modifiers for deterministic comparison (so ``<alt>+<ctrl>``
    modifiers.sort()

    return HotkeySpec(
        modifiers=tuple(modifiers),
        keys=tuple(keys),
        is_modifier_only=len(keys) == 0 and len(modifiers) > 0,
        is_empty=False,
    )


__all__ = [
    "KEY_ALIASES",
    "MODIFIER_ALIASES",
    "HotkeySpec",
    "parse_hotkey",
]
