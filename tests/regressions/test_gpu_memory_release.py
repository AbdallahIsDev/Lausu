"""Source marker: ``tests/test_new_mem_001_gpu_release.py``."""

# === Source: tests/test_new_mem_001_gpu_release.py ===

from __future__ import annotations

import sys
import threading
from unittest.mock import MagicMock, patch

import pytest
from voice_typer.server.asr_utils import release_gpu_memory


class TestReleaseGpuMemoryHelper:
    """The shared helper is a no-op for ONNX Runtime, kept for API"""

    def test_no_torch_installed_is_noop(self, monkeypatch):
        """When torch is not installed, the helper must silently no-op."""
        # Simulate torch not being importable.
        monkeypatch.setitem(sys.modules, "torch", None)
        # Must not raise.
        release_gpu_memory()

    def test_does_not_invoke_torch_cuda_api_when_cuda_available(self, monkeypatch):
        """The post-ONNX helper is a no-op regardless of torch / CUDA"""
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = True
        fake_torch.cuda.synchronize = MagicMock()
        fake_torch.cuda.empty_cache = MagicMock()
        monkeypatch.setitem(sys.modules, "torch", fake_torch)

        release_gpu_memory()

        # The post-ONNX no-op must NOT touch the torch.cuda API at all.
        fake_torch.cuda.is_available.assert_not_called()
        fake_torch.cuda.synchronize.assert_not_called()
        fake_torch.cuda.empty_cache.assert_not_called()

    def test_swallows_runtime_errors(self, monkeypatch):
        """If torch.cuda.synchronize() raises (e.g. CUDA not initialized),"""
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = True
        fake_torch.cuda.synchronize.side_effect = RuntimeError("cuda not initialized")
        fake_torch.cuda.empty_cache = MagicMock()
        monkeypatch.setitem(sys.modules, "torch", fake_torch)

        # Must not raise.
        release_gpu_memory()

        fake_torch.cuda.empty_cache.assert_not_called()


class TestEnginesCallReleaseGpuMemory:
    """Each ASR engine's unload() must call release_gpu_memory()."""

    def test_parakeet_engine_unload_calls_release(self):
        """ParakeetEngine.unload() must invoke release_gpu_memory()."""
        import inspect

        from voice_typer.server.parakeet_engine import ParakeetEngine

        source = inspect.getsource(ParakeetEngine.unload)
        assert "release_gpu_memory()" in source, (
            "ParakeetEngine.unload() must call release_gpu_memory() "
            "to drop the ORT InferenceSession reference so the CUDA arena "
            "is freed on gc (NEW-MEM-001)"
        )

    def test_qwen_engine_unload_calls_release(self):
        """QwenEngine.unload() must invoke release_gpu_memory()."""
        import inspect

        from voice_typer.server.qwen_engine import QwenEngine

        source = inspect.getsource(QwenEngine.unload)
        assert "release_gpu_memory()" in source, (
            "QwenEngine.unload() must call release_gpu_memory() to drop the ORT session reference (NEW-MEM-001)"
        )


class TestReleaseGpuMemoryFunctional:
    """Functional test: actually invoke unload() and verify the helper"""

    def test_parakeet_unload_invokes_release(self):
        """End-to-end: ParakeetEngine.unload() must trigger"""
        from voice_typer.server.parakeet_engine import ParakeetEngine

        # Build a ParakeetEngine without loading the model.
        eng = ParakeetEngine.__new__(ParakeetEngine)
        eng._lock = threading.Lock()
        eng._inference_cond = threading.Condition(eng._lock)
        eng._active_inference = 0
        eng._model = None
        eng._processor = None

        # Mock the helper at its canonical source so the local import
        with patch("voice_typer.server.asr_utils.release_gpu_memory") as mock_release:
            eng.unload()
            mock_release.assert_called_once()

    def test_qwen_unload_invokes_release(self):
        """End-to-end: QwenEngine.unload() must trigger"""
        from voice_typer.server.qwen_engine import QwenEngine

        eng = QwenEngine.__new__(QwenEngine)
        eng._lock = threading.Lock()
        eng._model = None

        with patch("voice_typer.server.transcription.release_gpu_memory") as mock_release:
            eng.unload()
            mock_release.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
