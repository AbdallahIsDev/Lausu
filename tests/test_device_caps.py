"""GPU capability probe + startup device self-heal."""

from __future__ import annotations

import sys
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from voice_typer.server import device_caps, startup_tasks


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    device_caps.reset_cache()
    # Neutralize the real DLL-dir scan: individual tests opt back in
    # where they assert on it. Keeps PATH/locks untouched.
    calls: list[bool] = []
    import voice_typer.server.nvidia_dll_paths as _nv

    monkeypatch.setattr(_nv, "_configure_nvidia_dll_paths", lambda: calls.append(True))
    yield calls
    device_caps.reset_cache()


def _no_gpu(monkeypatch) -> None:
    import voice_typer.server.nvidia_dll_paths as _nv

    monkeypatch.setattr(_nv, "_cuda_runtime_available", lambda: False)


class TestProbe:
    def test_caches_result(self, monkeypatch) -> None:
        calls: list[bool] = []

        def _probe() -> bool:
            calls.append(True)
            return True

        monkeypatch.setattr(device_caps, "_probe", _probe)
        assert device_caps.gpu_available() is True
        assert device_caps.gpu_available() is True
        assert len(calls) == 1

    def test_refresh_reprobes(self, monkeypatch) -> None:
        monkeypatch.setattr(device_caps, "_probe", lambda: False)
        assert device_caps.gpu_available() is False
        monkeypatch.setattr(device_caps, "_probe", lambda: True)
        assert device_caps.gpu_available() is False
        assert device_caps.gpu_available(refresh=True) is True

    def test_missing_cuda_dll_means_no_gpu(self, monkeypatch) -> None:
        _no_gpu(monkeypatch)
        assert device_caps.gpu_available() is False

    def test_macos_means_no_gpu(self, monkeypatch) -> None:
        import voice_typer.server.platform_utils as _pu

        monkeypatch.setattr(_pu, "is_macos", lambda: True)
        assert device_caps.gpu_available() is False

    def test_gpu_available_configures_first(self, monkeypatch, _fresh_cache) -> None:
        import voice_typer.server.nvidia_dll_paths as _nv

        monkeypatch.setattr(_nv, "_cuda_runtime_available", lambda: False)
        assert device_caps.gpu_available() is False
        assert _fresh_cache == [True], "probe must configure DLL dirs before checking"

    def test_probe_runs_inside_budget(self, monkeypatch) -> None:
        import voice_typer.server.nvidia_dll_paths as _nv

        monkeypatch.setattr(_nv, "_cuda_runtime_available", lambda: True)
        monkeypatch.setitem(sys.modules, "ctranslate2", None)
        monkeypatch.setitem(sys.modules, "onnxruntime", None)
        t0 = time.monotonic()
        device_caps.gpu_available()
        assert time.monotonic() - t0 < 1.0

    def test_ct2_cuda_wins_over_cpu_only_ort(self, monkeypatch) -> None:
        import sys
        import types

        import voice_typer.server.nvidia_dll_paths as _nv
        import voice_typer.server.platform_utils as _pu

        # Hermetic w.r.t. the host OS. ``_probe()`` returns False the moment
        # ``is_macos()`` is true (no CUDA on macOS), so on a macos-14 runner
        # the fakes below were never consulted and the test failed.
        monkeypatch.setattr(_pu, "is_macos", lambda: False)
        monkeypatch.setattr(_nv, "_cuda_runtime_available", lambda: True)
        fake_ct2 = types.SimpleNamespace(get_cuda_device_count=lambda: 1)
        monkeypatch.setitem(sys.modules, "ctranslate2", fake_ct2)
        fake_ort = types.SimpleNamespace(get_available_providers=lambda: ["CPUExecutionProvider"])
        monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
        assert device_caps.gpu_available(refresh=True) is True

    def test_ct2_zero_devices_means_no_gpu(self, monkeypatch) -> None:
        import sys
        import types

        import voice_typer.server.nvidia_dll_paths as _nv
        import voice_typer.server.platform_utils as _pu

        # Same host-OS neutrality as the test above: without it this one
        # passed on macOS via the short-circuit, testing nothing.
        monkeypatch.setattr(_pu, "is_macos", lambda: False)
        monkeypatch.setattr(_nv, "_cuda_runtime_available", lambda: True)
        fake_ct2 = types.SimpleNamespace(get_cuda_device_count=lambda: 0)
        monkeypatch.setitem(sys.modules, "ctranslate2", fake_ct2)
        assert device_caps.gpu_available(refresh=True) is False


def _make_app(device: Any) -> tuple[Any, list[bool]]:
    saves: list[bool] = []

    def save() -> bool:
        saves.append(True)
        return True

    app = SimpleNamespace(config=SimpleNamespace(device=device, save=save))
    return app, saves


