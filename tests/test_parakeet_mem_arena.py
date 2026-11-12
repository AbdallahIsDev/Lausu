"""Parakeet ORT arena-off: options threaded, unload frees (no real weights)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from voice_typer.server.parakeet_engine import ParakeetEngine


def _mock_modules():
    mock_onnx_asr = MagicMock(name="mock_onnx_asr")
    mock_onnx_asr.__version__ = "0.12.0-test"
    mock_onnx_asr.load_model.side_effect = lambda *args, **kwargs: MagicMock(name="mock_model")
    mock_ort = MagicMock(name="mock_onnxruntime")
    mock_ort.__version__ = "1.20.0-test"
    mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]
    session_options = MagicMock(name="mock_session_options")
    mock_ort.SessionOptions.return_value = session_options
    return mock_onnx_asr, mock_ort, session_options


def _engine_with_mocks(tmp_path, monkeypatch):
    snap = tmp_path / "models--Masterx--parakeet-tdt-0.6b-ultra-onnx" / "snapshots" / "test123"
    snap.mkdir(parents=True)
    (snap / "model.onnx").write_bytes(b"fake-onnx")
    monkeypatch.setattr(
        "voice_typer.server.model_availability.snapshot_search_dirs",
        lambda config_dir, repo_id: [snap.parent.parent],
    )
    monkeypatch.setattr(
        "voice_typer.server.security.verify_model_integrity",
        lambda snapshot, repo_id: True,
    )
    saved = (
        ParakeetEngine._imports_loaded,
        ParakeetEngine._onnx_asr,
        ParakeetEngine._ort,
    )
    ParakeetEngine._imports_loaded = False
    ParakeetEngine._onnx_asr = None
    ParakeetEngine._ort = None
    mock_onnx_asr, mock_ort, session_options = _mock_modules()
    with patch.dict(
        sys.modules,
        {"onnx_asr": mock_onnx_asr, "onnxruntime": mock_ort},
    ):
        engine = ParakeetEngine(device="cpu", language="en")
        ParakeetEngine._ensure_imports()
    return engine, mock_onnx_asr, mock_ort, session_options, saved


def test_load_threads_arena_off_sess_options(tmp_path, monkeypatch):
    engine, mock_onnx_asr, _, session_options, saved = _engine_with_mocks(
        tmp_path, monkeypatch
    )
    try:
        with patch.object(type(engine), "_is_cached", return_value=True):
            assert engine.load() is True
        mock_onnx_asr.load_model.assert_called_once()
        _, kwargs = mock_onnx_asr.load_model.call_args
        assert kwargs.get("sess_options") is session_options
        # enable_cpu_mem_arena=False is the arena-off contract.
        assert session_options.enable_cpu_mem_arena is False
    finally:
        (
            ParakeetEngine._imports_loaded,
            ParakeetEngine._onnx_asr,
            ParakeetEngine._ort,
        ) = saved


def test_load_impl_threads_arena_off_sess_options(tmp_path, monkeypatch):
    engine, mock_onnx_asr, _, session_options, saved = _engine_with_mocks(
        tmp_path, monkeypatch
    )
    try:
        engine._onnx_model_dir = "C:/fake/snapshot"
        assert engine._load_impl(providers=["CPUExecutionProvider"]) is True
        mock_onnx_asr.load_model.assert_called_once()
        _, kwargs = mock_onnx_asr.load_model.call_args
        assert kwargs.get("sess_options") is session_options
        assert session_options.enable_cpu_mem_arena is False
    finally:
        (
            ParakeetEngine._imports_loaded,
            ParakeetEngine._onnx_asr,
            ParakeetEngine._ort,
        ) = saved


def test_make_sess_options_disabled_when_ort_missing(tmp_path, monkeypatch):
    engine, _, _, _, saved = _engine_with_mocks(tmp_path, monkeypatch)
    try:
        ParakeetEngine._ort = None
        assert engine._make_sess_options() is None
    finally:
        (
            ParakeetEngine._imports_loaded,
            ParakeetEngine._onnx_asr,
            ParakeetEngine._ort,
        ) = saved


def test_unload_still_frees_model(tmp_path, monkeypatch):
    engine, _, _, _, saved = _engine_with_mocks(tmp_path, monkeypatch)
    try:
        with patch.object(type(engine), "_is_cached", return_value=True):
            assert engine.load() is True
        assert engine.is_loaded is True
        engine.unload()
        assert engine.is_loaded is False
        assert engine._model is None
    finally:
        (
            ParakeetEngine._imports_loaded,
            ParakeetEngine._onnx_asr,
            ParakeetEngine._ort,
        ) = saved


def test_transcribe_still_raises_when_unloaded(tmp_path, monkeypatch):
    import numpy as np

    engine, _, _, _, saved = _engine_with_mocks(tmp_path, monkeypatch)
    try:
        assert engine.is_loaded is False
        import pytest

        with pytest.raises(RuntimeError, match="not loaded"):
            engine.transcribe(np.zeros(16000, dtype=np.float32))
    finally:
        (
            ParakeetEngine._imports_loaded,
            ParakeetEngine._onnx_asr,
            ParakeetEngine._ort,
        ) = saved
