"""Microphone quality preset definitions."""

from __future__ import annotations

from typing import Any

# Preset name constants
PRESET_AUTO = "auto"
PRESET_STUDIO = "studio"
PRESET_NOISY_ROOM = "noisy_room"
PRESET_OFF = "off"
PRESET_CUSTOM = "custom"

# Preset → filter settings + optional per-preset parameter overrides.
#
# ``auto`` and ``noisy_room`` are deliberately SHORT: high-pass +
# one neural suppressor + the brick-wall limiter. Every extra stage moves
# the transcript further from "what the microphone heard", and the measured
# failures (docs/microphone-filter-failures.md §1.1, §1.6) came from the
# gate/EQ/compressor shaping a healthy signal. The gate and the compressor
# remain available per-field under ``custom``.
PRESETS: dict[str, dict[str, Any]] = {
    PRESET_AUTO: {
        "noise_filter_highpass": True,
        "noise_suppression_method": "dpdfnet",
        "noise_filter_gate": False,
        "noise_filter_eq": False,
        "noise_filter_compressor": False,
        "noise_filter_limiter": True,
        "noise_filter_notch": False,
    },
    PRESET_STUDIO: {
        "noise_filter_highpass": True,
        "noise_suppression_method": "none",  # quiet room, good mic
        "noise_filter_gate": False,
        "noise_filter_eq": True,
        "noise_filter_compressor": True,
        "noise_filter_limiter": True,
        "noise_filter_notch": False,
    },
    PRESET_NOISY_ROOM: {
        "noise_filter_highpass": True,
        "noise_suppression_method": "dpdfnet",
        "noise_filter_gate": False,
        "noise_filter_eq": False,
        "noise_filter_compressor": False,
        "noise_filter_limiter": True,
        "noise_filter_notch": True,
        "noise_filter_highpass_cutoff_hz": 100.0,  # default 80; strip HVAC rumble
    },
    PRESET_OFF: {
        "noise_filter_highpass": False,
        "noise_suppression_method": "none",
        "noise_filter_gate": False,
        "noise_filter_eq": False,
        "noise_filter_compressor": False,
        "noise_filter_limiter": False,
        "noise_filter_notch": False,
    },
    # PRESET_CUSTOM is not in this dict, it means "use individual field values"
}


def apply_preset(preset: str, config: Any) -> None:
    """Apply a named preset to a config object in-place."""
    # The legacy flag is the meter/test chain's on/off switch
    # (``update_level_processor``). The config applier used to be its only
    # writer, so a config LOADED with ``audio_preset: "off"`` kept the flag True
    # and built a pass-through processor. One writer, both paths.
    if preset == PRESET_CUSTOM:
        # Custom keeps the individual toggles, which need the chain running.
        config.noise_filter_enabled = True
        return
    if preset not in PRESETS:
        return
    for key, value in PRESETS[preset].items():
        setattr(config, key, value)
    config.noise_filter_enabled = preset != PRESET_OFF


def get_preset_filters(preset: str) -> dict[str, Any]:
    """Return the filter settings for a named preset.

    Returns an empty dict for "custom" (no automatic changes).
    """
    return dict(PRESETS.get(preset, {}))
