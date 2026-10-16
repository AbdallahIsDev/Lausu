"""Streaming polyphase resampler used by the neural noise suppressors.

Owns the streaming resampler and its FIR tap-count / group-delay helpers.
Extracted from ``noise_suppressor.py`` so the suppressor module keeps only
backend selection + frame processing.
"""

from __future__ import annotations

import math

from voice_typer.server._lazy_import import lazy_module

np = lazy_module("numpy")


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
    """Streaming polyphase resampler ( / ).

    True polyphase form: the FIR is split into ``up`` phase banks and
    each output samples ONLY its bank (``taps / up`` MACs). The naive
    dense form (zero-stuff, full ``lfilter``, decimate) computes
    ``down - 1`` of every ``down`` filtered samples only to discard
    them -- ~440x wasted work at 44.1 kHz -> 16 kHz -- and a reused
    zero-stuff working buffer leaks stale input across chunks. Both
    are fixed here by construction: no upsample buffer exists, and
    per-output cost is ``len(bank)`` MACs in float32.
    """

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
        h64 = np.asarray(firwin(num_taps, cutoff, fs=2.0), dtype=np.float64)
        self._h = h64.astype(np.float32)

        # Polyphase banks: bank[p] holds every up-th tap starting at p.
        # Output sample at upsampled index m uses bank[m % up] dotted
        # against the input window ending at input sample (m - m%up)/up.
        self._banks: list[np.ndarray] = [
            np.ascontiguousarray(self._h[p :: self._up]) for p in range(self._up)
        ]
        self._max_bank_len: int = max(len(b) for b in self._banks)

        # Input history tail (zero-initial = zero filter state, same as
        # the old lfilter zi=0). Length covers the longest bank window.
        self._hist_len: int = self._max_bank_len
        self._hist: np.ndarray | None = None

        # Counters and phase for the output-length invariant () and for
        self._in_total: int = 0
        self._out_total: int = 0
        self._phase: int = 0

    def process(self, x: np.ndarray) -> np.ndarray:
        """Resample ``x`` (float32/float64) by ``up / down``."""
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)

        x32 = np.ascontiguousarray(x, dtype=np.float32).reshape(-1)
        n_in = x32.size
        up = self._up
        down = self._down

        # Output upsampled positions, same count contract as before:
        # every down-th position starting at the carried phase.
        m_total = n_in * up
        count = (m_total - self._phase + down - 1) // down if m_total > self._phase else 0
        out = np.empty(count, dtype=np.float32)

        hist = self._hist
        if hist is None:
            hist = np.zeros(self._hist_len, dtype=np.float32)
        ext = np.concatenate([hist, x32])
        base = hist.size  # ext index of x32[0]

        for j in range(count):
            m = self._phase + j * down
            bank = self._banks[m % up]
            s = (m - (m % up)) // up + base
            lo = s - len(bank) + 1
            out[j] = float(np.dot(bank, ext[lo : s + 1]))

        # Carry the tail forward for the next chunk.
        tail = ext[-self._hist_len :] if ext.size >= self._hist_len else ext
        if tail.size < self._hist_len:
            pad = np.zeros(self._hist_len - tail.size, dtype=np.float32)
            tail = np.concatenate([pad, tail])
        self._hist = np.ascontiguousarray(tail)

        # Advance phase: the next chunk's first output sits at the next
        # grid point at or after this chunk's end. Grid points are global
        # (0, down, 2*down, ...), so with this chunk spanning m_total
        # upsampled samples the offset is (phase - m_total) mod down.
        # (The old dense form used (phase + m_total) mod down, which
        # lands off-grid whenever m_total % down != 0 and drifts one
        # sample per chunk -- invisible at down=1, which is all the old
        # tests exercised.)
        self._phase = (self._phase - m_total) % down

        self._in_total += n_in
        self._out_total += count
        return out

    def reset(self) -> None:
        """Clear all internal state (history tail, phase, counters)."""
        if self._hist is not None:
            self._hist.fill(0)
        self._in_total = 0
        self._out_total = 0
        self._phase = 0
