"""Parity: vendored mel/STFT in qwen_onnx_model vs faster_whisper reference.

C7 removed the ``faster_whisper.feature_extractor`` import from the slim
core; these tests prove the vendored replacement is numerically the
same. faster_whisper stays an installed base dep, so the reference is
importable wherever this runs (importorskip, never a hard failure).
"""

from __future__ import annotations

import numpy as np

try:
    from faster_whisper.feature_extractor import FeatureExtractor as _RefExtractor
except ImportError:  # pragma: no cover - base dep always present
    _RefExtractor = None

import pytest
from voice_typer.server import qwen_onnx_model as qwen_mel


@pytest.mark.skipif(_RefExtractor is None, reason="faster_whisper reference not installed")
class TestVendoredMelParity:
    def _reference_mel(self, audio: np.ndarray) -> np.ndarray:
        ref = _RefExtractor(
            feature_size=qwen_mel._MEL_N_BINS,
            sampling_rate=qwen_mel._MEL_SAMPLE_RATE,
            hop_length=qwen_mel._MEL_HOP,
            n_fft=qwen_mel._MEL_N_FFT,
        )
        window = np.hanning(qwen_mel._MEL_N_FFT + 1)[:-1].astype("float32")
        stft = _RefExtractor.stft(
            audio, qwen_mel._MEL_N_FFT, hop_length=qwen_mel._MEL_HOP, window=window, return_complex=True
        )
        magnitudes = (np.abs(stft) ** 2).astype(np.float32)
        mel_spec = ref.mel_filters @ magnitudes
        log_spec = np.log10(np.clip(mel_spec, a_min=1e-10, a_max=None))
        log_spec = np.maximum(log_spec, log_spec.max() - 8.0)
        log_spec = (log_spec + 4.0) / 4.0
        log_spec = log_spec[:, :-1]
        return log_spec[np.newaxis, :, :]

    def test_sine_sweep_matches(self):
        sr = qwen_mel._MEL_SAMPLE_RATE
        t = np.arange(sr * 3, dtype=np.float32) / sr
        audio = (0.5 * np.sin(2 * np.pi * (440 + 220 * t) * t)).astype(np.float32)
        np.testing.assert_allclose(
            qwen_mel._log_mel_spectrogram(audio), self._reference_mel(audio), rtol=1e-5, atol=1e-6
        )

    def test_noise_matches(self):
        rng = np.random.default_rng(7)
        audio = rng.standard_normal(qwen_mel._MEL_SAMPLE_RATE * 2).astype(np.float32)
        np.testing.assert_allclose(
            qwen_mel._log_mel_spectrogram(audio), self._reference_mel(audio), rtol=1e-5, atol=1e-6
        )

    def test_short_audio_matches(self):
        audio = np.zeros(1000, dtype=np.float32)
        np.testing.assert_allclose(
            qwen_mel._log_mel_spectrogram(audio), self._reference_mel(audio), rtol=1e-5, atol=1e-6
        )

    def test_filterbank_matches(self):
        assert qwen_mel._whisper_mel_filters().shape == (qwen_mel._MEL_N_BINS, qwen_mel._MEL_N_FFT // 2 + 1)
