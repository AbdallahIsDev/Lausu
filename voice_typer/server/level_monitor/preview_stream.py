"""Filtered live-preview audio frames (Listen Live through the sidecar chain).

The preview reuses the level monitor's capture stream and its
``AudioProcessor`` (the SAME chain the 10 s test and the meter run, E7): the
level worker already has the post-chain samples in hand, so a preview frame is
a copy of that buffer, never a second capture path or a second filter chain.

Wire shape: one push event per audio chunk,
``{"type": "live_preview_audio", "data": {pcm, sample_rate, seq}}`` where
``pcm`` is base64 PCM16 little-endian mono. One chunk is one frame (a few
KiB), so the 3-byte base64 slicing rules for multi-chunk transfers never
apply here (C-MIC-21).
"""

from __future__ import annotations

import base64
import logging

import numpy as np

from ._state import _state

log = logging.getLogger("voice_typer.server.level_monitor")

PREVIEW_EVENT_TYPE = "live_preview_audio"

# PCM16 full scale: float samples are clamped to [-1, 1] before scaling.
_PCM16_SCALE = 32767.0


def set_live_preview_enabled(enabled: bool) -> dict[str, object]:
    """Turn the preview stream on/off; report what the caller can expect.

    Enabling requires an active monitor stream: the preview has no capture
    path of its own (C-MIC-10), so without the monitor there is nothing to
    filter. The reply is the honest state, never an optimistic one.
    """
    with _state._monitor_lock:
        monitoring = _state._monitor_active
        active = bool(enabled) and monitoring
        _state._live_preview_active = active
        _state._live_preview_seq = 0
        return {
            "active": active,
            "monitoring": monitoring,
            "sample_rate": int(_state._monitor_sample_rate),
            "filtered": _state._level_processor is not None,
        }


def is_live_preview_active() -> bool:
    """True while the renderer is playing the backend preview."""
    with _state._monitor_lock:
        return _state._live_preview_active


def clear_live_preview() -> None:
    """Stop pushing frames (monitor stop / shutdown). Idempotent."""
    with _state._monitor_lock:
        _state._live_preview_active = False
        _state._live_preview_seq = 0


def publish_preview_frame(samples: np.ndarray, sample_rate: int) -> None:
    """Push one filtered chunk to the renderer.

    Called from the level worker with the post-chain buffer, OUTSIDE the
    monitor lock. ``samples`` is float32 mono in [-1, 1]; a closed gate
    legitimately yields exact zeros, which is what the user asked for.
    """
    if samples.size == 0:
        return
    with _state._monitor_lock:
        if not _state._live_preview_active:
            return
        _state._live_preview_seq += 1
        seq = _state._live_preview_seq

    pcm = np.clip(samples, -1.0, 1.0)
    pcm16 = (pcm * _PCM16_SCALE).astype("<i2", copy=False)
    payload = base64.b64encode(pcm16.tobytes()).decode("ascii")

    try:
        from voice_typer.server import event_bus

        event_bus.publish(
            {
                "type": PREVIEW_EVENT_TYPE,
                "data": {
                    "pcm": payload,
                    "sample_rate": int(sample_rate),
                    "seq": seq,
                },
            },
        )
    except Exception:
        log.debug("[LEVEL-MON] live preview frame publish failed", exc_info=True)
