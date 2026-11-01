"""Noise suppressor backend."""

from __future__ import annotations

import logging
import math
from typing import Any

from voice_typer.server._lazy_import import lazy_module

np = lazy_module("numpy")
from voice_typer.server._audio_constants import RNNOISE_SAMPLE_RATE, WHISPER_SAMPLE_RATE  # noqa: E402
from voice_typer.server.audio_filters.base import AudioFilter  # noqa: E402
from voice_typer.server.audio_filters.resampler import (  # noqa: E402, F401  # facade re-export
    _resampler_fir_num_taps,
    _resampler_group_delay_ms,
    _StreamingResampler,
)

log = logging.getLogger(__name__)

# Once-per-process latch for backend-ready INFO lines. Each fresh
_backend_ready_logged: set[str] = set()


def _log_backend_ready_once(key: str, msg: str, *args: object) -> None:
    """Log a backend-ready line once at INFO, repeats at DEBUG."""
    if key in _backend_ready_logged:
        log.debug(msg + " (repeat, already logged)", *args)
        return
    _backend_ready_logged.add(key)
    log.info(msg, *args)


# RNNoise requires 48kHz, 480-sample frames (10ms at 48kHz).
_RNNOISE_FRAME_SIZE: int = 480

# GTCRN (the bundled ONNX streaming model) is native 16 kHz and
_GTCRN_HOP_SIZE: int = 256

# DPDFNet aliases users can reach through hand-edited config files.
_DPDFNET_ALIASES: frozenset[str] = frozenset({"dpdfnet", "dpdfnet2"})

# float32 -> int16 conversion constants. ``_FLOAT_TO_INT16_MAX`` is the
_FLOAT_TO_INT16_MAX: float = float(2**15 - 1)  # 32767.0
_INT16_SCALE: float = _FLOAT_TO_INT16_MAX


