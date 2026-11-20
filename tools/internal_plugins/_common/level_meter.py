"""Measured microphone levels for browser-owned dictations.

The browser owns the recording, so no PCM reaches the bubble on its own. A
single hardcoded level rendered as a frozen waveform pinned high. This meter
opens a small meter-only capture and forwards RMS/peak into the app's existing
waveform coordinator, so the same smoothing and ``bubble_level`` push path the
local model uses drives the pill. Both internal STT plugins share it so the
fix cannot land in one copy and drift from the other.

Best effort by contract: a device that refuses a second open degrades to "no
levels" (the bars settle at rest) and logs ONE warning - never a fake level,
never a broken dictation.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

log = logging.getLogger("voice_typer.internal_plugin.level_meter")


def compute_levels(samples: Any) -> tuple[float, float]:
    """RMS and peak of a captured block, in that order."""
    import numpy as np

    return (
        float(np.sqrt(np.mean(np.square(samples)))),
        float(np.max(np.abs(samples))),
    )


def _meter_device(app: Any) -> int | None:
    """Device index for the meter: the user's selection, else the OS default."""
    try:
        from voice_typer.server.server_platform.microphone_list import (
            resolve_mic_id_to_device_index,
        )

        mic_id = getattr(app.config, "microphone", None)
        if mic_id:
            return resolve_mic_id_to_device_index(mic_id)
    except Exception:
        log.debug("[PLUGIN] mic-id resolution failed, using the system default", exc_info=True)
    return None


class LevelMeter:
    """Captures short audio blocks while a plugin session is recording."""

    RATE = 16000
    BLOCK = 800  # 50 ms

    def __init__(self, app: Any) -> None:
        self._app = app
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        # Daemon: metering is best-effort and must never hold process exit.
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="plugin-level-meter"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        import sounddevice as sd

        warned = False

        def _warn_once(msg: str) -> None:
            nonlocal warned
            if not warned:
                warned = True
                log.warning("[PLUGIN] %s", msg)

        try:
            device = _meter_device(self._app)
            stream = sd.InputStream(
                samplerate=self.RATE,
                blocksize=self.BLOCK,
                channels=1,
                dtype="float32",
                device=device,
            )
            stream.start()
        except Exception as exc:
            _warn_once(f"bubble level meter unavailable ({exc}); the waveform stays at rest")
            return
        if not warned:
            log.debug("[PLUGIN] bubble level meter started (device=%s)", device)
        try:
            while not self._stop.is_set():
                try:
                    block, overflowed = stream.read(self.BLOCK)
                except Exception as exc:
                    _warn_once(f"bubble level meter stopped reading ({exc})")
                    break
                samples = block[:, 0] if getattr(block, "ndim", 1) > 1 else block
                try:
                    rms, peak = compute_levels(samples)
                except Exception:
                    continue
                bubble = getattr(self._app, "_waveform_bubble", None)
                if bubble is not None:
                    try:
                        bubble.update_level(rms, peak)
                    except Exception:
                        log.debug("[PLUGIN] level push failed", exc_info=True)
                if overflowed:
                    log.debug("[PLUGIN] level meter input overflow (dropped samples)")
        finally:
            try:
                stream.stop()
                stream.close()
            except Exception:
                log.debug("[PLUGIN] level meter close failed", exc_info=True)
