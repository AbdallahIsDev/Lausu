"""Streaming polyphase resampler used by the neural noise suppressors.

Owns the streaming resampler and its FIR tap-count / group-delay helpers.
Extracted from ``noise_suppressor.py`` so the suppressor module keeps only
backend selection + frame processing.
"""

from __future__ import annotations

import math

from voice_typer.server._lazy_import import lazy_module

np = lazy_module("numpy")
from voice_typer.server.audio_filters.base import _get_lfilter  # noqa: E402


def _resampler_fir_num_taps(up: int, down: int) -> int:
    """FIR length used by :class:`_StreamingResampler` for an ``up``/``down`` ratio."""
    rate_gcd = math.gcd(up, down)
    up_reduced = up // rate_gcd
    down_reduced = down // rate_gcd
    taps = 10 * max(up_reduced, down_reduced) + 1
    if taps % 2 == 0:
        taps += 1
    return taps


def _resampler_group_delay_ms(up: int, down: int, input_rate: int) -> float:
    """Group delay (ms) of one :class:`_StreamingResampler` FIR stage."""
    delay_samples = (_resampler_fir_num_taps(up, down) - 1) / 2
    intermediate_rate = input_rate * up
    return delay_samples / intermediate_rate * 1000.0


class _StreamingResampler:
    """Streaming polyphase resampler ( / )."""

    def __init__(self, up: int, down: int) -> None:
        if up <= 0:
            raise ValueError(f"up must be > 0, got {up!r}")
        if down <= 0:
            raise ValueError(f"down must be > 0, got {down!r}")
        self._up = int(up)
        self._down = int(down)

        # Design the FIR filter ONCE at construction (). Cutoff is the
        from scipy.signal import firwin

        rate_gcd = math.gcd(self._up, self._down)
        up_reduced = self._up // rate_gcd
        down_reduced = self._down // rate_gcd
        cutoff = 1.0 / max(up_reduced, down_reduced)
        num_taps = _resampler_fir_num_taps(self._up, self._down)
        self._h = np.asarray(firwin(num_taps, cutoff, fs=2.0), dtype=np.float64)

        # Persistent lfilter state (len = len(h) - 1 for an FIR filter).
        self._zi: np.ndarray = np.zeros(max(len(self._h) - 1, 0), dtype=np.float64)

        # Counters and phase for the output-length invariant () and for
        self._in_total: int = 0
        self._out_total: int = 0
        self._phase: int = 0
        # pre-allocated upsample buffer (zero-filled, reused across
        self._x_up_buf: np.ndarray | None = None

    def process(self, x: np.ndarray) -> np.ndarray:
        """Resample ``x`` (float32/float64) by ``up / down``."""
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)

        x64 = np.asarray(x, dtype=np.float64)
        n_in = x64.size
        up = self._up
        down = self._down

        # Upsample: insert up-1 zeros between samples.
        up_len = n_in * up
        if self._x_up_buf is None or self._x_up_buf.shape[0] < up_len:
            self._x_up_buf = np.zeros(max(up_len, 1024), dtype=np.float64)
        x_up = self._x_up_buf[:up_len]
        # Only the stride slots are ever written (``x_up[::up] = x64``);
        x_up[::up] = x64

        # Apply FIR filter with persistent state.
        y, self._zi = _get_lfilter()(self._h, [1.0], x_up, zi=self._zi)

        # Downsample: pick every `down`-th sample starting at current phase.
        m = y.size  # == n_in * up
        idx = np.arange(self._phase, m, down)
        out = y[idx]

        # Advance phase: the next chunk's first downsample sample is offset by
        self._phase = (self._phase + m) % down

        self._in_total += n_in
        self._out_total += out.size
        return out.astype(np.float32, copy=False)

    def reset(self) -> None:
        """Clear all internal state (zeros ``_zi`` in place)."""
        #  (mirrored from NoiseSuppressor.reset): zero the existing
        if self._zi.size > 0:
            self._zi.fill(0)
        self._in_total = 0
        self._out_total = 0
        self._phase = 0
        # Zero the pre-allocated upsample working buffer so the
        if self._x_up_buf is not None:
            self._x_up_buf.fill(0)
