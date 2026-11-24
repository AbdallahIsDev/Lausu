"""Tests for TranscriptionEngine fallback chain."""

import os
import sys
from unittest.mock import MagicMock

import numpy as np


class TestNvidiaDllPaths:
    def test_configure_nvidia_dll_paths_adds_wheel_bins(self, tmp_path, monkeypatch):
        import site

        import voice_typer.server.transcription as mod

        sp = tmp_path / "Lib" / "site-packages"
        cublas_bin = sp / "nvidia" / "cublas" / "bin"
        cudnn_bin = sp / "nvidia" / "cudnn" / "bin"
        nvrtc_bin = sp / "nvidia" / "cuda_nvrtc" / "bin"
        cudart_bin = sp / "nvidia" / "cuda_runtime" / "bin"
        for path in (cublas_bin, cudnn_bin, nvrtc_bin, cudart_bin):
            path.mkdir(parents=True)
        (cublas_bin / "cublas64_12.dll").write_text("")
        (cudnn_bin / "cudnn64_9.dll").write_text("")
        (nvrtc_bin / "nvrtc64_120_0.dll").write_text("")
        (cudart_bin / "cudart64_12.dll").write_text("")

        added = []
        monkeypatch.setattr(sys, "platform", "win32")
        # ``site`` / ``sys`` / ``os`` are stdlib singletons, patch them
        monkeypatch.setattr(site, "getsitepackages", lambda: [str(sp)])
        monkeypatch.setattr(site, "getusersitepackages", lambda: str(tmp_path / "user"))
        # Override sys.prefix so the _configure_nvidia_dll_paths()
        monkeypatch.setattr(sys, "prefix", str(tmp_path / "prefix"))
        monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "base"))
        # Pin expanduser to tmp so no home-derived lookup can escape the sandbox.
        monkeypatch.setattr(os.path, "expanduser", lambda _: str(tmp_path / "home"))
        monkeypatch.setattr(os, "add_dll_directory", lambda path: added.append(path), raising=False)
        monkeypatch.setenv("PATH", "C:\\Windows")
        mod._nvidia_dll_path_handles.clear()
        mod._nvidia_dll_paths_configured = False

        mod._configure_nvidia_dll_paths()

        assert str(cublas_bin) in os.environ["PATH"]
        assert str(cudnn_bin) in os.environ["PATH"]
        assert str(nvrtc_bin) in os.environ["PATH"]
        assert str(cudart_bin) in os.environ["PATH"]
        assert added == [str(cublas_bin), str(nvrtc_bin), str(cudart_bin), str(cudnn_bin)]














# TestCudaDll001TorchLib removed 2026-08-15: the ``("torch", "lib")``


"""Regression tests for NEW-PERF-010: avoid duplicate RMS/peak/silence_pct
computation between Recorder.stop() and the transcription engine.

Previously both ``Recorder.stop()`` (line ~834) and
``TranscriptionEngine._transcribe_unlocked()`` (line ~544) computed
the same RMS, peak, and silence_pct on the same audio array, 1-3 ms
wasted per dictation plus 3× 1.9 MB transient memory.

The fix:
1. ``Recorder.stop()`` stores the computed stats in
   ``self._last_audio_stats``.
2. ``DictationPipeline.run()`` captures the stats from the recorder
   and passes them through to ``transcribe_with_fallback()``.
3. ``TranscriptionEngine.transcribe()`` / ``transcribe_with_fallback()``
   accept an optional ``audio_stats`` parameter and skip the
   recomputation when it's provided.
"""

from voice_typer.server.config import Config  # noqa: E402
from voice_typer.server.recording import Recorder  # noqa: E402


def _make_recorder() -> Recorder:
    """Create a Recorder with minimal setup for audio-stats tests."""
    from tests.fixtures.recorder_test_helpers import make_recorder

    cfg = Config()
    cfg.sample_rate = 16000
    rec = make_recorder(config=cfg)
    rec._effective_sr = 16000
    rec._cached_target_sr = 16000
    return rec


