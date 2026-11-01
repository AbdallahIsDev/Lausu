"""DPDFNet streaming noise-suppression backend (DeepFilterNet2 + dual-path RNN).

Why this file exists: it adapts the ``dpdfnet`` streaming model to the
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
"""

from __future__ import annotations

import importlib
import math
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from voice_typer.server._audio_constants import WHISPER_SAMPLE_RATE
from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.audio_filters.resampler import _resampler_group_delay_ms, _StreamingResampler
from voice_typer.server.duration import format_duration

np = lazy_module("numpy")

import logging  # noqa: E402

log = logging.getLogger(__name__)

# ``dpdfnet2`` = DeepFilterNet2 (9.7 MB ONNX) at native 16 kHz: the chain runs
# at the same rate Whisper is trained on, so no per-chunk resample is needed.
MODEL_NAME: str = "dpdfnet2"
MODEL_SAMPLE_RATE: int = WHISPER_SAMPLE_RATE

# Real-time-factor ceiling. Measured 0.09 on a 4-core laptop, so 0.3 leaves
# ~3x headroom before the model is considered too expensive to ship enabled.
MAX_REALTIME_FACTOR: float = 0.3

# Seconds of synthetic speech used for the RTF probe (one-time, at preload).
_PROBE_SECONDS: float = 1.0

# Model cache lives inside the app config dir (never the user's global cache),
# so uninstall/backup treat it like every other downloaded asset.
_CACHE_SUBDIR: str = "dpdfnet"


@dataclass(frozen=True)
class _Runtime:
    """Process-wide DPDFNet session + its fixed STFT geometry."""

    session: Any
    init_state: Any
    in_spec_name: str
    in_state_name: str
    out_spec_name: str
    out_state_name: str
    win_len: int
    hop_size: int
    window: Any
    model_sample_rate: int
    realtime_factor: float


_runtime: _Runtime | None = None
_runtime_error: str = ""
_runtime_lock: threading.Lock = threading.Lock()
_preload_logged: bool = False
_cache_env_owned: bool = False


def _default_cache_root() -> Path:
    from voice_typer.server._paths import config_dir

    return config_dir() / _CACHE_SUBDIR


def _ensure_cache_dir_env() -> None:
    """Point the library's cache at the app config dir unless overridden.

    ``dpdfnet.models`` reads ``DPDFNET_CACHE_DIR`` on every call. An
    externally-set value (a test redirect, a packager override) always wins;
    the value WE set is refreshed each call so it follows ``config_dir()``
    when a test or a profile switch moves it.
    """
    global _cache_env_owned
    import os

    if "DPDFNET_CACHE_DIR" in os.environ and not _cache_env_owned:
        return
    os.environ["DPDFNET_CACHE_DIR"] = str(_default_cache_root())
    _cache_env_owned = True


def has_runtime() -> bool:
    """True once the shared session is loaded (preload finished successfully)."""
    return _runtime is not None


def _probe_realtime_factor(runtime: _Runtime) -> float:
    """Measure the model's cost on one second of audio at its own rate."""
    rate = runtime.model_sample_rate
    rng = np.random.default_rng(0)
    n = int(rate * _PROBE_SECONDS)
    t = np.arange(n) / rate
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 3.0 * t)
    probe = (0.1 * np.sin(2 * np.pi * 140.0 * t) * envelope + 0.01 * rng.standard_normal(n)).astype(np.float32)
    window = runtime.window
    win_len = runtime.win_len
    hop = runtime.hop_size
    state = runtime.init_state.copy()
    in_buf = probe[:win_len].copy()
    pos = win_len
    windows = 0
    started = time.perf_counter()
    while in_buf.size >= win_len:
        windowed = in_buf[:win_len] * window
        spec = np.fft.rfft(windowed, n=win_len)
        spec_t = np.stack([spec.real, spec.imag], axis=-1).astype(np.float32)[None, None]
        enhanced, state = runtime.session.run(
            [runtime.out_spec_name, runtime.out_state_name],
            {runtime.in_spec_name: spec_t, runtime.in_state_name: state},
        )
        ri = enhanced[0, 0]
        np.fft.irfft(ri[:, 0] + 1j * ri[:, 1], n=win_len)  # exercise the synthesis cost
        in_buf = np.concatenate([in_buf[hop:], probe[pos : pos + hop]])
        pos += hop
        windows += 1
        if pos > n:
            break
    elapsed = time.perf_counter() - started
    return elapsed / max(windows * hop / MODEL_SAMPLE_RATE, 1e-6)


def _dpdfnet_symbol(module: str, name: str) -> Any:
    """Resolve one dpdfnet symbol by name at runtime.

    The optional package ships no stubs, so a static import would add
    ``import-untyped`` errors only on machines that happen to have it
    installed (C-TEST-13).
    """
    try:
        return getattr(importlib.import_module(f"dpdfnet.{module}"), name)
    except ImportError as exc:
        raise RuntimeError(f"dpdfnet not importable: {exc}") from exc


