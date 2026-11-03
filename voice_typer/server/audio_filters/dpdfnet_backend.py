"""DPDFNet streaming noise-suppression backend (DeepFilterNet2 + dual-path RNN).

Why this file exists: it adapts the ``dpdfnet2`` streaming ONNX model to the
:class:`~voice_typer.server.audio_filters.base.AudioFilter` contract, which
requires ``process(chunk)`` to return EXACTLY ``len(chunk)`` samples.

The upstream streaming path lags by one model window (20 ms @ 16 kHz): its
first calls return an empty array and every later call returns fewer samples
than it consumed. Feeding that output straight into the recording buffer would
drop the first 20 ms and shift the rest, so this adapter pre-fills an output
FIFO with one window of zeros and pops exactly the consumed length per call.
Cost: a fixed 20 ms delay, zero drift.

The ONNX session is shared process-wide (one ~10 MB graph, thread-safe
``InferenceSession.run``); RNN state, buffers and the FIFO stay per instance.

Model provenance: ``Ceva-IP/DPDFNet`` on Hugging Face, ``onnx/dpdfnet2.onnx``
(revision ``dd6818d0``), Apache-2.0. It ships beside ``silero_vad.onnx`` /
``gtcrn_simple.onnx`` so the app needs no download and no network for it. The
graph's session/state bootstrap below mirrors the Apache-2.0 ``dpdfnet``
package (``onnx_backend.py`` / ``audio.py``) rather than depending on it: that
package hard-depends on librosa -> numba/llvmlite, which does not freeze.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from voice_typer.server._audio_constants import WHISPER_SAMPLE_RATE
from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.audio_filters.resampler import _resampler_group_delay_ms, _StreamingResampler
from voice_typer.server.duration import format_duration

if TYPE_CHECKING:
    # ``np.ndarray`` annotations need a real module symbol; the runtime proxy
    # stays lazy so importing this module never pulls numpy in (PERF-COLDSTART-001).
    import numpy as np
else:
    np = lazy_module("numpy")

log = logging.getLogger(__name__)

# Bundled weights, next to ``silero_vad.onnx`` (see MANIFEST.in + lausu.spec).
MODEL_PATH: Path = Path(__file__).resolve().parent.parent / "dpdfnet2.onnx"

# ``dpdfnet2`` is the 16 kHz model: the chain runs at the rate Whisper is
# trained on, so the common case needs no per-chunk resample.
MODEL_SAMPLE_RATE: int = WHISPER_SAMPLE_RATE

# Real-time-factor ceiling: above this the filter costs more than a third of a
# core and stays disabled. Measured ~0.09 warm on a 4-core laptop, so 0.3 leaves
# ~3x headroom for the hosts this is meant to run on.
MAX_REALTIME_FACTOR: float = 0.3

# Seconds of audio the one-time RTF probe measures (at preload only).
_PROBE_SECONDS: float = 2.0

# Windows run before the clock starts: the first ``session.run`` pays ORT's
# arena + thread-pool spin-up, which measured ~3x the steady cost.
_PROBE_WARMUP_WINDOWS: int = 5


class RealtimeFactorError(RuntimeError):
    """Measured model cost is above ``MAX_REALTIME_FACTOR`` (an expected verdict)."""


@dataclass(frozen=True)
class _Runtime:
    """Process-wide DPDFNet session + its fixed STFT geometry."""

    # onnxruntime ships no stubs for InferenceSession's dynamic surface, so the
    # handle is typed ``Any`` rather than ``object`` (which would flag every
    # ``run``/``get_modelmeta`` call as missing-attribute).
    session: Any
    init_state: np.ndarray
    in_spec_name: str
    in_state_name: str
    out_spec_name: str
    out_state_name: str
    win_len: int
    hop_size: int
    window: np.ndarray
    model_sample_rate: int
    realtime_factor: float


_runtime: _Runtime | None = None
_runtime_error: str = ""
_runtime_lock: threading.Lock = threading.Lock()
_preload_logged: bool = False


def _vorbis_window(window_len: int) -> np.ndarray:
    """Vorbis analysis/synthesis window used by the model's STFT."""
    half = window_len / 2
    indices = np.arange(window_len)
    s = np.sin(0.5 * np.pi * (indices + 0.5) / half)
    return np.sin(0.5 * np.pi * s * s).astype(np.float32)


