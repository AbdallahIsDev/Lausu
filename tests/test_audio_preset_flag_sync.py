"""A loaded preset owns the legacy meter switch too (``noise_filter_enabled``).

``config/loader.py`` calls ``apply_preset`` on every load, but the flag was
written only by the config applier, so a config saved with ``audio_preset:
"off"`` still loaded with ``noise_filter_enabled: True`` and the meter built a
pass-through ``AudioProcessor`` — "preset off means no processor" silently
stopped being true (`update_level_processor` keys on that flag).
"""

from __future__ import annotations

from voice_typer.server.audio_presets import (
    PRESET_AUTO,
    PRESET_OFF,
    PRESET_STUDIO,
    apply_preset,
)
from voice_typer.server.config import Config
from voice_typer.server.config_applier_handlers import to_filter_dict


def test_loading_an_off_preset_leaves_no_meter_processor() -> None:
    cfg = Config()
    cfg.audio_preset = PRESET_OFF
    apply_preset(PRESET_OFF, cfg)  # exactly config/loader.py's load path

    assert cfg.noise_filter_enabled is False
    assert to_filter_dict(cfg)["noise_filter_enabled"] is False


def test_named_presets_keep_the_chain_enabled() -> None:
    cfg = Config()
    apply_preset(PRESET_AUTO, cfg)
    assert cfg.noise_filter_enabled is True

    apply_preset(PRESET_STUDIO, cfg)  # still a chain, just no denoiser
    assert cfg.noise_filter_enabled is True


def test_custom_keeps_the_individual_toggles_running() -> None:
    cfg = Config()
    cfg.noise_filter_enabled = False
    apply_preset("custom", cfg)

    assert cfg.noise_filter_enabled is True, (
        "custom means 'use the individual toggles', which need the chain"
    )


def test_off_preset_clears_the_live_meter_processor() -> None:
    from voice_typer.server.level_monitor import update_level_processor
    from voice_typer.server.level_monitor._state import _state as state

    cfg = Config()
    apply_preset(PRESET_OFF, cfg)
    try:
        update_level_processor(to_filter_dict(cfg))
        assert state._level_processor is None
    finally:
        state._level_processor = None
        state._level_processor_config = None
        state._level_processor_sample_rate = 0
