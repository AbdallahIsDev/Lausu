"""NVIDIA wheel scan + probe ordering (the runtime contract probe lives in
``tests/test_device_caps.py``).
"""

from __future__ import annotations

import logging
import os
import sys
import threading

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
        monkeypatch.setattr(_nv, "_load_cuda_dll", lambda ctypes, name: probed.append(name) or True)
        assert _nv._cuda_runtime_available() is True
        assert sorted(probed) == ["cublas64_13.dll", "cublasLt64_13.dll"]

    def test_probe_falls_back_to_12_names(self, monkeypatch, _nv_state):
        probed: list[str] = []
        monkeypatch.setattr(_nv, "is_windows", lambda: True)
        monkeypatch.setattr(_nv, "_CONFIGURED_NVIDIA_BIN_DIRS", [])
        monkeypatch.setattr(_nv, "_load_cuda_dll", lambda ctypes, name: probed.append(name) or True)
        assert _nv._cuda_runtime_available() is True
        assert sorted(probed) == sorted(_nv._CUDA_DLL_CANDIDATES)
