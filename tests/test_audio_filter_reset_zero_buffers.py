"""Regression tests: audio filter reset() must zero pre-allocated working buffers."""

from __future__ import annotations

import numpy as np
from voice_typer.server.audio_filters.compressor import Compressor
from voice_typer.server.audio_filters.equalizer import Equalizer
from voice_typer.server.audio_filters.limiter import Limiter
from voice_typer.server.audio_filters.noise_suppressor import (
    NoiseSuppressor,
    _StreamingResampler,
)

_SR = 16000


def _nonzero_chunk(n: int = 1024) -> np.ndarray:
    """Return a non-zero float32 audio chunk (0.5 amplitude 440 Hz sine)."""
    t = np.linspace(0, n / _SR, n, endpoint=False)
    return (0.5 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32)


def test_compressor_reset_zeros_env_db_buf():
    c = Compressor(sample_rate=_SR)
    c.process(_nonzero_chunk(), _SR)
    assert c._env_db_buf is not None
    assert not np.all(c._env_db_buf == 0)
    c.reset()
    assert c._env_db_buf is not None
    assert np.all(c._env_db_buf == 0)


def test_compressor_reset_before_process_does_not_crash():
    """reset() before the lazy buffer is allocated must not crash (buf is None)."""
    c = Compressor(sample_rate=_SR)
    assert c._env_db_buf is None
    c.reset()  # no-op on the None buffer
    assert c._env_db_buf is None


def test_limiter_reset_zeros_env_db_buf():
    lim = Limiter(sample_rate=_SR)
    lim.process(_nonzero_chunk(), _SR)
    assert lim._env_db_buf is not None
    assert not np.all(lim._env_db_buf == 0)
    lim.reset()
    assert lim._env_db_buf is not None
    assert np.all(lim._env_db_buf == 0)


def test_limiter_reset_before_process_does_not_crash():
    lim = Limiter(sample_rate=_SR)
    assert lim._env_db_buf is None
    lim.reset()
    assert lim._env_db_buf is None


def test_equalizer_reset_zeros_delay_buf():
    eq = Equalizer(sample_rate=_SR)
    eq.process(_nonzero_chunk(), _SR)
    assert eq._delay_buf is not None
    assert not np.all(eq._delay_buf == 0)
    eq.reset()
    assert eq._delay_buf is not None
    assert np.all(eq._delay_buf == 0)


def test_equalizer_reset_before_process_does_not_crash():
    eq = Equalizer(sample_rate=_SR)
    assert eq._delay_buf is None
    eq.reset()
    assert eq._delay_buf is None


def test_noise_suppressor_reset_zeros_frame_buffers():
    """reset() must zero _frame_f32_buf and _frame_i16_buf."""
    ns = NoiseSuppressor(method="rnnoise", sample_rate=_SR)
    ns.process(_nonzero_chunk(), _SR)
    # Ensure the buffers are non-zero before reset -- either process()
    ns._frame_f32_buf[:] = 0.5
    ns._frame_i16_buf[:] = 12345
    assert not np.all(ns._frame_f32_buf == 0)
    assert not np.all(ns._frame_i16_buf == 0)
    ns.reset()
    assert np.all(ns._frame_f32_buf == 0)
    assert np.all(ns._frame_i16_buf == 0)


def test_noise_suppressor_reset_clears_resampler_history():
    """NoiseSuppressor.reset() must cascade to the resamplers' history tails."""
    ns = NoiseSuppressor(method="none", sample_rate=_SR)
    # Force the resamplers to exist by calling _ensure_resamplers
    ns._ensure_resamplers(_SR)
    assert ns._upsampler is not None
    ns._upsampler.process(_nonzero_chunk(64))
    assert ns._upsampler._hist is not None
    ns.reset()
    assert ns._upsampler._hist is not None
    assert np.all(ns._upsampler._hist == 0)


def test_streaming_resampler_reset_clears_history_and_phase():
    # 16k -> 48k upsampler (up=3, down=1)
    rs = _StreamingResampler(up=3, down=1)
    rs.process(_nonzero_chunk(64))
    assert rs._hist is not None
    rs.reset()
    assert rs._hist is not None
    assert np.all(rs._hist == 0)
    assert rs._phase == 0


def test_streaming_resampler_reset_before_process_does_not_crash():
    rs = _StreamingResampler(up=3, down=1)
    assert rs._hist is None
    rs.reset()
    assert rs._hist is None


def test_streaming_resampler_chunked_matches_oneshot():
    """Chunked streaming must match one-shot resampling to float32 precision.

    This is the guard for the phase-carry contract: the resampler must be
    stateless across a chunk boundary beyond its history tail, so feeding
    ``a`` then ``b`` has to reconstruct the same output as feeding ``a+b``.

    Exact equality is deliberately not asserted. Each output tap is a
    float32 ``np.dot``, and BLAS is free to order that reduction by SIMD
    lane, which depends on the *alignment* of the operand buffer -- the
    one-shot call slices a longer ``ext`` than the chunked one. Locally the
    two agree bit-for-bit; on macOS (Accelerate) they differ by ~9e-10,
    which is float32 noise on a 1.3e-2 signal, not a phase error. A real
    phase or history bug shifts output by a whole sample and lands at
    ~1e-2, four orders of magnitude above this tolerance, so the guard
    keeps its teeth.
    """
    rng = np.random.default_rng(7)
    a = rng.standard_normal(1411)
    b = rng.standard_normal(1411)
    ref = _StreamingResampler(up=160, down=441).process(np.concatenate([a, b]))
    rs = _StreamingResampler(up=160, down=441)
    streamed = np.concatenate([rs.process(a), rs.process(b)])
    assert len(ref) == len(streamed), "chunking must not change the output length"
    worst = float(np.max(np.abs(ref - streamed)))
    assert worst < 1e-6, f"chunked output diverges from one-shot by {worst:.3e}"