def _init_state_from_metadata(session: Any) -> np.ndarray:
    """Rebuild the model's recurrent state vector from its embedded metadata."""
    meta = session.get_modelmeta().custom_metadata_map
    try:
        state_size = int(meta["state_size"])
        erb_size = int(meta["erb_norm_state_size"])
        spec_size = int(meta["spec_norm_state_size"])
        erb_init = np.array([float(x) for x in meta["erb_norm_init"].split(",")], dtype=np.float32)
        spec_init = np.array([float(x) for x in meta["spec_norm_init"].split(",")], dtype=np.float32)
    except KeyError as exc:
        raise RuntimeError(f"bundled dpdfnet model is missing metadata key {exc}") from exc
    state = np.zeros(state_size, dtype=np.float32)
    state[0:erb_size] = erb_init
    state[erb_size : erb_size + spec_size] = spec_init
    return np.ascontiguousarray(state)


def _probe_realtime_factor(runtime: _Runtime) -> float:
    """Measure the model's STEADY cost on ``_PROBE_SECONDS`` of audio.

    The first ``_PROBE_WARMUP_WINDOWS`` windows are run but not timed: a cold
    session pays ORT's arena/thread-pool spin-up, which made a warm host
    measure well above what the same session costs per window afterwards.
    """
    rate = runtime.model_sample_rate
    rng = np.random.default_rng(0)
    n = int(rate * _PROBE_SECONDS)
    t = np.arange(n) / rate
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 3.0 * t)
    probe = (0.1 * np.sin(2 * np.pi * 140.0 * t) * envelope + 0.01 * rng.standard_normal(n)).astype(np.float32)
    state = runtime.init_state.copy()
    in_buf = probe[: runtime.win_len].copy()
    pos = runtime.win_len
    windows = 0
    timed_windows = 0
    started = 0.0
    while in_buf.size >= runtime.win_len:
        windowed = in_buf[: runtime.win_len] * runtime.window
        spec = np.fft.rfft(windowed, n=runtime.win_len)
        spec_t = np.stack([spec.real, spec.imag], axis=-1).astype(np.float32)[None, None]
        enhanced, state = runtime.session.run(
            [runtime.out_spec_name, runtime.out_state_name],
            {runtime.in_spec_name: spec_t, runtime.in_state_name: state},
        )
        ri = enhanced[0, 0]
        np.fft.irfft(ri[:, 0] + 1j * ri[:, 1], n=runtime.win_len)  # exercise the synthesis cost
        in_buf = np.concatenate([in_buf[runtime.hop_size :], probe[pos : pos + runtime.hop_size]])
        pos += runtime.hop_size
        windows += 1
        if windows == _PROBE_WARMUP_WINDOWS:
            started = time.perf_counter()
        elif windows > _PROBE_WARMUP_WINDOWS:
            timed_windows += 1
        if pos > n:
            break
    if timed_windows == 0 or started == 0.0:
        return float("inf")
    elapsed = time.perf_counter() - started
    return elapsed / max(timed_windows * runtime.hop_size / rate, 1e-6)


