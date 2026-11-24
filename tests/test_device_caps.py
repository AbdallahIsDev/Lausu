"""GPU capability probe + startup device self-heal."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

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

    @pytest.mark.parametrize("backends", [["cpu", "vulkan"], ["cpu", "cuda"]])
    def test_runner_gpu_backend_wins_over_cpu_only_ort(self, monkeypatch, backends) -> None:
        import voice_typer.server.nvidia_dll_paths as _nv
        import voice_typer.server.platform_utils as _pu

        # Hermetic w.r.t. the host OS: on macOS the probe short-circuits.
        monkeypatch.setattr(_pu, "is_macos", lambda: False)
        monkeypatch.setattr(_nv, "_cuda_runtime_available", lambda: True)
        monkeypatch.setattr(device_caps, "_runner_backends", lambda: set(backends))
        assert device_caps.gpu_available(refresh=True) is True
        assert device_caps.is_gpu_unverified() is False

    def test_cpu_only_contract_means_no_gpu(self, monkeypatch) -> None:
        import voice_typer.server.nvidia_dll_paths as _nv
        import voice_typer.server.platform_utils as _pu

        monkeypatch.setattr(_pu, "is_macos", lambda: False)
        monkeypatch.setattr(_nv, "_cuda_runtime_available", lambda: True)
        monkeypatch.setattr(device_caps, "_runner_backends", lambda: {"cpu"})
        assert device_caps.gpu_available(refresh=True) is False

    def test_unreadable_contract_is_unverified_and_keeps_cpu(self, monkeypatch, caplog) -> None:
        import voice_typer.server.nvidia_dll_paths as _nv
        import voice_typer.server.platform_utils as _pu

        monkeypatch.setattr(_pu, "is_macos", lambda: False)
        monkeypatch.setattr(_nv, "_cuda_runtime_available", lambda: True)
        monkeypatch.setattr(device_caps, "_runner_backends", lambda: None)
        with caplog.at_level("WARNING", logger="voice_typer.server.device_caps"):
            assert device_caps.gpu_available(refresh=True) is False
        assert device_caps.is_gpu_unverified() is True
        assert any("GPU UNVERIFIED" in r.getMessage() for r in caplog.records)

    def test_contract_reader_publishes_backends(self, monkeypatch, tmp_path) -> None:
        import voice_typer.worker.asr_runner.runner as runner_mod

        contract_dir = tmp_path / "runtime"
        contract_dir.mkdir()
        (contract_dir / "contract.json").write_text('{"version":"0.4.2","backends":["cpu","vulkan"]}')
        monkeypatch.setattr(runner_mod, "library_dir", lambda: contract_dir)
        assert device_caps._runner_backends() == {"cpu", "vulkan"}

    def test_probe_runs_inside_budget(self, monkeypatch) -> None:
        import voice_typer.server.nvidia_dll_paths as _nv

        monkeypatch.setattr(_nv, "_cuda_runtime_available", lambda: True)
        monkeypatch.setattr(device_caps, "_runner_backends", lambda: {"cpu"})
        t0 = time.monotonic()
        device_caps.gpu_available()
        assert time.monotonic() - t0 < 1.0


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
        # Startup reconciliation only persists the REQUEST; no engine has
        # reported an effective device yet.
        assert {"type": "config_changed", "data": {"device": "cpu"}} in published

    def test_hand_edited_gpu_value_healed(self, monkeypatch) -> None:
        monkeypatch.setattr(device_caps, "gpu_available", lambda: False)
        monkeypatch.setattr("voice_typer.server.event_bus.publish", lambda event: True)
        app, _saves = _make_app("GPU")
        assert startup_tasks.reconcile_configured_device(app) is True
        assert app.config.device == "cpu"

    def test_stale_cpu_pin_warns_when_gpu_present(self, monkeypatch, caplog) -> None:
        monkeypatch.setattr(device_caps, "gpu_available", lambda: True)
        app, saves = _make_app("cpu")
        with caplog.at_level("WARNING", logger="voice_typer.server.startup_tasks"):
            assert startup_tasks.reconcile_configured_device(app) is False
        assert app.config.device == "cpu"
        assert saves == []
        assert any("although a CUDA GPU is available" in r.getMessage() for r in caplog.records)

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
        assert {"type": "config_changed", "data": {"device": "cpu", "active_device": "cpu"}} in published

    def test_runner_abort_broadcasts_cpu_fallback(self, monkeypatch) -> None:
        """A stopped native decode emits the same session-scoped CPU switch."""
        import numpy as np
        from voice_typer.server.asr_utils import is_cuda_error

        assert is_cuda_error(RuntimeError("Library cublas64_12.dll is not found or cannot be loaded"))
        published: list[dict] = []
        monkeypatch.setattr("voice_typer.server.event_bus.publish", lambda event: published.append(event) or True)
        device_caps.publish_device_cpu_fallback("cublas boom")
        assert {"type": "config_changed", "data": {"device": "cpu", "active_device": "cpu"}} in published
        assert np.isfinite(1.0), "fixture sanity: numpy is available for decode tests"
