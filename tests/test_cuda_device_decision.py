"""GPU device decision: reasoned logs, full wheel scan, ordering."""

from __future__ import annotations

import logging
import os
import sys
import threading
import types

import pytest
import voice_typer.server.nvidia_dll_paths as _nv


@pytest.fixture()
def _nv_state():
    checked, available = _nv._cuda_availability_checked, _nv._cuda_available
    bin_dirs = list(_nv._CONFIGURED_NVIDIA_BIN_DIRS)
    _nv._invalidate_cuda_availability_cache()
    yield
    _nv._cuda_availability_checked = checked
    _nv._cuda_available = available
    _nv._CONFIGURED_NVIDIA_BIN_DIRS = bin_dirs


def _fake_ct2(monkeypatch, count=None, exc=None, version="4.8.1-test"):
    calls: list[str] = []

    def _count():
        calls.append("cuda_enum")
        if exc is not None:
            raise exc
        return count

    fake = types.SimpleNamespace(get_cuda_device_count=_count, __version__=version)
    monkeypatch.setitem(sys.modules, "ctranslate2", fake)
    return calls


def _patch_transcription(monkeypatch, calls, available):
    import voice_typer.server.transcription as _t

    def _configure():
        calls.append("configure")

    monkeypatch.setattr(_t, "_configure_nvidia_dll_paths", _configure)
    monkeypatch.setattr(_t, "_cuda_runtime_available", lambda: available)