class TestCudaAvailabilityCache:
    def test_invalidate_forgets_cached_verdict(self, monkeypatch) -> None:
        import voice_typer.server.nvidia_dll_paths as _nv

        # Hermetic start: earlier suites may have warmed the
        # process-global verdict (a real probe elsewhere caches it).
        _nv._invalidate_cuda_availability_cache()
        monkeypatch.setattr(_nv, "is_windows", lambda: True)
        monkeypatch.setattr(_nv, "_load_cuda_dll", lambda ctypes, name: False)
        assert _nv._cuda_runtime_available() is False
        monkeypatch.setattr(_nv, "_load_cuda_dll", lambda ctypes, name: True)
        assert _nv._cuda_runtime_available() is False, "verdict must be cached"
        _nv._invalidate_cuda_availability_cache()
        assert _nv._cuda_runtime_available() is True

    def test_configure_resets_cache(self, monkeypatch) -> None:
        import threading

        import voice_typer.server.nvidia_dll_paths as _nv

        monkeypatch.setattr(_nv, "is_windows", lambda: True)
        monkeypatch.setattr("os.path.isdir", lambda path: False)
        monkeypatch.setattr(_nv, "_cuda_availability_checked", True)
        state = {
            "_nvidia_dll_path_handles": [],
            "_nvidia_dll_paths_configured": False,
            "_nvidia_config_lock": threading.Lock(),
        }
        _nv._NvidiaDllPathManager(state)._configure_locked()
        assert _nv._cuda_availability_checked is False
        assert state["_nvidia_dll_paths_configured"] is True
        _nv._invalidate_cuda_availability_cache()


class TestReconcileConfiguredDevice:
    def test_noop_when_gpu_present(self, monkeypatch) -> None:
        monkeypatch.setattr(device_caps, "gpu_available", lambda: True)
        app, saves = _make_app("cuda")
        assert startup_tasks.reconcile_configured_device(app) is False
        assert app.config.device == "cuda"
        assert saves == []

    def test_noop_when_already_cpu(self, monkeypatch) -> None:
        monkeypatch.setattr(device_caps, "gpu_available", lambda: False)
        app, saves = _make_app("cpu")
        assert startup_tasks.reconcile_configured_device(app) is False
        assert saves == []

    def test_forces_cpu_and_persists(self, monkeypatch) -> None:
        monkeypatch.setattr(device_caps, "gpu_available", lambda: False)
        published: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish",
            lambda event: published.append(event),
        )
        app, saves = _make_app("cuda")
        assert startup_tasks.reconcile_configured_device(app) is True
        assert app.config.device == "cpu"
        assert saves == [True]
        assert {"type": "config_changed", "data": {"device": "cpu"}} in published

    def test_hand_edited_gpu_value_healed(self, monkeypatch) -> None:
        monkeypatch.setattr(device_caps, "gpu_available", lambda: False)
        monkeypatch.setattr("voice_typer.server.event_bus.publish", lambda event: True)
        app, _saves = _make_app("GPU")
        assert startup_tasks.reconcile_configured_device(app) is True
        assert app.config.device == "cpu"

    def test_save_failure_returns_false(self, monkeypatch) -> None:
        monkeypatch.setattr(device_caps, "gpu_available", lambda: False)
        app = SimpleNamespace(config=SimpleNamespace(device="cuda", save=lambda: False))
        assert startup_tasks.reconcile_configured_device(app) is False


class TestFallbackBroadcast:
    def test_publish_device_cpu_fallback(self, monkeypatch) -> None:
        published: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish",
            lambda event: published.append(event),
        )
        device_caps.publish_device_cpu_fallback("cublas boom")
        assert {"type": "config_changed", "data": {"device": "cpu"}} in published

    def test_system_whisper_fallback_broadcasts(self, monkeypatch) -> None:
        import numpy as np
        from voice_typer.server.system_whisper import SystemWhisperEngine

        engine = SystemWhisperEngine.__new__(SystemWhisperEngine)
        engine._model_size = "tiny"
        engine._weights_dir = "/tmp/fake-weights"
        engine._device = "cuda"
        engine._language = "en"
        engine._beam_size = 5
        engine._model = MagicMock(name="fw-model")
        engine._loaded = True
        engine._cpu_fallback_notified = False
        engine._model.transcribe.side_effect = [
            RuntimeError("Library cublas64_12.dll is not found or cannot be loaded"),
            ([MagicMock(text=" hi ")], MagicMock()),
        ]
        engine._rebuild_on_cpu = lambda: setattr(engine, "_device", "cpu")  # type: ignore[method-assign]
        published: list[dict] = []
        monkeypatch.setattr(
            "voice_typer.server.event_bus.publish",
            lambda event: published.append(event) or True,
        )
        result = engine.transcribe_with_fallback(np.ones(16000, dtype=np.float32))
        assert result == "hi"
        assert {"type": "config_changed", "data": {"device": "cpu"}} in published
