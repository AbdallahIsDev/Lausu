"""User-saved microphone presets (custom_presets + active_custom_preset)."""

from __future__ import annotations

import types


def _ctx(config, updates):
    from voice_typer.server.config_applier_handlers import SideEffectContext

    return SideEffectContext(
        app=object(),
        config=config,
        updates=updates,
        status={},
    )


def test_schema_defaults():
    from voice_typer.server.config import Config

    cfg = Config()
    assert cfg.custom_presets == []
    assert cfg.active_custom_preset is None


def test_validator_accepts_wellformed():
    from voice_typer.server.config_validators import _make_custom_presets_validator

    validate = _make_custom_presets_validator()
    assert (
        validate(
            [
                {"id": "late-night", "name": "Late Night", "values": {"noise_filter_gate": True}},
                {"id": "x", "name": "X", "values": {}},
            ]
        )
        is None
    )


def test_validator_rejects_shapes():
    from voice_typer.server.config_validators import _make_custom_presets_validator

    validate = _make_custom_presets_validator()
    assert validate("nope") is not None
    assert validate([{"id": "a", "name": "A", "values": {"nope_key": True}}]) is not None
    assert validate([{"id": "a", "name": "", "values": {}}]) is not None
    assert validate(
        [
            {"id": "a", "name": "A", "values": {}},
            {"id": "a", "name": "B", "values": {}},
        ]
    ) is not None
    assert validate([{"id": "a", "name": "A", "values": {"noise_filter_gate": "yes"}}]) is not None
    assert validate([{"id": "ok", "name": "Ok", "values": {}}] * 33) is not None


def test_allowlist_has_new_keys():
    from voice_typer.server.config_validators import IPC_CONFIG_ALLOWLIST

    assert "custom_presets" in IPC_CONFIG_ALLOWLIST
    assert "active_custom_preset" in IPC_CONFIG_ALLOWLIST


def test_handler_applies_matching_custom_snapshot():
    from voice_typer.server.config_applier_handlers import _AudioPresetHandler

    config = types.SimpleNamespace(
        active_custom_preset="night",
        custom_presets=[
            {"id": "night", "name": "Night", "values": {"noise_filter_gate": False}},
        ],
        noise_filter_gate=True,
        noise_filter_enabled=True,
    )
    _AudioPresetHandler().apply(_ctx(config, {"audio_preset": "custom"}))
    assert config.noise_filter_gate is False


def test_handler_unknown_custom_id_is_noop():
    from voice_typer.server.config_applier_handlers import _AudioPresetHandler

    config = types.SimpleNamespace(
        active_custom_preset="ghost",
        custom_presets=[],
        noise_filter_gate=True,
    )
    _AudioPresetHandler().apply(_ctx(config, {"audio_preset": "custom"}))
    assert config.noise_filter_gate is True


def test_handler_stock_preset_unchanged():
    from voice_typer.server.config_applier_handlers import _AudioPresetHandler

    config = types.SimpleNamespace(
        active_custom_preset=None,
        custom_presets=[],
        noise_filter_gate=False,
        noise_filter_enabled=True,
    )
    _AudioPresetHandler().apply(_ctx(config, {"audio_preset": "studio"}))
    assert config.noise_filter_gate is False
