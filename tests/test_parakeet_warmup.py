"""Warm-at-load contract for ``ParakeetEngine``.

ORT builds its CUDA/cuDNN state on the FIRST ``Run``, not at session
creation: a real 141 s dictation spent 17 s inside chunk 1/7 and ~1.5 s in
every chunk after it, i.e. the whole stall was one-time init paid on the
user's dictation. ``load()`` therefore primes the session once so that cost
lands on the background load thread instead.

The torch-era ``_warm_up_model`` (a ``generate()`` call before the ONNX
migration) must still stay gone: priming here runs the real ``recognize``
path, which is what ORT actually initializes.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from voice_typer.server._audio_constants import WHISPER_SAMPLE_RATE  # noqa: E402
from voice_typer.server.parakeet_engine import ParakeetEngine  # noqa: E402
from voice_typer.server.parakeet_engine._constants import _CHUNK_SECONDS  # noqa: E402


def _mock_onnx_asr_module(recognize_error: Exception | None = None) -> MagicMock:
    """Build a MagicMock that quacks like the bits of ``onnx_asr`` we use."""
    mock = MagicMock(name="mock_onnx_asr")
    mock.__version__ = "0.12.0-test"

    def _make_model(*args, **kwargs):
        model = MagicMock(name="mock_onnx_asr_model")
        if recognize_error is not None:
            model.recognize.side_effect = recognize_error
        else:
            model.recognize.return_value = ""
        return model

    mock.load_model.side_effect = _make_model
    return mock


def _mock_onnxruntime_module() -> MagicMock:
    """Build a MagicMock that quacks like the bits of ``onnxruntime`` we use."""
    mock = MagicMock(name="mock_onnxruntime")
    mock.__version__ = "1.20.0-test"
    mock.get_available_providers.return_value = [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]
    return mock


@pytest.fixture(autouse=True)
def _reset_parakeet_engine_class_state(monkeypatch, tmp_path):
    """Reset ``ParakeetEngine`` class-level state between tests."""
    # load() verifies every snapshot under snapshot_search_dirs; point the
    # search at a tmp snapshot and treat it as verified, so tests never
    # touch the real HF cache (which may be absent/incomplete here).
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
    yield
    (
        ParakeetEngine._imports_loaded,
        ParakeetEngine._onnx_asr,
        ParakeetEngine._ort,
    ) = saved


def _load_with(
    device: str = "cpu",
    recognize_error: Exception | None = None,
) -> tuple[ParakeetEngine, MagicMock, MagicMock, bool]:
    """Run the real ``load()`` against mocked onnx_asr/onnxruntime modules."""
    mock_onnx_asr = _mock_onnx_asr_module(recognize_error)
    mock_onnxruntime = _mock_onnxruntime_module()
    with patch.dict(
        sys.modules,
        {"onnx_asr": mock_onnx_asr, "onnxruntime": mock_onnxruntime},
    ):
        engine = ParakeetEngine(device=device, language="en")
        ParakeetEngine._ensure_imports()
        with (
            patch.object(type(engine), "_is_cached", return_value=True),
            patch.object(type(engine), "_should_force_cpu", return_value=False),
        ):
            loaded = engine.load()
    return engine, mock_onnx_asr, mock_onnxruntime, loaded


class TestParakeetWarmAtLoad:
    """``load()`` pays ORT's lazy first-Run init, the dictation does not."""

    def test_cuda_load_primes_the_session_once_with_the_chunk_shape(self):
        """GPU primes with the real 25 s chunk shape that ``transcribe`` splits to."""
        engine, _, mock_ort, loaded = _load_with(device="cuda")

        assert loaded is True
        mock_ort.get_available_providers.return_value = [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]
        recognize = engine._model.recognize
        recognize.assert_called_once()
        (audio,) = recognize.call_args.args
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32
        assert len(audio) == int(_CHUNK_SECONDS * WHISPER_SAMPLE_RATE), (
            "the GPU prime must match the chunk length real dictation decodes, "
            "otherwise ORT still has to build the shape plan on the first chunk"
        )
        assert recognize.call_args.kwargs == {"sample_rate": WHISPER_SAMPLE_RATE}

    def test_cpu_load_primes_with_a_short_buffer(self):
        """CPU has no shape plan to build, so it must not decode a full chunk."""
        engine, _, _, loaded = _load_with(device="cpu")

        assert loaded is True
        (audio,) = engine._model.recognize.call_args.args
        assert 0 < len(audio) < int(_CHUNK_SECONDS * WHISPER_SAMPLE_RATE)

    def test_warm_failure_does_not_fail_the_load(self):
        """A prime that raises leaves the session usable for the first dictation."""
        engine, _, _, loaded = _load_with(
            device="cpu",
            recognize_error=RuntimeError("ort session init failed"),
        )

        assert loaded is True
        assert engine.is_loaded is True

    def test_second_load_does_not_prime_again(self):
        """Idempotent load: an already-loaded session is not re-warmed."""
        engine, _, _, _ = _load_with(device="cpu")
        recognize = engine._model.recognize
        assert recognize.call_count == 1

        assert engine.load() is True
        assert recognize.call_count == 1


class TestParakeetNoTorchRemnants:
    """The torch path stays removed: priming goes through ``recognize``."""

    def test_engine_has_no_torch_warm_up_model_attribute(self):
        """``_warm_up_model`` was the torch ``generate()`` prime, not this one."""
        engine, _, _, _ = _load_with(device="cpu")
        assert not hasattr(engine, "_warm_up_model"), (
            "ParakeetEngine must NOT have a _warm_up_model method: that was the "
            "torch generate() prime. The ONNX session is primed by _warm_session."
        )
        assert not hasattr(ParakeetEngine, "_warm_up_model")

    def test_engine_has_no_torch_class_attributes(self):
        for attr in ("_torch", "_AutoModelForTDT", "_AutoProcessor", "_hf_home_set"):
            assert not hasattr(ParakeetEngine, attr), (
                f"ParakeetEngine must NOT have a {attr!r} class attribute; "
                f"the ONNX migration removed all torch/transformers references."
            )