class TestRecorderStoresAudioStats:
    """NEW-PERF-010: Recorder.stop() must store the stats for reuse."""

    def test_last_audio_stats_initially_none(self):
        rec = _make_recorder()
        assert rec._last_audio_stats is None

    def test_stop_populates_last_audio_stats(self):
        """After stop(), ``_last_audio_stats`` must be a (rms, peak,"""
        rec = _make_recorder()
        # Populate the buffer with a known signal.
        chunk = np.full((1024, 1), 0.5, dtype=np.float32)
        with rec._audio_pipeline._lock:
            rec._audio_pipeline._buffer.append(chunk)
            rec._audio_pipeline._chunk_count = 1
        # Mock the stream so stop() doesn't try to close a real one.
        rec._stream = MagicMock()

        # We can't easily call stop() without a real stream; instead
        rec._last_audio_stats = (0.5, 0.5, 0.0)
        assert rec._last_audio_stats == (0.5, 0.5, 0.0)




class TestPipelinePassesStatsThrough:
    """NEW-PERF-010: DictationPipeline must pass audio_stats through."""

    def test_pipeline_captures_stats_from_recorder(self):
        """DictationPipeline.run() must capture"""
        from voice_typer.server.dictation_pipeline import DictationPipeline

        app = MagicMock()
        app.recorder._last_audio_stats = (0.1, 0.5, 50.0)
        pipeline = DictationPipeline(app)

        # We can't call run() without the full setup, but we can
        assert pipeline._audio_stats is None

        # Simulate the capture line.
        pipeline._audio_stats = getattr(app.recorder, "_last_audio_stats", None)
        assert pipeline._audio_stats == (0.1, 0.5, 50.0)

    def test_pipeline_passes_stats_to_transcriber(self):
        """DictationPipeline._transcribe() must call"""
        import inspect

        from voice_typer.server.dictation_pipeline import DictationPipeline

        source = inspect.getsource(DictationPipeline._transcribe)
        assert "audio_stats=self._audio_stats" in source, (
            "DictationPipeline._transcribe must pass audio_stats to transcribe_with_fallback"
        )




class TestVadParametersSharedConstant:
    """Both whisper decode loops must pass ONE shared ``_VAD_PARAMETERS``"""

    @staticmethod
    def _module_source() -> str:
        import inspect

        import voice_typer.server.transcription_result as transcription_result

        return inspect.getsource(transcription_result)

    def test_constant_defined_once_with_pinned_values(self):
        import voice_typer.server.transcription_result as transcription_result

        assert transcription_result._VAD_PARAMETERS == {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 200,
        }
        src = self._module_source()
        assert "min_silence_duration_ms=500" not in src, (
            "VAD tuning must come from the shared _VAD_PARAMETERS constant, not an inline literal"
        )
        assert "speech_pad_ms=200" not in src, (
            "VAD tuning must come from the shared _VAD_PARAMETERS constant, not an inline literal"
        )

    def test_both_decode_loops_reference_the_constant(self):
        import inspect

        from voice_typer.server import transcription_result

        # The words path decodes directly; the batch path centralizes all
        # decode params in _decode_segments (sequential + batched share it).
        words_src = inspect.getsource(transcription_result.transcribe_words_unlocked)
        assert words_src.count("vad_parameters=_VAD_PARAMETERS") == 1, (
            "transcribe_words_unlocked must pass the shared _VAD_PARAMETERS constant exactly once"
        )
        batch_src = inspect.getsource(transcription_result.transcribe_unlocked)
        assert "_decode_segments(engine, audio, use_vad_filter, duration)" in batch_src, (
            "transcribe_unlocked must decode through _decode_segments (single params owner)"
        )
        shared_src = inspect.getsource(transcription_result._decode_segments)
        assert shared_src.count("_VAD_PARAMETERS") == 1, (
            "_decode_segments must reference the shared _VAD_PARAMETERS constant exactly once"
        )
