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
    # Stash the config_dict BEFORE the early-return disable path so the
    try:
        _state._level_processor_config = dict(config_dict)
    except Exception:
        _state._level_processor_config = None

    # Stash the ``level_bar_filtered`` flag on _state so the worker can
    level_bar_filtered = bool(config_dict.get("level_bar_filtered", False))
    with _state._monitor_lock:
        _state._level_bar_filtered = level_bar_filtered

    if not config_dict.get("noise_filter_enabled", True):
        with _state._monitor_lock:
            _state._level_processor = None
        log.debug("[LEVEL-MON] Level processor disabled")
        return

    try:
        # ADR 0007: AudioProcessor takes a config-like object (anything
        from voice_typer.server.audio_processor import AudioProcessor

        # Snapshot the current monitor sample rate under the lock so
        with _state._monitor_lock:
            sample_rate = _state._monitor_sample_rate

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

