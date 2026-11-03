"""Level-monitor level queries + live level-processor configuration.

Read-only level accessors (``is_monitoring`` / ``get_level`` /
``get_level_diagnostics``) and ``update_level_processor``, the (re)builder of
the live level-bar audio processor. State lives in :mod:`._state`.

Extracted from ``monitoring.py``.
"""

from __future__ import annotations

import contextlib
import logging
import time
import types

from voice_typer.server.audio_filters.effective_backend import effective_noise_suppression

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


def _effective_label(processor: object) -> str:
    """Denoiser actually serving this chain, for log lines (C-UI-15)."""
    try:
        return str(effective_noise_suppression(processor)["effective"])
    except Exception:
        return "unknown"


def update_level_processor(config_dict: dict) -> None:
    """Create, converge, or bypass the audio processor behind the live meter."""
    try:
        new_config: dict | None = dict(config_dict)
    except Exception:
        new_config = None

    filter_enabled = bool(config_dict.get("noise_filter_enabled", True))

    # One page open reaches here 2-3x with the same effective config (post-restart
    # rebuild, service seed, filter-chain handler): rebuild + re-log on a real
    # transition only. The presence term keeps a FAILED construction retryable.
    with _state._monitor_lock:
        sample_rate = _state._monitor_sample_rate
        unchanged = (
            _state._level_processor_config == new_config
            and _state._level_processor_sample_rate == sample_rate
            and (_state._level_processor is not None) == filter_enabled
        )
        existing = _state._level_processor if unchanged else None
        if not unchanged:
            _state._level_processor_config = new_config
            _state._level_processor_sample_rate = sample_rate

    if unchanged:
        # Identical config, but the denoiser that is READY can change after the
        # chain was built (the DPDFNet preload lands seconds later, and the
        # gtcrn substitute otherwise pinned the session to it). Converge the
        # live chain in place rather than rebuilding another model.
        with contextlib.suppress(Exception):
            if existing is not None and existing.refresh_backends():
                log.info("[LEVEL-MON] Level processor backend promoted: effective=%s", _effective_label(existing))
        return

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
            "[LEVEL-MON] Level processor updated: highpass=%s, gate=%s, method=%s, effective=%s",
            config_dict.get("noise_filter_highpass", True),
            config_dict.get("noise_filter_gate", True),
            config_dict.get("noise_suppression_method", "rnnoise"),
            _effective_label(new_processor),
        )
    except Exception as exc:
        log.warning("[LEVEL-MON] Failed to create level processor: %s", exc)
        with _state._monitor_lock:
            _state._level_processor = None