class TestResolveDeviceReasons:
    def test_explicit_cpu_logs_reason(self, monkeypatch, caplog):
        from voice_typer.worker.whisper.device import resolve_device

        _patch_transcription(monkeypatch, [], True)
        with caplog.at_level(logging.INFO, logger="voice_typer.server.transcription"):
            assert resolve_device(object(), "cpu") == ("cpu", "int8")
        assert any("reason" in r.message and "CPU" in r.message for r in caplog.records)

    def test_cuda_selected_logs_device_count(self, monkeypatch, caplog):
        from voice_typer.worker.whisper.device import resolve_device

        calls: list[str] = []
        _patch_transcription(monkeypatch, calls, True)
        enum_calls = _fake_ct2(monkeypatch, count=2)
        with caplog.at_level(logging.INFO, logger="voice_typer.server.transcription"):
            assert resolve_device(object(), "auto") == ("cuda", "float16")
        assert calls == ["configure"]
        assert enum_calls == ["cuda_enum"]
        assert any("cuda_devices=2" in r.message for r in caplog.records)

    def test_zero_devices_logs_diagnostics(self, monkeypatch, caplog):
        from voice_typer.worker.whisper.device import resolve_device

        _patch_transcription(monkeypatch, [], True)
        _fake_ct2(monkeypatch, count=0)
        monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
        with caplog.at_level(logging.INFO, logger="voice_typer.server.transcription"):
            assert resolve_device(object(), "auto") == ("cpu", "int8")
        text = " ".join(r.message for r in caplog.records)
        assert "cuda_devices=0" in text
        assert "CUDA_VISIBLE_DEVICES" in text

    def test_detection_error_logs_with_traceback(self, monkeypatch, caplog):
        from voice_typer.worker.whisper.device import resolve_device

        _patch_transcription(monkeypatch, [], True)
        _fake_ct2(monkeypatch, exc=OSError("no driver"))
        with caplog.at_level(logging.INFO, logger="voice_typer.server.transcription"):
            assert resolve_device(object(), "auto") == ("cpu", "int8")
        assert any("falling back to CPU" in r.message for r in caplog.records)

    def test_dll_gate_skips_ctranslate2_import(self, monkeypatch, caplog):
        import importlib.abc

        from voice_typer.worker.whisper.device import resolve_device

        _patch_transcription(monkeypatch, [], False)
        monkeypatch.delitem(sys.modules, "ctranslate2", raising=False)
        attempts: list[str] = []

        class _Guard(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name == "ctranslate2":
                    attempts.append(name)
                    raise ImportError("blocked")
                return None

        guard = _Guard()
        sys.meta_path.insert(0, guard)
        try:
            with caplog.at_level(logging.INFO, logger="voice_typer.server.transcription"):
                assert resolve_device(object(), "auto") == ("cpu", "int8")
        finally:
            sys.meta_path.remove(guard)
        assert attempts == []
        assert not any("CUDA detection failed" in r.message for r in caplog.records)
        assert any("cuda_runtime_dlls_unavailable" in r.message for r in caplog.records)


class TestPrependProbeLoadOrdering:
    def test_load_configures_before_whisper_import(self, monkeypatch):
        import importlib.abc
        import threading

        from voice_typer.server.asr_errors import ModelNotDownloadedError
        from voice_typer.worker.whisper import TranscriptionEngine, engine as _engine_mod

        order: list[str] = []
        monkeypatch.setattr(
            _engine_mod,
            "_configure_nvidia_dll_paths",
            lambda: order.append("configure"),
        )
        monkeypatch.delitem(sys.modules, "faster_whisper", raising=False)

        class _Watch(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name == "faster_whisper":
                    order.append("faster_whisper_import")
                return None

        watch = _Watch()
        sys.meta_path.insert(0, watch)
        try:
            engine = TranscriptionEngine.__new__(TranscriptionEngine)
            engine._lock = threading.RLock()
            engine._model = None
            engine._device = "cpu"
            engine._compute_type = "int8"
            engine.model_size = "tiny"
            engine._configured_model_size = "tiny"
            monkeypatch.setattr(engine, "_whisper_size_cached", lambda size: False)
            chain = engine._build_fallback_chain()
            with pytest.raises(ModelNotDownloadedError):
                engine._load_transcriber_impl(chain, acquire_lock=True)
        finally:
            sys.meta_path.remove(watch)
        assert order == ["configure", "faster_whisper_import"]


class TestWheelScanAndProbeNames:
    def test_scan_discovers_companion_bins(self, tmp_path, monkeypatch, caplog, _nv_state):
        import site

        pkgs = ["cublas", "cudnn", "cuda_nvrtc", "cuda_runtime", "cufft"]
        sp = tmp_path / "spkg" / "site-packages"
        bins = {}
        for pkg in pkgs:
            b = sp / "nvidia" / pkg / "bin"
            b.mkdir(parents=True)
            (b / f"{pkg}64_12.dll").write_text("")
            bins[pkg] = b
        empty_bin = sp / "nvidia" / "empty_pkg" / "bin"
        empty_bin.mkdir(parents=True)

        monkeypatch.setattr(_nv, "is_windows", lambda: True)
        monkeypatch.setattr(site, "getsitepackages", lambda: [str(sp)])
        monkeypatch.setattr(site, "getusersitepackages", lambda: str(tmp_path / "user"))
        monkeypatch.setattr(sys, "prefix", str(tmp_path / "p"))
        monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "b"))
        monkeypatch.setenv("PATH", "C:\\Windows")
        state = {
            "_nvidia_dll_path_handles": [],
            "_nvidia_dll_paths_configured": False,
            "_nvidia_config_lock": threading.Lock(),
        }
        with caplog.at_level(logging.INFO, logger="voice_typer.server.nvidia_dll_paths"):
            _nv._NvidiaDllPathManager(state)._configure_locked()
        path_env = os.environ["PATH"]
        for pkg in pkgs:
            assert str(bins[pkg]) in path_env
        assert str(empty_bin) not in path_env
        assert state["_nvidia_dll_paths_configured"] is True
        assert [str(bins[p]) for p in sorted(pkgs)] == _nv._CONFIGURED_NVIDIA_BIN_DIRS
        assert any("cuda_runtime" in r.message for r in caplog.records)

    def test_probe_prefers_on_disk_major(self, tmp_path, monkeypatch, _nv_state):
        bindir = tmp_path / "bin"
        bindir.mkdir()
        (bindir / "cublas64_13.dll").write_text("")
        (bindir / "cublasLt64_13.dll").write_text("")
        probed: list[str] = []
        monkeypatch.setattr(_nv, "is_windows", lambda: True)
        monkeypatch.setattr(_nv, "_CONFIGURED_NVIDIA_BIN_DIRS", [str(bindir)])
        monkeypatch.setattr(
            _nv, "_load_cuda_dll", lambda ctypes, name: probed.append(name) or True
        )
        assert _nv._cuda_runtime_available() is True
        assert sorted(probed) == ["cublas64_13.dll", "cublasLt64_13.dll"]

    def test_probe_falls_back_to_12_names(self, monkeypatch, _nv_state):
        probed: list[str] = []
        monkeypatch.setattr(_nv, "is_windows", lambda: True)
        monkeypatch.setattr(_nv, "_CONFIGURED_NVIDIA_BIN_DIRS", [])
        monkeypatch.setattr(
            _nv, "_load_cuda_dll", lambda ctypes, name: probed.append(name) or True
        )
        assert _nv._cuda_runtime_available() is True
        assert sorted(probed) == sorted(_nv._CUDA_DLL_CANDIDATES)
