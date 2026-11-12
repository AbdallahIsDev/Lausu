"""Push-to-talk recorder: taps the level monitor's single stream.

The app owns exactly ONE capture device (the level monitor's
``InputStream``); this class never opens a second stream. It arms a flag
and a dedicated deque; the level worker appends raw chunks under the same
lock as the mic-test buffer. The two states never share a buffer.
"""

from __future__ import annotations

import logging

import numpy as np

from voice_typer.server._audio_constants import WHISPER_SAMPLE_RATE
from voice_typer.server.level_monitor import is_monitoring, start_monitoring
from voice_typer.server.level_monitor._state import _state

log = logging.getLogger(__name__)


class ChatCapture:
    """Arms/disarms chat capture on the level monitor's stream."""

    def start(self, mic_id: str | None = None) -> int:
        """Start capturing; return the stream's sample rate."""
        if not is_monitoring():
            result = start_monitoring(mic_id)
            if not (isinstance(result, dict) and result.get("success")):
                raise RuntimeError("microphone monitoring could not start")
        with _state._monitor_lock:
            _state._chat_capture_chunks.clear()
            _state._chat_capture_cap_warned = False
            _state._chat_capture_active = True
            return int(_state._monitor_sample_rate)

    def stop(self) -> np.ndarray:
        """Stop capturing; return mono float32 at ``WHISPER_SAMPLE_RATE``."""
        with _state._monitor_lock:
            _state._chat_capture_active = False
            sample_rate = int(_state._monitor_sample_rate)
            raw_chunks = [np.array(c, copy=True) for c in _state._chat_capture_chunks]
            _state._chat_capture_chunks.clear()
            _state._chat_capture_cap_warned = False
        if not raw_chunks:
            return np.empty(0, dtype=np.float32)
        audio = np.concatenate(raw_chunks, axis=0).reshape(-1).astype(np.float32)
        if sample_rate != WHISPER_SAMPLE_RATE:
            from voice_typer.server.recording.resampling import resample_audio

            audio = resample_audio(audio, sample_rate, WHISPER_SAMPLE_RATE)
        return np.ascontiguousarray(audio, dtype=np.float32)

    def cancel(self) -> None:
        """Drop any in-progress capture without decoding it."""
        with _state._monitor_lock:
            _state._chat_capture_active = False
            _state._chat_capture_chunks.clear()
            _state._chat_capture_cap_warned = False


__all__ = ["ChatCapture"]
