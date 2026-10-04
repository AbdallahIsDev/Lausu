"""SystemWhisperEngine GPU→CPU fallback regression tests."""

from __future__ import annotations

import sys
import threading
from collections import OrderedDict
from unittest.mock import MagicMock, patch

import pytest


def _make_engine(device: str = "cuda"):
    from voice_typer.server.system_whisper import SystemWhisperEngine

    engine = SystemWhisperEngine.__new__(SystemWhisperEngine)
    engine._model_size = "tiny"
    engine._weights_dir = "/tmp/fake-weights"
    engine._device = device
    engine._language = "en"
    engine._beam_size = 5
    engine._model = MagicMock(name="fw-model")
    engine._loaded = True
    engine._cpu_fallback_notified = False
    return engine


class TestSystemWhisperCublasFallback:
    def test_cublas_error_rebuilds_on_cpu_and_retries(self):
        import numpy as np

        engine = _make_engine(device="cuda")
        engine._model.transcribe.side_effect = [
            RuntimeError("Library cublas64_12.dll is not found or cannot be loaded"),
            ([MagicMock(text=" hello ")], MagicMock()),
        ]
        rebuilt = {}

        def _fake_rebuild():
            rebuilt["called"] = True
            engine._device = "cpu"

        engine._rebuild_on_cpu = _fake_rebuild  # type: ignore[method-assign]
        with patch("voice_typer.server.event_bus.publish", return_value=True):
            result = engine.transcribe_with_fallback(np.ones(16000, dtype=np.float32))
        assert result == "hello"
        assert rebuilt.get("called") is True
        assert engine._device == "cpu"
        assert engine._cpu_fallback_notified is True

    def test_non_cuda_error_does_not_rebuild(self):
        import numpy as np

        engine = _make_engine(device="cuda")
        engine._model.transcribe.side_effect = ValueError("unrelated boom")
        engine._rebuild_on_cpu = MagicMock(name="_rebuild_on_cpu")  # type: ignore[method-assign]
        with pytest.raises(ValueError, match="unrelated boom"):
            engine.transcribe_with_fallback(np.ones(16000, dtype=np.float32))
        engine._rebuild_on_cpu.assert_not_called()

    def test_cpu_device_never_retries(self):
        import numpy as np

        engine = _make_engine(device="cpu")
        engine._model.transcribe.side_effect = RuntimeError("cublas GEMM launch failed")
        engine._rebuild_on_cpu = MagicMock(name="_rebuild_on_cpu")  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="cublas"):
            engine.transcribe_with_fallback(np.ones(16000, dtype=np.float32))
        engine._rebuild_on_cpu.assert_not_called()

    def test_rebuild_uses_cpu_device(self, monkeypatch):
        engine = _make_engine(device="cuda")
        fake_fw = MagicMock(name="faster_whisper")
        monkeypatch.setitem(sys.modules, "faster_whisper", fake_fw)
        engine._rebuild_on_cpu.__wrapped__ if hasattr(engine._rebuild_on_cpu, "__wrapped__") else None
        from voice_typer.server.system_whisper import SystemWhisperEngine

        SystemWhisperEngine._rebuild_on_cpu(engine)
        _, kwargs = fake_fw.WhisperModel.call_args
        assert kwargs["device"] == "cpu"
        assert engine._device == "cpu"


class TestEffectiveDeviceWord:
    def test_device_info_is_gpu_word_for_cuda(self):
        engine = _make_engine(device="cuda")
        engine._effective_device = "cuda"
        assert engine.device_info == "GPU"

    def test_device_info_is_cpu_word_for_cpu(self):
        engine = _make_engine(device="cpu")
        engine._effective_device = "cpu"
        assert engine.device_info == "CPU"

    def test_device_info_falls_back_to_requested_word(self):
        engine = _make_engine(device="auto")
        engine._effective_device = "auto"
        assert engine.device_info == "auto"

    def test_no_cuda_jargon_in_device_info(self):
        engine = _make_engine(device="cuda")
        engine._effective_device = "cuda"
        assert "cuda" not in engine.device_info


class TestWatchdogDiscardDualType:
    def test_discard_handles_set_and_ordereddict(self):
        from voice_typer.server.transcription_watchdog import TranscriptionWatchdog

        helper = TranscriptionWatchdog()
        set_ctrl = MagicMock()
        set_ctrl._cancelled_cycle_ids = {"a", "b"}
        set_ctrl._cancelled_cycle_ids_lock = threading.Lock()
        helper.discard_cancelled_cycle_id(set_ctrl, "a")
        assert set_ctrl._cancelled_cycle_ids == {"b"}

        od_ctrl = MagicMock()
        od_ctrl._cancelled_cycle_ids = OrderedDict([("a", None), ("b", None)])
        od_ctrl._cancelled_cycle_ids_lock = threading.Lock()
        helper.discard_cancelled_cycle_id(od_ctrl, "a")
        assert list(od_ctrl._cancelled_cycle_ids) == ["b"]
        helper.discard_cancelled_cycle_id(od_ctrl, "missing-does-not-raise")
