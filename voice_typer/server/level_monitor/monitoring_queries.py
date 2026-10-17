"""Level-monitor level queries + live level-processor configuration.

Read-only level accessors (``is_monitoring`` / ``get_level`` /
``get_level_diagnostics``) and ``update_level_processor``, the (re)builder of
the live level-bar audio processor. State lives in :mod:`._state`.

Extracted from ``monitoring.py``.
"""

from __future__ import annotations

import logging
import time
import types

from ._state import _state

log = logging.getLogger("voice_typer.server.level_monitor")


def is_monitoring() -> bool:
    """Return True if the continuous level monitor is active.

    Returns:
    """
    with _state._monitor_lock:
        return _state._monitor_active


def get_level() -> dict:
    """Return the current audio level from the monitor.

    Returns:
    """
    # record the poll timestamp so the worker thread can detect
    _state._last_get_level_poll_ts = time.monotonic()
    with _state._monitor_lock:
        return {
            # Display gain: shared constant (see ``_state._LEVEL_DISPLAY_GAIN``)
            "level": min(1.0, _state._monitor_level * _state._LEVEL_DISPLAY_GAIN),
            "peak": _state._monitor_peak,
            "active": _state._monitor_active,
        }


def get_level_diagnostics() -> dict:
    """Return runtime diagnostics for the level monitor ().

    Returns:
    """
    # ``_dropped_level_chunks`` is incremented in the PortAudio callback
    from . import worker as _worker_mod

    return {
        "dropped_level_chunks": _state._dropped_level_chunks,
        "total_dropped_level_chunks": _worker_mod._total_dropped_level_chunks,
        "ring_buffer_capacity": _state._LEVEL_RING_BUFFER_CAPACITY,
        "ring_buffer_len": len(_state._level_ring_buffer),
        "monitor_active": _state._monitor_active,
    }


def update_level_processor(config_dict: dict) -> None:
    """Create or update the audio processor for the live level bar."""
    try:
        new_config: dict | None = dict(config_dict)
    except Exception:
        new_config = None

    # The worker reads this flag off _state to pick the filtered vs raw RMS path.
    # Default True: no producer writes the key (to_filter_dict never includes it);
    # the choke-point default makes the bar follow the preset without touching
    # the three seeding sites. Explicit False remains the escape hatch.
    level_bar_filtered = bool(config_dict.get("level_bar_filtered", True))
    filter_enabled = bool(config_dict.get("noise_filter_enabled", True))

    # One page open reaches here 2-3x with the same effective config (post-restart
    # rebuild, service seed, filter-chain handler): rebuild + re-log on a real
    # transition only. The presence term keeps a FAILED construction retryable.
    with _state._monitor_lock:
        sample_rate = _state._monitor_sample_rate
        if (
            _state._level_processor_config == new_config
            and _state._level_processor_sample_rate == sample_rate
            and _state._level_bar_filtered == level_bar_filtered
            and (_state._level_processor is not None) == filter_enabled
        ):
            return
        _state._level_processor_config = new_config
        _state._level_bar_filtered = level_bar_filtered
        _state._level_processor_sample_rate = sample_rate

    if not filter_enabled:
        with _state._monitor_lock:
            _state._level_processor = None
        # Not a failure: with the noise filter off the meter reads RAW RMS.
        log.debug("[LEVEL-MON] Level processor bypassed: raw meter (noise filter off)")
        return

    try:
        # ADR 0007: AudioProcessor takes a config-like object (anything
        from voice_typer.server.audio_processor import AudioProcessor

        # Construct the processor OUTSIDE the lock: ``AudioProcessor.__init__``
        ap_config = types.SimpleNamespace(**config_dict)
        new_processor = AudioProcessor(ap_config, sample_rate=sample_rate, quiet=True)

        # Assign under the lock so the worker's read of
        with _state._monitor_lock:
            _state._level_processor = new_processor

        log.info(
            "[LEVEL-MON] Level processor updated: highpass=%s, gate=%s, method=%s",
            config_dict.get("noise_filter_highpass", True),
            config_dict.get("noise_filter_gate", True),
            config_dict.get("noise_suppression_method", "rnnoise"),
        )
    except Exception as exc:
        log.warning("[LEVEL-MON] Failed to create level processor: %s", exc)
        with _state._monitor_lock:
            _state._level_processor = None