class NoiseSuppressor(AudioFilter):
    """Neural noise suppression with multiple backends."""

    def __init__(
        self,
        method: str = "rnnoise",
        sample_rate: int = WHISPER_SAMPLE_RATE,
        quiet: bool = False,
    ) -> None:
        self.name = f"NoiseSuppressor({method})"
        self._method = method
        self._source_sample_rate = int(sample_rate)
        self._backend: object | None = None
        self._degraded: bool = False
        self._degraded_reason: str = ""
        # ``quiet`` suppresses the backend-init INFO/WARNING lines
        self._quiet = quiet

        # Frame buffering: carry holds partial frames between process() calls.
        self._carry: np.ndarray = np.array([], dtype=np.float32)

        # pre-allocated per-frame conversion buffers for the RNNoise
        self._frame_f32_buf: np.ndarray = np.zeros(_RNNOISE_FRAME_SIZE, dtype=np.float32)
        self._frame_i16_buf: np.ndarray = np.zeros(_RNNOISE_FRAME_SIZE, dtype=np.int16)
        # pre-allocated float64 output buffer for the concatenated RNNoise
        self._result_48k_buf: np.ndarray | None = None
        # pre-allocated float32 padding buffer for the length-match path
        self._padded_buf: np.ndarray | None = None

        # streaming resamplers created lazily by
        self._upsampler: _StreamingResampler | None = None
        self._downsampler: _StreamingResampler | None = None
        self._resampler_rate: int | None = None

        # GTCRN is native 16 kHz (not 48 kHz like RNNoise), so it gets
        self._gtcrn_upsampler: _StreamingResampler | None = None
        self._gtcrn_downsampler: _StreamingResampler | None = None
        self._gtcrn_resampler_rate: int | None = None
        # pre-allocated float32 output buffer for the concatenated GTCRN
        self._result_16k_buf: np.ndarray | None = None

        # DPDFNet model weights download in the background after startup
        # (C-START-1), so a chain built before that finishes serves the
        # rnnoise fallback. This flag lets the next reset() promote it.
        self._dpdfnet_pending: bool = False

        self._init_backend()

    def _init_backend(self) -> None:
        """Initialize the selected backend. Fall back to 'none' on failure."""
        method = self._method
        if method == "none":
            self._backend = None
            return

        if method == "rnnoise":
            self._init_rnnoise()
        elif method == "gtcrn":
            self._init_gtcrn()
        elif method in _DPDFNET_ALIASES:
            self._init_dpdfnet()
        elif method == "deepfilternet":
            # Legacy config value: the DeepFilterNet backend was replaced
            if not self._quiet:
                log.info("[NOISE-SUPPRESS] legacy method 'deepfilternet', using gtcrn")
            self._method = "gtcrn"
            self._init_gtcrn()
        else:
            if not self._quiet:
                log.warning("[NOISE-SUPPRESS] unknown method %r, using none", method)
            self._method = "none"
            self._backend = None

    def _try_gtcrn_substitute(self) -> bool:
        """Serve gtcrn when the configured backend is unavailable (no recursion).

        Used ONLY from the rnnoise-unavailable path: constructs the bundled
        gtcrn backend directly (never via _init_gtcrn, which would route back
        here on failure). Returns True when serving gtcrn.
        """
        try:
            from voice_typer.server.audio_filters.gtcrn_backend import GtcrnBackend

            self._backend = GtcrnBackend()
        except Exception:
            return False
        self._method = "gtcrn"
        if not self._quiet:
            _log_backend_ready_once(
                "gtcrn-substitute", "[NOISE-SUPPRESS] rnnoise unavailable, serving bundled gtcrn instead"
            )
        return True

    def _init_rnnoise(self) -> None:
        try:
            from pyrnnoise import RNNoise

            self._backend = RNNoise(sample_rate=RNNOISE_SAMPLE_RATE)
            if not self._quiet:
                _log_backend_ready_once("rnnoise", "[NOISE-SUPPRESS] RNNoise backend ready")
        except ImportError:
            # pyrnnoise (or its own audiolab/av chain) is not importable:
            # serve the bundled gtcrn model instead of running with no
            # neural denoising while the preset advertises it.
            self._degraded = True
            rnnoise_reason = "rnnoise library not installed"
            if self._try_gtcrn_substitute():
                self._degraded_reason = f"{rnnoise_reason}, serving bundled gtcrn instead"
                return
            if not self._quiet:
                log.warning(
                    "[NOISE-SUPPRESS] pyrnnoise not installed and gtcrn unavailable, falling back to none. "
                    "Install with: pip install pyrnnoise"
                )
            self._degraded_reason = rnnoise_reason
            self._method = "none"
        except Exception as exc:
            if not self._quiet:
                log.warning("[NOISE-SUPPRESS] RNNoise init failed: %s, falling back to none", exc)
            self._degraded = True
            self._degraded_reason = f"rnnoise init failed: {exc}"
            self._method = "none"

    def _init_gtcrn(self) -> None:
        """Initialize the GTCRN backend (bundled ONNX streaming model)."""
        try:
            from voice_typer.server.audio_filters.gtcrn_backend import GtcrnBackend

            self._backend = GtcrnBackend()
        except Exception as exc:
            if not self._quiet:
                log.warning("[NOISE-SUPPRESS] GTCRN init failed: %s, falling back to rnnoise", exc)
            # Mark degraded BEFORE calling _init_rnnoise so the flag is
            self._degraded = True
            gtcrn_reason = f"gtcrn init failed: {exc}, falling back to rnnoise"
            self._degraded_reason = gtcrn_reason

            # Switch to rnnoise at init time so process() uses the
            self._method = "rnnoise"
            self._init_rnnoise()

            if self._method == "none":
                # _init_rnnoise overwrote _degraded_reason with the
                rnnoise_reason = self._degraded_reason
                self._degraded_reason = f"{gtcrn_reason}; rnnoise fallback also unavailable: {rnnoise_reason}"
            else:
                # _init_rnnoise succeeded, restore gtcrn_reason as the
                self._degraded = True
                self._degraded_reason = gtcrn_reason
        else:
            if not self._quiet:
                _log_backend_ready_once("gtcrn", "[NOISE-SUPPRESS] GTCRN backend ready (bundled ONNX streaming model)")

    def _init_dpdfnet(self) -> None:
        """Initialize the DPDFNet backend (DeepFilterNet2 streaming ONNX).

        The model download + session build run on a startup daemon thread, so
        this can legitimately find no runtime yet. That is a degraded (not
        fatal) state: serve rnnoise for now and retry at the next reset().
        """
        reason = ""
        try:
            from voice_typer.server.audio_filters.dpdfnet_backend import DpdfnetBackend

            self._backend = DpdfnetBackend(sample_rate=self._source_sample_rate)
        except Exception as exc:
            reason = f"dpdfnet unavailable: {exc}"
        else:
            if not self._quiet:
                _log_backend_ready_once(
                    "dpdfnet",
                    "[NOISE-SUPPRESS] DPDFNet backend ready (DeepFilterNet2 streaming ONNX)",
                )
            return

        if not self._quiet:
            log.debug("[NOISE-SUPPRESS] %s, serving rnnoise until it is ready", reason)
        self._degraded = True
        self._dpdfnet_pending = True
        self._method = "rnnoise"
        self._init_rnnoise()
        if self._method == "none":
            rnnoise_reason = self._degraded_reason
            self._degraded_reason = f"{reason}; rnnoise fallback also unavailable: {rnnoise_reason}"
            return
        self._degraded = True
        self._degraded_reason = f"{reason}, serving rnnoise instead"

    def _promote_dpdfnet(self) -> None:
        """Swap the rnnoise fallback for DPDFNet once its runtime has landed.

        Called from ``reset()`` (recording start), never from ``process()``: a
        session build must not run on the audio callback. Uses the already
        cached runtime only, so a failed/slow preload costs nothing.
        """
        if not self._dpdfnet_pending or self._method != "rnnoise":
            return
        try:
            from voice_typer.server.audio_filters import dpdfnet_backend

            if dpdfnet_backend._cached_runtime() is None:
                return
            backend = dpdfnet_backend.DpdfnetBackend(sample_rate=self._source_sample_rate)
        except Exception:
            return
        self._backend = backend
        self._method = "dpdfnet"
        self._dpdfnet_pending = False
        self._degraded = False
        self._degraded_reason = ""
        if not self._quiet:
            _log_backend_ready_once(
                "dpdfnet",
                "[NOISE-SUPPRESS] DPDFNet backend ready (DeepFilterNet2 streaming ONNX)",
            )

    def process(self, audio: np.ndarray, sample_rate: int) -> np.ndarray | None:
        if self._method == "none" or self._backend is None or audio.size == 0:
            return audio

        original_shape = audio.shape
        samples = np.ravel(audio).astype(np.float32, copy=False)

        if self._method == "rnnoise":
            return self._process_rnnoise(samples, sample_rate, original_shape)
        if self._method == "gtcrn":
            return self._process_gtcrn(samples, sample_rate, original_shape)
        if self._method == "dpdfnet":
            return self._process_dpdfnet(samples, sample_rate, original_shape)
        #  defensive guard: ``_init_backend`` is supposed to
        if not self._degraded:
            self._degraded = True
            self._degraded_reason = f"{self._method} backend not yet implemented, falling back to rnnoise"
            log.warning(
                "[AUDIO] NoiseSuppressor: %s backend not yet wired; "
                "falling back to rnnoise for neural noise suppression",
                self._method,
            )
        try:
            self._method = "rnnoise"
            # The defensive ``_backend is None or not _backend.get(...)``
            if self._backend is None or (hasattr(self._backend, "get") and not self._backend.get("rnnoise")):
                self._init_rnnoise()
            return self._process_rnnoise(samples, sample_rate, original_shape)
        except Exception:
            # If rnnoise also fails, return the original audio (last resort).
            return audio.reshape(original_shape)

    def _ensure_resamplers(self, sample_rate: int) -> None:
        """Lazily create (or recreate) the streaming resamplers for ``sample_rate``."""
        if sample_rate == RNNOISE_SAMPLE_RATE:
            if self._resampler_rate != sample_rate:
                self._upsampler = None
                self._downsampler = None
                self._resampler_rate = sample_rate
            return
        if self._resampler_rate == sample_rate and self._upsampler is not None:
            return  # already configured for this rate
        gcd = math.gcd(RNNOISE_SAMPLE_RATE, int(sample_rate))
        up = RNNOISE_SAMPLE_RATE // gcd
        down = int(sample_rate) // gcd
        self._upsampler = _StreamingResampler(up, down)
        self._downsampler = _StreamingResampler(down, up)
        self._resampler_rate = int(sample_rate)

    def _process_rnnoise(
        self,
        samples: np.ndarray,
        sample_rate: int,
        original_shape: tuple,
    ) -> np.ndarray | None:
        """Process through RNNoise with frame buffering."""
        # ``# type: ignore[union-attr]`` suppressions. The process()
        assert self._backend is not None

        #  ensure streaming resamplers exist for this rate.
        self._ensure_resamplers(sample_rate)

        # Resample to 48kHz if needed (using streaming resamplers).
        up = self._upsampler.process(samples) if self._upsampler is not None else samples

        # Prepend carry from previous call
        combined = np.concatenate([self._carry, up])
        n_full = len(combined) // _RNNOISE_FRAME_SIZE
        remainder = len(combined) - n_full * _RNNOISE_FRAME_SIZE

        if n_full == 0:
            # Not enough for a full frame, buffer it
            self._carry = combined
            return None  # signal caller to skip this chunk

        # Set channel info once for pyrnnoise (mono).
        self._backend.channels = 1

        # pre-allocate the float64 output buffer for the concatenated
        total_out = n_full * _RNNOISE_FRAME_SIZE
        if self._result_48k_buf is None or self._result_48k_buf.shape[0] < total_out:
            self._result_48k_buf = np.empty(max(total_out, 1024), dtype=np.float64)
        result_48k = self._result_48k_buf[:total_out]

        for i in range(n_full):
            start = i * _RNNOISE_FRAME_SIZE
            frame = combined[start : start + _RNNOISE_FRAME_SIZE]
            out_slice = result_48k[i * _RNNOISE_FRAME_SIZE : (i + 1) * _RNNOISE_FRAME_SIZE]
            try:
                # clip float32 input to [-1, 1] BEFORE scaling to int16
                frame_f32 = self._frame_f32_buf
                np.clip(frame, -1.0, 1.0, out=frame_f32)
                np.multiply(frame_f32, _INT16_SCALE, out=frame_f32)
                frame_i16 = self._frame_i16_buf
                frame_i16[:] = frame_f32.astype(np.int16)
                # pyrnnoise expects [num_channels, 480]; returns (speech_prob, cleaned) as int16
                _, cleaned_i16 = self._backend.denoise_frame(frame_i16[np.newaxis, :])
                # write the cleaned frame directly into the result buffer
                np.copyto(out_slice, cleaned_i16[0], casting="same_kind")
                np.divide(out_slice, _FLOAT_TO_INT16_MAX, out=out_slice)
            except Exception as exc:
                log.debug("[NOISE-SUPPRESS] RNNoise frame failed: %s", exc)
                # fall back to the original frame (upcast float32 -> float64
                np.copyto(out_slice, frame, casting="same_kind")

        # Save remainder for next call
        if remainder > 0:
            self._carry = combined[n_full * _RNNOISE_FRAME_SIZE :]
        else:
            self._carry = np.array([], dtype=np.float32)

        # Resample back to source rate (using streaming resamplers).
        result = self._downsampler.process(result_48k) if self._downsampler is not None else result_48k

        # The resampling may produce slightly different length than input.
        target_len = len(samples)
        if len(result) >= target_len:
            result = result[:target_len]
        else:
            # pre-allocated padding buffer (lazy-resized). The tail beyond
            if self._padded_buf is None or self._padded_buf.shape[0] < target_len:
                self._padded_buf = np.zeros(max(target_len, 1024), dtype=np.float32)
            padded = self._padded_buf[:target_len]
            padded[: len(result)] = result
            padded[len(result) :] = 0.0
            result = padded

        return result.astype(np.float32, copy=False).reshape(original_shape)

    def _ensure_gtcrn_resamplers(self, sample_rate: int) -> None:
        """Lazily create (or recreate) the GTCRN streaming resamplers."""
        if sample_rate == WHISPER_SAMPLE_RATE:
            if self._gtcrn_resampler_rate != sample_rate:
                self._gtcrn_upsampler = None
                self._gtcrn_downsampler = None
                self._gtcrn_resampler_rate = sample_rate
            return
        if self._gtcrn_resampler_rate == sample_rate and self._gtcrn_upsampler is not None:
            return  # already configured for this rate
        gcd = math.gcd(WHISPER_SAMPLE_RATE, int(sample_rate))
        up = WHISPER_SAMPLE_RATE // gcd
        down = int(sample_rate) // gcd
        self._gtcrn_upsampler = _StreamingResampler(up, down)
        self._gtcrn_downsampler = _StreamingResampler(down, up)
        self._gtcrn_resampler_rate = int(sample_rate)

    def _process_gtcrn(
        self,
        samples: np.ndarray,
        sample_rate: int,
        original_shape: tuple,
    ) -> np.ndarray | None:
        """Process through the GTCRN streaming model with hop buffering."""
        assert self._backend is not None

        self._ensure_gtcrn_resamplers(sample_rate)

        # Resample to the model's native 16 kHz if needed.
        up = self._gtcrn_upsampler.process(samples) if self._gtcrn_upsampler is not None else samples

        # Prepend carry from previous call and slice into full hops.
        combined = np.concatenate([self._carry, up])
        n_full = len(combined) // _GTCRN_HOP_SIZE
        remainder = len(combined) - n_full * _GTCRN_HOP_SIZE

        if n_full == 0:
            # Not enough for a full hop, buffer it.
            self._carry = combined
            return None  # signal caller to skip this chunk

        # pre-allocated float32 output buffer: each hop's enhanced
        total_out = n_full * _GTCRN_HOP_SIZE
        if self._result_16k_buf is None or self._result_16k_buf.shape[0] < total_out:
            self._result_16k_buf = np.empty(max(total_out, 1024), dtype=np.float32)
        result_16k = self._result_16k_buf[:total_out]

        for i in range(n_full):
            start = i * _GTCRN_HOP_SIZE
            hop = combined[start : start + _GTCRN_HOP_SIZE]
            out_slice = result_16k[i * _GTCRN_HOP_SIZE : (i + 1) * _GTCRN_HOP_SIZE]
            try:
                enhanced, _ = self._backend.process_hop(hop)
                np.copyto(out_slice, enhanced)
            except Exception as exc:
                # A single failed hop falls back to the ORIGINAL hop
                log.debug("[NOISE-SUPPRESS] GTCRN hop failed: %s", exc)
                np.copyto(out_slice, hop)

        # Save remainder for next call.
        if remainder > 0:
            self._carry = combined[n_full * _GTCRN_HOP_SIZE :]
        else:
            self._carry = np.array([], dtype=np.float32)

        # Resample back to the source rate if needed.
        result = self._gtcrn_downsampler.process(result_16k) if self._gtcrn_downsampler is not None else result_16k

        # The resampling may produce slightly different length than
        target_len = len(samples)
        if len(result) >= target_len:
            result = result[:target_len]
        else:
            if self._padded_buf is None or self._padded_buf.shape[0] < target_len:
                self._padded_buf = np.zeros(max(target_len, 1024), dtype=np.float32)
            padded = self._padded_buf[:target_len]
            padded[: len(result)] = result
            padded[len(result) :] = 0.0
            result = padded

        return result.astype(np.float32, copy=False).reshape(original_shape)

    def _process_dpdfnet(
        self,
        samples: Any,
        sample_rate: int,
        original_shape: tuple,
    ) -> Any:
        """Process through DPDFNet; the backend already returns exact length.

        ``Any`` here is truthful, not a shortcut: ``_backend`` is an untyped
        object (the optional package ships no stubs), so the exact-length
        contract is enforced by the check below rather than by the signature.
        """
        assert self._backend is not None
        backend: Any = self._backend
        try:
            result = backend.process_chunk(samples, sample_rate)
        except Exception as exc:
            # Never kill the recording on a model hiccup: pass the raw chunk.
            log.debug("[NOISE-SUPPRESS] DPDFNet chunk failed: %s", exc)
            return samples.astype(np.float32, copy=False).reshape(original_shape)
        if len(result) == len(samples):
            return result.reshape(original_shape)
        return samples.astype(np.float32, copy=False).reshape(original_shape)

    def reset(self) -> None:
        # A recording is starting: use the configured backend if its
        # background preload finished since the chain was built.
        self._promote_dpdfnet()
        # zero the existing state array BEFORE replacing it
        if self._carry.size > 0:
            self._carry.fill(0)
        self._carry = np.array([], dtype=np.float32)
        # Zero the pre-allocated per-frame conversion buffers
        self._frame_f32_buf.fill(0)
        self._frame_i16_buf.fill(0)
        # zero the concatenated-output + padding buffers for the same
        if self._result_48k_buf is not None:
            self._result_48k_buf.fill(0)
        if self._padded_buf is not None:
            self._padded_buf.fill(0)
        #  also reset the streaming resamplers' filter state
        if self._upsampler is not None:
            self._upsampler.reset()
        if self._downsampler is not None:
            self._downsampler.reset()
        # GTCRN state: the model's recurrent caches + overlap-add tail
        if self._method == "gtcrn" and self._backend is not None:
            self._backend.reset()
        if self._result_16k_buf is not None:
            self._result_16k_buf.fill(0)
        if self._gtcrn_upsampler is not None:
            self._gtcrn_upsampler.reset()
        if self._gtcrn_downsampler is not None:
            self._gtcrn_downsampler.reset()
        # DPDFNet state: RNN state, STFT buffers, overlap-add + pre-roll FIFO
        if self._method == "dpdfnet" and self._backend is not None:
            self._backend.reset()

    def _resampler_pair_delay_ms(self, native_rate: int) -> float:
        """Round-trip group delay (ms) of this suppressor's streaming resampler pair."""
        source_rate = self._source_sample_rate
        if source_rate <= 0 or source_rate == native_rate:
            return 0.0
        rate_gcd = math.gcd(native_rate, source_rate)
        up = native_rate // rate_gcd
        down = source_rate // rate_gcd
        # Upsampler: input at the source rate. Downsampler: constructed as
        return _resampler_group_delay_ms(up, down, source_rate) + _resampler_group_delay_ms(down, up, native_rate)

    @property
    def latency_ms(self) -> float:
        # ~10ms (one RNNoise frame) / ~16ms (one 256-sample GTCRN hop at
        if self._method == "rnnoise":
            return 10.0 + self._resampler_pair_delay_ms(RNNOISE_SAMPLE_RATE)
        if self._method == "gtcrn":
            return 16.0 + self._resampler_pair_delay_ms(WHISPER_SAMPLE_RATE)
        if self._method == "dpdfnet" and self._backend is not None:
            # The backend owns its own resampler pair, so no extra term.
            return float(getattr(self._backend, "latency_ms", 0.0))
        return 0.0

    @property
    def is_degraded(self) -> bool:
        return self._degraded

    @property
    def degraded_reason(self) -> str:
        return self._degraded_reason
