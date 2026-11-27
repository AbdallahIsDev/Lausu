"""Golden equivalence and drift tests for the vectorized streaming resampler.

The golden vectors were captured from the previous per-output ``np.dot`` loop.
A single row-wise ``einsum`` changes only the float32 reduction order: worst
observed divergence is ~1.2e-8 absolute on 0.05-scale signals (~1.8e-7 of the
output peak), far below the 1e-6 tolerance already used by the streaming test.
History carries raw input samples, never previous outputs, so the difference
cannot accumulate across chunks; the 10,000-chunk test pins that.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
import pytest
from voice_typer.server.audio_filters.resampler import _StreamingResampler

_GOLDEN_PATH = Path(__file__).parent / "fixtures" / "resampler_golden.json"
_GOLDEN = json.loads(_GOLDEN_PATH.read_text(encoding="ascii"))

# 2e-8 is ~2x the largest observed reduction-order difference; a phase or
# history error moves whole samples (~1e-2) and is four orders above it.
_TOLERANCE = 2e-8


class _ScalarResampler(_StreamingResampler):
    """Reference process() using the original one-dot-per-output loop."""

    def process(self, x: np.ndarray) -> np.ndarray:
        if x.size == 0:
            return np.zeros(0, dtype=np.float32)
        x32 = np.ascontiguousarray(x, dtype=np.float32).reshape(-1)
        n_in = x32.size
        up, down = self._up, self._down
        m_total = n_in * up
        count = (m_total - self._phase + down - 1) // down if m_total > self._phase else 0
        out = np.empty(count, dtype=np.float32)
        hist = self._hist
        if hist is None:
            hist = np.zeros(self._hist_len, dtype=np.float32)
        ext = np.concatenate([hist, x32])
        base = hist.size
        for j in range(count):
            m = self._phase + j * down
            bank = self._banks[m % up]
            s = (m - (m % up)) // up + base
            lo = s - len(bank) + 1
            out[j] = float(np.dot(bank, ext[lo : s + 1]))
        tail = ext[-self._hist_len :] if ext.size >= self._hist_len else ext
        if tail.size < self._hist_len:
            pad = np.zeros(self._hist_len - tail.size, dtype=np.float32)
            tail = np.concatenate([pad, tail])
        self._hist = np.ascontiguousarray(tail)
        self._phase = (self._phase - m_total) % down
        self._in_total += n_in
        self._out_total += count
        return out


def _f32(payload: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(payload), dtype=np.float32)


def _assert_state(resampler: _StreamingResampler, chunk: dict) -> None:
    assert resampler._phase == chunk["phase"]
    assert resampler._in_total == chunk["in_total"]
    assert resampler._out_total == chunk["out_total"]
    assert resampler._hist is not None
    assert resampler._hist.tobytes() == _f32(chunk["hist"]).tobytes()


@pytest.mark.parametrize("case", _GOLDEN["cases"], ids=[c["name"] for c in _GOLDEN["cases"]])
def test_golden_vectors_match(case: dict) -> None:
    resampler = _StreamingResampler(case["up"], case["down"])
    for chunk in case["chunks"]:
        want = _f32(chunk["output"])
        got = resampler.process(_f32(chunk["input"]))
        assert got.dtype == np.float32
        assert got.size == want.size
        np.testing.assert_allclose(got, want, rtol=0.0, atol=_TOLERANCE)
        _assert_state(resampler, chunk)


@pytest.mark.parametrize("up,down", [(3, 1), (1, 3), (160, 147), (147, 160), (160, 441)])
def test_output_length_and_values_match_scalar_reference(up: int, down: int) -> None:
    rng = np.random.default_rng(31)
    for n in (1, 5, 13, 17, 64, 121, 511):
        x = (rng.standard_normal(n) * 0.05).astype(np.float32)
        reference = _ScalarResampler(up, down)
        vectorized = _StreamingResampler(up, down)
        want = reference.process(x)
        got = vectorized.process(x)
        assert got.size == want.size == (n * up + down - 1) // down
        np.testing.assert_allclose(got, want, rtol=0.0, atol=_TOLERANCE)
        assert (vectorized._phase, vectorized._in_total, vectorized._out_total) == (
            reference._phase,
            reference._in_total,
            reference._out_total,
        )
        assert vectorized._hist.tobytes() == reference._hist.tobytes()


@pytest.mark.parametrize("up,down", [(3, 1), (1, 3), (160, 147)])
def test_zero_length_input_preserves_state(up: int, down: int) -> None:
    resampler = _StreamingResampler(up, down)
    empty = np.zeros(0, dtype=np.float32)
    first = resampler.process(empty)
    assert first.size == 0 and first.dtype == np.float32
    assert resampler._hist is None
    assert (resampler._phase, resampler._in_total, resampler._out_total) == (0, 0, 0)

    resampler.process(np.full(17, 0.1, dtype=np.float32))
    state = (
        resampler._phase,
        resampler._in_total,
        resampler._out_total,
        resampler._hist.tobytes(),
    )
    after = resampler.process(empty)
    assert after.size == 0 and after.dtype == np.float32
    assert (
        resampler._phase,
        resampler._in_total,
        resampler._out_total,
        resampler._hist.tobytes(),
    ) == state


@pytest.mark.parametrize(
    "up,down,sizes",
    [(3, 1, (13, 1, 17, 5)), (1, 3, (13, 1, 17, 5)), (160, 147, (13, 17, 1, 5))],
)
def test_10000_chunks_have_no_accumulating_drift(up: int, down: int, sizes: tuple[int, ...]) -> None:
    rng = np.random.default_rng(23)
    reference = _ScalarResampler(up, down)
    vectorized = _StreamingResampler(up, down)
    first_1k = 0.0
    last_1k = 0.0
    for i in range(10_000):
        x = (rng.standard_normal(sizes[i % len(sizes)]) * 0.05).astype(np.float32)
        want = reference.process(x)
        got = vectorized.process(x)
        assert got.size == want.size
        delta = float(np.abs(got.astype(np.float64) - want.astype(np.float64)).max(initial=0))
        assert delta <= _TOLERANCE, f"diverged at chunk {i}: {delta:.3e}"
        if i < 1000:
            first_1k = max(first_1k, delta)
        if i >= 9000:
            last_1k = max(last_1k, delta)
    assert last_1k <= max(_TOLERANCE, first_1k)
    assert (vectorized._phase, vectorized._in_total, vectorized._out_total) == (
        reference._phase,
        reference._in_total,
        reference._out_total,
    )
    assert vectorized._hist.tobytes() == reference._hist.tobytes()