def _load_runtime(*, auto_download: bool) -> _Runtime:
    """Resolve the model, build the session, probe RTF (heavy; background only)."""
    _ensure_cache_dir_env()
    make_stft_config = _dpdfnet_symbol("audio", "make_stft_config")
    resolve_model = _dpdfnet_symbol("models", "resolve_model")
    build_runtime_model = _dpdfnet_symbol("onnx_backend", "build_runtime_model")
    infer_win_len = _dpdfnet_symbol("onnx_backend", "infer_win_len")

    try:
        resolved = resolve_model(model=MODEL_NAME, auto_download=auto_download)
    except FileNotFoundError as exc:
        raise RuntimeError(f"dpdfnet model '{MODEL_NAME}' is not downloaded yet") from exc

    runtime_model = build_runtime_model(resolved.onnx_path)
    model_sr = int(resolved.info.sample_rate)
    win_len = infer_win_len(runtime_model.session, model_sr)
    cfg = make_stft_config(win_len)
    runtime = _Runtime(
        session=runtime_model.session,
        init_state=runtime_model.init_state,
        in_spec_name=runtime_model.in_spec_name,
        in_state_name=runtime_model.in_state_name,
        out_spec_name=runtime_model.out_spec_name,
        out_state_name=runtime_model.out_state_name,
        win_len=win_len,
        hop_size=cfg.hop_size,
        window=cfg.window,
        model_sample_rate=model_sr,
        realtime_factor=0.0,
    )
    rtf = _probe_realtime_factor(runtime)
    if not math.isfinite(rtf) or rtf > MAX_REALTIME_FACTOR:
        raise RuntimeError(f"dpdfnet real-time factor {rtf:.3f} exceeds the {MAX_REALTIME_FACTOR:.2f} ceiling")
    return replace(runtime, realtime_factor=rtf)


def _get_runtime(*, auto_download: bool) -> _Runtime:
    """Return the cached runtime, loading it under the lock (failures not cached)."""
    global _runtime, _runtime_error
    cached = _runtime
    if cached is not None:
        return cached
    with _runtime_lock:
        if _runtime is not None:
            return _runtime
        try:
            _runtime = _load_runtime(auto_download=auto_download)
        except Exception as exc:
            _runtime_error = str(exc)
            raise
        _runtime_error = ""
        return _runtime


def _cached_runtime() -> _Runtime | None:
    return _runtime


def last_error() -> str:
    """Human-readable reason the runtime is unavailable ("" when healthy)."""
    return _runtime_error


def is_available() -> bool:
    """True when the backend can load (model file present, deps importable)."""
    for dep in ("dpdfnet", "onnxruntime"):
        try:
            importlib.import_module(dep)
        except ImportError:
            return False
    try:
        _ensure_cache_dir_env()
        get_cache_model_dir = _dpdfnet_symbol("models", "get_cache_model_dir")

        info_name = f"{MODEL_NAME}.onnx"
        return any(p.is_file() and p.stat().st_size > 0 for p in (get_cache_model_dir() / info_name,))
    except Exception:
        return False


def preload() -> bool:
    """Download + load + warm + RTF-probe the shared runtime (fire-and-forget).

    Never raises. Runs on a daemon thread spawned AFTER the process handshake
    (C-START-1): the download and the ~1 s session build must never sit in
    front of startup. One INFO line with a C-LOG-2 duration suffix.
    """
    global _preload_logged
    started = time.perf_counter()
    try:
        runtime = _get_runtime(auto_download=True)
    except Exception as exc:
        log.debug("[DPDFNET] preload failed: %s", exc, exc_info=True)
        return False
    if not _preload_logged:
        _preload_logged = True
        log.info(
            "[DPDFNET] model %s ready (win=%d samples, rtf=%.3f, sr=%d)%s",
            MODEL_NAME,
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
        runtime = _cached_runtime()
        if runtime is None:
            reason = _runtime_error or "dpdfnet runtime not preloaded"
            raise RuntimeError(reason)
        self._rt = runtime
        self._source_rate = int(sample_rate)
        self._adapter: tuple[int, _StreamingResampler, _StreamingResampler] | None = None
        self._ensure_adapter(self._source_rate)
        self._state: Any = runtime.init_state.copy()
        self._in_buf: Any = np.zeros(0, dtype=np.float32)
        self._ola: Any = np.zeros(runtime.win_len, dtype=np.float32)
        # Pre-roll: one window of silence makes the delayed model output
        # length-preserving (see module docstring).
        self._fifo: Any = np.zeros(runtime.win_len, dtype=np.float32)
        self._warm()
        self.reset()

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
            base
            + _resampler_group_delay_ms(up, down, self._source_rate)
            + _resampler_group_delay_ms(down, up, native)
        )

    def process_chunk(self, chunk: Any, sample_rate: int | None = None) -> Any:
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

    def _enhance(self, samples: Any) -> Any:
        """Push ``samples`` through the model; pop exactly ``len(samples)``."""
        rt = self._rt
        win_len = rt.win_len
        hop = rt.hop_size
        emitted: list[Any] = []
        if self._in_buf.size:
            self._in_buf = np.concatenate([self._in_buf, samples])
        else:
            self._in_buf = samples
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
            self._ola = self._ola + frame
            emitted.append(self._ola[:hop].copy())
            self._ola[:-hop] = self._ola[hop:]
            self._ola[-hop:] = 0.0
            self._in_buf = self._in_buf[hop:]
        if emitted:
            self._fifo = np.concatenate([self._fifo, *emitted]) if len(emitted) > 1 else np.concatenate(
                [self._fifo, emitted[0]]
            )
        if self._fifo.size < samples.size:
            # Only reachable if the caller's length contract was violated;
            # pad rather than desynchronise the stream silently.
            pad = np.zeros(samples.size - self._fifo.size, dtype=np.float32)
            self._fifo = np.concatenate([self._fifo, pad])
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

    @property
    def realtime_factor(self) -> float:
        return self._rt.realtime_factor
