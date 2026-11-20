"""Tests for the minimal ctypes RNNoise binding and its noise_suppressor seam."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from voice_typer.server.audio_filters import noise_suppressor, rnnoise_ctypes
from voice_typer.server.audio_filters.rnnoise_ctypes import (
    FRAME_SIZE,
    SAMPLE_RATE,
    LibraryLoadError,
    RNNoise,
    find_library_path,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _native_lib_or_skip() -> str:
    path = find_library_path()
    if path is None:
        pytest.skip("native RNNoise library not installed")
    return path


def test_public_constants_match_rnnoise_c_api() -> None:
    assert FRAME_SIZE == 480
    assert SAMPLE_RATE == 48000
    assert rnnoise_ctypes._LIB_FILENAMES == {
        "Windows": "rnnoise.dll",
        "Darwin": "librnnoise.dylib",
        "Linux": "librnnoise.so",
    }


def test_find_library_path_resolves_real_file() -> None:
    path = _native_lib_or_skip()
    assert os.path.isfile(path)


def test_real_library_reduces_rms_of_white_noise() -> None:
    _native_lib_or_skip()
    rng = np.random.default_rng(7)
    frames = 50
    count = FRAME_SIZE * frames
    noise = (rng.standard_normal(count) * 0.25).astype(np.float32)
    pcm = np.multiply(np.clip(noise, -1.0, 1.0), 32767.0).astype(np.int16)

    denoiser = RNNoise(sample_rate=SAMPLE_RATE)
    cleaned = np.empty(count, dtype=np.float32)
    for index in range(frames):
        speech_prob, frame = denoiser.denoise_frame(pcm[index * FRAME_SIZE : (index + 1) * FRAME_SIZE][np.newaxis, :])
        assert frame.shape == (1, FRAME_SIZE)
        assert frame.dtype == np.int16
        assert 0.0 <= float(speech_prob[0, 0]) <= 1.0
        cleaned[index * FRAME_SIZE : (index + 1) * FRAME_SIZE] = frame[0]

    input_rms = float(np.sqrt(np.mean((pcm.astype(np.float32) / 32767.0) ** 2)))
    output_rms = float(np.sqrt(np.mean((cleaned / 32767.0) ** 2)))
    assert np.all(np.isfinite(cleaned))
    assert output_rms < input_rms * 0.1, f"RNNoise did not suppress noise: {input_rms:.6f} -> {output_rms:.6f}"


def test_missing_library_raises_library_load_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rnnoise_ctypes, "_lib", None)
    monkeypatch.setattr(rnnoise_ctypes, "find_library_path", lambda: None)
    with pytest.raises(LibraryLoadError, match="not found"):
        RNNoise(sample_rate=SAMPLE_RATE)


def test_reset_clears_per_instance_state() -> None:
    _native_lib_or_skip()
    rng = np.random.default_rng(11)
    t = np.arange(FRAME_SIZE) / SAMPLE_RATE
    first = (0.5 * np.sin(2 * np.pi * 440 * t) + 0.2 * rng.standard_normal(FRAME_SIZE)).astype(np.float32)
    second = (0.5 * np.sin(2 * np.pi * 660 * t) + 0.2 * rng.standard_normal(FRAME_SIZE)).astype(np.float32)
    pcm_first = np.multiply(first, 32767.0).astype(np.int16)[np.newaxis, :]
    pcm_second = np.multiply(second, 32767.0).astype(np.int16)[np.newaxis, :]

    carried = RNNoise(sample_rate=SAMPLE_RATE)
    carried.denoise_frame(pcm_first)
    _, carried_out = carried.denoise_frame(pcm_second)

    reset = RNNoise(sample_rate=SAMPLE_RATE)
    reset.denoise_frame(pcm_first)
    reset.reset()
    assert reset._states == []
    _, reset_out = reset.denoise_frame(pcm_second)

    fresh = RNNoise(sample_rate=SAMPLE_RATE)
    _, fresh_out = fresh.denoise_frame(pcm_second)

    np.testing.assert_array_equal(reset_out, fresh_out)
    assert not np.array_equal(carried_out, fresh_out)


def test_suppressor_forwards_reset_like_siblings(monkeypatch: pytest.MonkeyPatch) -> None:
    """RNNoise state resets on the same path as GTCRN/DPDFNet backends."""

    class _TrackingBackend:
        channels = 1

        def __init__(self) -> None:
            self.reset_calls = 0

        def denoise_frame(self, frame_i16: np.ndarray) -> tuple[float, np.ndarray]:
            return (0.0, frame_i16)

        def reset(self) -> None:
            self.reset_calls += 1

    monkeypatch.setattr(
        noise_suppressor,
        "_make_rnnoise_backend",
        lambda sample_rate: _TrackingBackend(),
    )
    suppressor = noise_suppressor.NoiseSuppressor(method="rnnoise", sample_rate=SAMPLE_RATE)
    suppressor.reset()
    assert cast(Any, suppressor._backend).reset_calls == 1


def test_noise_suppressor_init_does_not_import_pyrnnoise_packages() -> None:
    """Lock-in: our RNNoise path must never import pyrnnoise/audiolab/av."""
    expected_method = "rnnoise" if find_library_path() is not None else "any"
    code = (
        "import sys; "
        "from voice_typer.server.audio_filters.noise_suppressor import NoiseSuppressor; "
        "ns = NoiseSuppressor(method='rnnoise', sample_rate=48000); "
        f"expected = {expected_method!r}; "
        "assert expected == 'any' or ns.effective_method == expected, ns.effective_method; "
        "assert 'pyrnnoise' not in sys.modules, 'pyrnnoise package imported'; "
        "assert 'audiolab' not in sys.modules, 'audiolab imported'; "
        "assert 'av' not in sys.modules, 'av imported'; "
        "print('OK: no pyrnnoise/audiolab/av in sys.modules after RNNoise init')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT),
        env={**os.environ, "PYTHONPATH": str(_PROJECT_ROOT)},
    )
    assert result.returncode == 0, f"subprocess failed (rc={result.returncode}):\n{result.stdout}\n{result.stderr}"
    assert "OK" in result.stdout
