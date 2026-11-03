"""Parity between the custom-theme tokens the renderer writes and the SEC-002 validator.

The renderer's ``CUSTOM_COLOR_KEYS`` (``themes.ts``) writes the consolidated
token names (``--surface-subtle`` / ``--muted-foreground``). The validator used
to require only the pre-consolidation aliases (``--bg-subtle`` /
``--text-muted``), so every custom-theme save was rejected with
``field 'custom_theme' light.--text-muted must be a string, got NoneType``.
Both shapes must validate; the renderer's shape is the canonical one.
"""

from __future__ import annotations

import re
from pathlib import Path

from voice_typer.server.config_validators.scalar import (
    CUSTOM_THEME_COLOR_SLOTS,
    _make_custom_theme_validator,
)

_THEMES_TS = (
    Path(__file__).resolve().parent.parent / "voice_typer" / "client" / "src" / "renderer" / "src" / "themes.ts"
)

# The exact payload the renderer builds today (DEFAULT_CUSTOM_LIGHT values).
_RENDERER_LIGHT = {
    "--background": "#ffffff",
    "--foreground": "#09090b",
    "--primary": "#1447e6",
    "--surface-subtle": "#f5f5f5",
    "--border": "#e4e4e7",
    "--muted-foreground": "#71717b",
}
_RENDERER_DARK = {
    "--background": "#131313",
    "--foreground": "#fafafa",
    "--primary": "#193cb8",
    "--surface-subtle": "#0f0f0f",
    "--border": "#1f1f1f",
    "--muted-foreground": "#9f9fa9",
}
# Pre-consolidation names, still present in older config.json files.
_LEGACY_ALIASES = {"--bg-subtle": "#f0f0f0", "--text-muted": "#666666"}


def _renderer_color_keys() -> list[str]:
    """Extract the ``var: "--token"`` entries of ``CUSTOM_COLOR_KEYS``."""
    source = _THEMES_TS.read_text(encoding="utf-8")
    start = source.index("export const CUSTOM_COLOR_KEYS")
    end = source.index("// ─── Default values for each custom colour key", start)
    return re.findall(r'var: "(--[a-z0-9-]+)"', source[start:end])


def _legacy_payload() -> dict[str, dict[str, str]]:
    mode = {k: v for k, v in _RENDERER_LIGHT.items() if k not in ("--surface-subtle", "--muted-foreground")}
    mode.update(_LEGACY_ALIASES)
    return {"light": dict(mode), "dark": dict(mode)}


class TestRendererTokenParity:
    def test_renderer_keys_are_exactly_the_validator_slots(self) -> None:
        assert sorted(_renderer_color_keys()) == sorted(slot[0] for slot in CUSTOM_THEME_COLOR_SLOTS), (
            "themes.ts CUSTOM_COLOR_KEYS and CUSTOM_THEME_COLOR_SLOTS drifted: "
            "a key one side writes and the other does not require rejects every save"
        )

    def test_renderer_payload_validates(self) -> None:
        validator = _make_custom_theme_validator()
        assert validator({"light": dict(_RENDERER_LIGHT), "dark": dict(_RENDERER_DARK)}) is None


class TestLegacyAliasesStillValidate:
    def test_legacy_only_payload_validates(self) -> None:
        assert _make_custom_theme_validator()(_legacy_payload()) is None

    def test_mixed_current_and_legacy_payload_validates(self) -> None:
        theme = {"light": {**_RENDERER_LIGHT, "--text-muted": "#666666"}, "dark": dict(_RENDERER_DARK)}
        assert _make_custom_theme_validator()(theme) is None


class TestMissingSlotIsDiagnosed:
    def test_missing_slot_names_the_canonical_token(self) -> None:
        light = {k: v for k, v in _RENDERER_LIGHT.items() if k != "--muted-foreground"}
        err = _make_custom_theme_validator()({"light": light, "dark": dict(_RENDERER_DARK)})
        assert err is not None
        assert "--muted-foreground" in err, f"missing slot must be named by its canonical token, got: {err!r}"
        assert "NoneType" in err

    def test_null_value_is_rejected(self) -> None:
        light = {**_RENDERER_LIGHT, "--border": None}
        err = _make_custom_theme_validator()({"light": light, "dark": dict(_RENDERER_DARK)})
        assert err is not None
        assert "--border" in err
        assert "NoneType" in err

    def test_non_hex_value_is_rejected(self) -> None:
        light = {**_RENDERER_LIGHT, "--primary": "blue"}
        err = _make_custom_theme_validator()({"light": light, "dark": dict(_RENDERER_DARK)})
        assert err is not None
        assert "hex colour" in err