def _load_runtime() -> _Runtime:
    """Build the shared session + geometry and gate it on measured RTF."""
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError(f"onnxruntime not importable: {exc}") from exc
    if not MODEL_PATH.is_file():
        raise RuntimeError(f"bundled dpdfnet model not found at {MODEL_PATH}")

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    try:
        session = ort.InferenceSession(
            str(MODEL_PATH),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
    except Exception as exc:
        raise RuntimeError(f"failed to load the bundled dpdfnet model: {exc}") from exc

    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) < 2 or len(outputs) < 2:
        raise RuntimeError(f"unexpected dpdfnet graph arity: {[i.name for i in inputs]!r}")

    meta = session.get_modelmeta().custom_metadata_map
    win_len = int(meta.get("window_length") or 0)
    if win_len <= 0:
        freq_bins = inputs[0].shape[-2] if len(inputs[0].shape) >= 2 else None
        win_len = int((freq_bins - 1) * 2) if isinstance(freq_bins, int) and freq_bins > 1 else MODEL_SAMPLE_RATE // 50
    hop_size = int(meta.get("hop_length") or win_len // 2)
    model_sr = int(meta.get("sample_rate") or MODEL_SAMPLE_RATE)

    runtime = _Runtime(
        session=session,
        init_state=_init_state_from_metadata(session),
        in_spec_name=inputs[0].name,
        in_state_name=inputs[1].name,
        out_spec_name=outputs[0].name,
        out_state_name=outputs[1].name,
        win_len=win_len,
        hop_size=hop_size,
        window=_vorbis_window(win_len),
        model_sample_rate=model_sr,
        realtime_factor=0.0,
    )
    return replace(runtime, realtime_factor=_warm_realtime_factor(runtime))


def _warm_realtime_factor(runtime: _Runtime) -> float:
    """Bounded median-of-3 RTF verdict (``MAX_REALTIME_FACTOR`` is the gate).

    One reading cannot decide: the first timed pass still rides the cold
    page-in of the graph plus ORT's arena growth, which measured ~3x the steady
    cost on hosts that then report 0.12-0.14. Nor can two: the minimum passes a
    slow host on one lucky sample. A first READING that already passes is the
    verdict (the common warm case, one probe); otherwise two more readings join
    it and their median decides.
    """
    readings: list[float] = [_probe_realtime_factor(runtime)]
    first = readings[0]
    if not (math.isfinite(first) and first <= MAX_REALTIME_FACTOR):
        readings.extend(_probe_realtime_factor(runtime) for _ in range(2))
    finite = sorted(r for r in readings if math.isfinite(r))
    if not finite:
        raise RealtimeFactorError("dpdfnet real-time factor unmeasurable (no finite probe reading)")
    rtf = finite[len(finite) // 2]
    if len(readings) > 1:
        log.info("[DPDFNET] RTF probe readings=%s verdict=%.3f", readings, rtf)
    if rtf > MAX_REALTIME_FACTOR:
        raise RealtimeFactorError(f"dpdfnet real-time factor {rtf:.3f} exceeds the {MAX_REALTIME_FACTOR:.2f} ceiling")
    return rtf


def _get_runtime() -> _Runtime:
    """Return the cached runtime, loading it under the lock (failures not cached)."""
    global _runtime, _runtime_error
    cached = _runtime
    if cached is not None:
        return cached
    with _runtime_lock:
        if _runtime is not None:
            return _runtime
        try:
            _runtime = _load_runtime()
        except Exception as exc:
            _runtime_error = str(exc)
            raise
        _runtime_error = ""
        return _runtime


def has_runtime() -> bool:
    """True once the shared session is loaded (preload finished successfully)."""
    return _runtime is not None


def last_error() -> str:
    """Human-readable reason the runtime is unavailable ("" when healthy)."""
    return _runtime_error


def is_available() -> bool:
    """True when the bundled model + onnxruntime are both present."""
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return MODEL_PATH.is_file() and MODEL_PATH.stat().st_size > 0


def preload() -> bool:
    """Load + warm + RTF-probe the shared runtime (fire-and-forget).

    Never raises. Runs on a daemon thread spawned AFTER the process handshake
    (C-START-1): session creation must never sit in front of startup. One INFO
    line with a C-LOG-2 duration suffix.
    """
    global _preload_logged
    started = time.perf_counter()
    try:
        runtime = _get_runtime()
    except RealtimeFactorError as exc:
        # Expected on slow hosts: a one-line verdict, not an error traceback.
        log.warning("[DPDFNET] disabled: %s", exc)
        return False
    except Exception as exc:
        log.debug("[DPDFNET] preload failed: %s", exc, exc_info=True)
        return False
    if not _preload_logged:
        _preload_logged = True
        log.info(
            "[DPDFNET] model ready (win=%d samples, rtf=%.3f, sr=%d)%s",
            runtime.win_len,
            runtime.realtime_factor,
            runtime.model_sample_rate,
            format_duration(time.perf_counter() - started),
        )
    else:
        log.debug("[DPDFNET] preload (repeat call)")
    return True


def _reset_for_tests() -> None:
    """Drop the shared runtime + log latch (test isolation)."""
    global _runtime, _runtime_error, _preload_logged
    with _runtime_lock:
        _runtime = None
        _runtime_error = ""
        _preload_logged = False


class DpdfnetBackend:
    """Streaming DPDFNet denoiser with an exact-length output contract."""

    def __init__(self, sample_rate: int = MODEL_SAMPLE_RATE) -> None:
        runtime = _runtime
        if runtime is None:
            raise RuntimeError(_runtime_error or "dpdfnet runtime not preloaded")
        self._rt = runtime
        self._source_rate = int(sample_rate)
        self._adapter: tuple[int, _StreamingResampler, _StreamingResampler] | None = None
        self._ensure_adapter(self._source_rate)
        self._state: np.ndarray = runtime.init_state.copy()
        self._in_buf: np.ndarray = np.zeros(0, dtype=np.float32)
        self._ola: np.ndarray = np.zeros(runtime.win_len, dtype=np.float32)
        # Pre-roll: one window of silence makes the delayed model output
        # length-preserving (see module docstring).
        self._fifo: np.ndarray = np.zeros(runtime.win_len, dtype=np.float32)
        self._warm()

    def _warm(self) -> None:
        """One zero window through the graph: validates the I/O contract once."""
        try:
            self._enhance(np.zeros(self._rt.win_len, dtype=np.float32))
        finally:
            self.reset()

    def _ensure_adapter(self, sample_rate: int) -> None:
        native = self._rt.model_sample_rate
        if sample_rate == native:
            self._adapter = None
            return
        if self._adapter is not None and self._adapter[0] == sample_rate:
            return
        rate_gcd = math.gcd(native, int(sample_rate))
        self._adapter = (
            int(sample_rate),
            _StreamingResampler(native // rate_gcd, int(sample_rate) // rate_gcd),
            _StreamingResampler(int(sample_rate) // rate_gcd, native // rate_gcd),
        )

    @property
    def window_samples(self) -> int:
        return self._rt.win_len

    @property
    def realtime_factor(self) -> float:
        return self._rt.realtime_factor

    @property
    def latency_ms(self) -> float:
        """Fixed algorithmic delay: one model window + resampler group delay."""
        native = self._rt.model_sample_rate
        base = self._rt.win_len / native * 1000.0
        if self._adapter is None:
            return base
        rate_gcd = math.gcd(native, self._source_rate)
        up = native // rate_gcd
        down = self._source_rate // rate_gcd
        return (
            base + _resampler_group_delay_ms(up, down, self._source_rate) + _resampler_group_delay_ms(down, up, native)
        )

    def process_chunk(self, chunk: np.ndarray, sample_rate: int | None = None) -> np.ndarray:
        """Return exactly ``len(chunk)`` enhanced samples (mono float32)."""
        samples = np.asarray(chunk, dtype=np.float32).reshape(-1)
        n_in = int(samples.size)
        if n_in == 0:
            return samples
        rate = self._source_rate if sample_rate is None else int(sample_rate)
        if rate != self._source_rate:
            self._source_rate = rate
            self._ensure_adapter(rate)
            self.reset()
        if self._adapter is None:
            return self._enhance(samples)
        _, upsampler, downsampler = self._adapter
        upsampled = upsampler.process(samples)
        enhanced = self._enhance(np.asarray(upsampled, dtype=np.float32))
        result = np.asarray(downsampler.process(enhanced), dtype=np.float32)
        if result.size == n_in:
            return result
        # Resampler rounding can cost a sample at a chunk boundary; never
        # change the caller's length (the recording buffer assumes it).
        if result.size > n_in:
            return result[:n_in]
        fitted = np.zeros(n_in, dtype=np.float32)
        fitted[: result.size] = result
        return fitted

    def _enhance(self, samples: np.ndarray) -> np.ndarray:
        """Push ``samples`` through the model; pop exactly ``len(samples)``."""
        rt = self._rt
        win_len = rt.win_len
        hop = rt.hop_size
        emitted: list[np.ndarray] = []
        self._in_buf = np.concatenate([self._in_buf, samples]) if self._in_buf.size else samples
        while self._in_buf.size >= win_len:
            windowed = self._in_buf[:win_len] * rt.window
            spec = np.fft.rfft(windowed, n=win_len)
            spec_t = np.stack([spec.real, spec.imag], axis=-1).astype(np.float32)[None, None]
            enhanced, self._state = rt.session.run(
                [rt.out_spec_name, rt.out_state_name],
                {rt.in_spec_name: spec_t, rt.in_state_name: self._state},
            )
            ri = enhanced[0, 0]
            frame = np.fft.irfft(ri[:, 0] + 1j * ri[:, 1], n=win_len).astype(np.float32) * rt.window
            self._ola += frame
            emitted.append(self._ola[:hop].copy())
            # copyto handles the overlapping source/dest with a temp copy.
            np.copyto(self._ola[:-hop], self._ola[hop:])
            self._ola[-hop:] = 0.0
            self._in_buf = self._in_buf[hop:]
        if emitted:
            self._fifo = np.concatenate([self._fifo, *emitted])
        if self._fifo.size < samples.size:
            # Only reachable if the caller's length contract was violated;
            # pad rather than desynchronise the stream silently.
            self._fifo = np.concatenate([self._fifo, np.zeros(samples.size - self._fifo.size, dtype=np.float32)])
        out = self._fifo[: samples.size].copy()
        self._fifo = self._fifo[samples.size :]
        return out

    def reset(self) -> None:
        """Clear RNN state, buffers and the pre-roll FIFO (new recording)."""
        rt = self._rt
        self._state = rt.init_state.copy()
        self._in_buf = np.zeros(0, dtype=np.float32)
        self._ola = np.zeros(rt.win_len, dtype=np.float32)
        self._fifo = np.zeros(rt.win_len, dtype=np.float32)
        if self._adapter is not None:
            _, upsampler, downsampler = self._adapter
            upsampler.reset()
            downsampler.reset()
