"""Mic-test transcription must receive 16 kHz audio regardless of device rate.

The test records at the device NATIVE rate (44100/48000 Hz) but every
transcription engine consumes 16 kHz. Passing native-rate audio through
unlabeled made Whisper hear ~2.8x slowed-down audio ("no speech" in real
speech). The service must resample to 16 kHz before transcribing.
"""

from __future__ import annotations

import types
import wave

import numpy as np


def _write_sine_wav(path, rate: int, seconds: float = 1.0, freq: float = 440.0):
    t = np.arange(int(rate * seconds), dtype=np.float64) / rate
    pcm = (0.5 * np.sin(2.0 * np.pi * freq * t) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    return pcm


def _dominant_freq(audio: np.ndarray, rate: int) -> float:
    spectrum = np.abs(np.fft.rfft(audio.astype(np.float64)))
    return float(np.argmax(spectrum) * rate / len(audio))


def _run_stop(tmp_path, monkeypatch, rate: int):
    from voice_typer.server import level_monitor as _lm
    from voice_typer.server.service.microphone_test import MicrophoneTestMixin

    wav = tmp_path / f"test-{rate}.wav"
    _write_sine_wav(wav, rate)

    captured = {}

    def _fake_stop():
        return {"success": True, "audio_file": {"path": str(wav), "bytes": wav.stat().st_size}}

    monkeypatch.setattr(_lm, "stop_test_recording", _fake_stop)

    def _fake_transcribe(audio):
        captured["audio"] = np.asarray(audio)
        return ""

    engine = types.SimpleNamespace(is_loaded=True, transcribe=_fake_transcribe)
    models = types.SimpleNamespace(active_transcriber=lambda: engine)
    svc = MicrophoneTestMixin()
    svc._app = types.SimpleNamespace(models=models)
    result = svc.microphone_test_stop()
    assert result.get("success") is True
    return captured["audio"]


def test_native_rate_audio_resampled_to_16k(tmp_path, monkeypatch):
    """44.1 kHz test audio reaches the engine at 16 kHz, tone intact."""
    got = _run_stop(tmp_path, monkeypatch, 44100)
    assert abs(len(got) - 16000) <= 2, f"engine must get 16k audio, got {len(got)}"
    assert abs(_dominant_freq(got, 16000) - 440.0) < 5.0, "tone must survive resampling at speed"


def test_16k_audio_passes_through_untouched(tmp_path, monkeypatch):
    """Native 16 kHz audio is not resampled."""
    got = _run_stop(tmp_path, monkeypatch, 16000)
    assert len(got) == 16000