def test_streaming_resampler_chunk_cost_within_budget():
    """A 32 ms chunk (44.1 kHz -> 16 kHz) must process far inside its budget."""
    import sys
    import time

    rng = np.random.default_rng(1)
    chunk = rng.standard_normal(1411).astype(np.float32)
    rs = _StreamingResampler(up=160, down=441)
    for _ in range(5):
        rs.process(chunk)
    # Time each chunk separately and judge the FASTEST. A wall-clock mean on
    # a shared CI runner measures the scheduler, not the algorithm: one
    # descheduled iteration (xdist workers on 2 cores) drags the mean to
    # 18.7 ms while the best iteration is 14.8 ms.
    per_chunk_ms: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        rs.process(chunk)
        per_chunk_ms.append((time.perf_counter() - t0) * 1000)
    best_ms = min(per_chunk_ms)
    mean_ms = sum(per_chunk_ms) / len(per_chunk_ms)
    # The ceiling has to account for what is actually being timed. `process`
    # is a Python loop of ~512 `np.dot` calls per chunk, so under coverage's
    # tracer every one of those lines is instrumented: the same code that
    # costs 0.7 ms here costs ~15 ms on a windows-2022 runner running the
    # suite with `--cov`. Judging it against 10 ms there fails a healthy
    # resampler. The regression this guards against -- the old dense
    # `lfilter` form -- is ~200 ms, so a 60 ms ceiling under tracing still
    # has 3x of teeth, and 10 ms is kept for the untraced case.
    ceiling_ms = 10.0 if sys.gettrace() is None else 60.0
    assert best_ms < ceiling_ms, (
        f"resampler too slow: best {best_ms:.1f} ms/chunk (mean {mean_ms:.1f}, ceiling {ceiling_ms})"
    )


def test_notch_reset_zeros_state():
    """NotchFilter.reset() must zero the IIR ``zi`` carry state except"""
    from voice_typer.server.audio_filters.base import ANTIDENORMAL_EPSILON
    from voice_typer.server.audio_filters.notch import NotchFilter

    notch = NotchFilter(frequency_hz=60.0, sample_rate=_SR)
    # Process a non-zero chunk so the IIR ``zi`` carry state is
    notch.process(_nonzero_chunk(1024), _SR)

    # Sanity: ``zi`` is non-zero BEFORE reset (the IIR carry state
    _b, _a, zi_before = notch._state
    assert zi_before is not None
    assert not np.all(zi_before == 0), "zi must be non-zero BEFORE reset (else the test is vacuous)."

    # reset.
    notch.reset()

    # The state tuple is preserved (same b/a arrays, same zi array
    assert notch._state is not None
    _b2, _a2, zi_after = notch._state
    assert zi_after is not None
    assert zi_after.size >= 1, "notch zi must have at least one element"

    assert zi_after[0] == np.float32(ANTIDENORMAL_EPSILON), (
        f"zi[0] must equal ANTIDENORMAL_EPSILON ({ANTIDENORMAL_EPSILON}); got {zi_after[0]}."
    )
    # All other elements (zi[1:]) must be exactly zero.
    if zi_after.size > 1:
        assert np.all(zi_after[1:] == 0), f"zi[1:] must be all-zero after reset; got {zi_after[1:]}."


def test_notch_reset_before_process_does_not_crash():
    """reset() before process() must not crash, the IIR state is"""
    from voice_typer.server.audio_filters.notch import NotchFilter

    notch = NotchFilter(frequency_hz=60.0, sample_rate=_SR)
    # No process() call, zi is still the initial zero-filled array.
    notch.reset()
    # State must still be valid (filter not degraded).
    assert notch._state is not None
    assert notch.is_degraded is False


def test_notch_reset_idempotent():
    """Calling reset() twice must leave the filter in the same state"""
    from voice_typer.server.audio_filters.base import ANTIDENORMAL_EPSILON
    from voice_typer.server.audio_filters.notch import NotchFilter

    notch = NotchFilter(frequency_hz=60.0, sample_rate=_SR)
    notch.process(_nonzero_chunk(1024), _SR)
    notch.reset()
    _b1, _a1, zi_after_first = notch._state
    assert zi_after_first[0] == np.float32(ANTIDENORMAL_EPSILON)

    # Second reset, idempotent (no accumulation, no error).
    notch.reset()
    _b2, _a2, zi_after_second = notch._state
    assert zi_after_second[0] == np.float32(ANTIDENORMAL_EPSILON)
    if zi_after_second.size > 1:
        assert np.all(zi_after_second[1:] == 0)
