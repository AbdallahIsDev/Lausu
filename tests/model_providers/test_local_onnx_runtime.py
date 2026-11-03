"""Local ONNX model directory + generation-loop contracts.

No 1.76 GB download and no ``onnx`` package: the graph contract is exercised
through a fake session that exposes the same names/shapes, plus real files for
the resolver/manifest paths.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from voice_typer.server.model_providers.errors import ProviderRuntimeError
from voice_typer.server.model_providers.local_onnx.generation import (
    KvShape,
    generate,
    kv_shape_from_session,
)
from voice_typer.server.model_providers.local_onnx.models import (
    LocalOnnxModel,
    list_installed_models,
    load_model,
    verify_manifest,
)


def _export(root: Path, *, eos: tuple[int, ...] | None = (1, 130073)) -> Path:
    model = root / "MiniCPM5-2B-ONNX"
    (model / "onnx").mkdir(parents=True)
    (model / "onnx" / "model_q4f16.onnx").write_bytes(b"graph-bytes")
    (model / "onnx" / "model_q4f16.onnx_data").write_bytes(b"weights-0")
    (model / "onnx" / "model_q4f16.onnx_data_1").write_bytes(b"weights-1")
    (model / "tokenizer.json").write_text("{}", encoding="utf-8")
    (model / "chat_template.jinja").write_text("{{ messages }}", encoding="utf-8")
    if eos is not None:
        (model / "generation_config.json").write_text(json.dumps({"eos_token_id": list(eos)}), encoding="utf-8")
    files = {}
    for rel in (
        "tokenizer.json",
        "onnx/model_q4f16.onnx",
        "onnx/model_q4f16.onnx_data",
        "onnx/model_q4f16.onnx_data_1",
    ):
        payload = (model / rel).read_bytes()
        files[rel] = {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    if eos is not None:
        payload = (model / "generation_config.json").read_bytes()
        files["generation_config.json"] = {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    (model / "manifest.json").write_text(json.dumps({"model_id": "minicpm5-2b", "files": files}), encoding="utf-8")
    return model


def test_recursive_graph_resolution_and_generation_config_eos(tmp_path: Path) -> None:
    model_dir = _export(tmp_path)
    model = LocalOnnxModel(model_id="minicpm5-2b", path=model_dir, manifest={})

    assert model.onnx_path == model_dir / "onnx" / "model_q4f16.onnx"
    assert model.eos_ids == (1, 130073)


def test_eos_falls_back_to_manifest_then_export_default(tmp_path: Path) -> None:
    model_dir = _export(tmp_path / "a", eos=None)
    from_manifest = LocalOnnxModel(model_id="m", path=model_dir, manifest={"eos_ids": [42]})
    assert from_manifest.eos_ids == (42,)

    default = LocalOnnxModel(model_id="m", path=model_dir, manifest={})
    assert default.eos_ids == (1, 130073)


def test_missing_graph_error_names_what_was_found(tmp_path: Path) -> None:
    model_dir = tmp_path / "broken"
    (model_dir / "onnx").mkdir(parents=True)
    (model_dir / "onnx" / "decoder_model.onnx").write_bytes(b"x")

    model = LocalOnnxModel(model_id="broken", path=model_dir, manifest={})
    with pytest.raises(ProviderRuntimeError, match="decoder_model.onnx"):
        _ = model.onnx_path


def test_listing_only_advertises_loadable_models(tmp_path: Path) -> None:
    root = tmp_path / "models"
    _export(root)
    no_graph = root / "manifest-only"
    no_graph.mkdir()
    (no_graph / "tokenizer.json").write_text("{}", encoding="utf-8")
    (no_graph / "manifest.json").write_text(json.dumps({"files": {}}), encoding="utf-8")

    listed = [model.id for model in list_installed_models(root)]

    assert listed == ["MiniCPM5-2B-ONNX"]


def test_listing_accepts_the_model_directory_itself(tmp_path: Path) -> None:
    model_dir = _export(tmp_path)

    assert [model.id for model in list_installed_models(model_dir)] == ["MiniCPM5-2B-ONNX"]


def test_load_model_verifies_and_reports_eos(tmp_path: Path) -> None:
    model = load_model(_export(tmp_path))

    assert model.model_id == "minicpm5-2b"
    assert model.verified_files == 5
    assert model.eos_ids == (1, 130073)


def test_hot_manifest_verification_is_cached(tmp_path: Path) -> None:
    model_dir = _export(tmp_path)

    assert verify_manifest(model_dir)[0] is True
    started = time.perf_counter()
    ok, reason, checked = verify_manifest(model_dir)
    elapsed = time.perf_counter() - started

    assert (ok, reason, checked) == (True, "", 5)
    assert elapsed < 0.05, f"second verify_manifest took {elapsed:.3f}s; the digest cache is not warm"


class _Tensor:
    def __init__(self, name: str, shape: list, type_name: str = "tensor(float16)") -> None:
        self.name = name
        self.shape = shape
        self.type = type_name


class _Value:
    def __init__(self, array: np.ndarray) -> None:
        self._array = array

    def numpy(self) -> np.ndarray:
        return self._array


class _FakeOrt:
    class OrtValue:
        @staticmethod
        def ortvalue_from_numpy(array: np.ndarray, device: str = "cpu") -> _Value:
            return _Value(array)


class _Binding:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def bind_cpu_input(self, name: str, value: np.ndarray) -> None:
        self._session.feeds[name] = value

    def bind_ortvalue_input(self, name: str, value: object) -> None:
        self._session.feeds[name] = value

    def bind_output(self, name: str, device: str | None = None) -> None:
        self._session.output_names.append(name)

    def get_outputs(self) -> list:
        return self._session.produced[-1]


class _FakeSession:
    """Same input names/shapes as the export, deterministic scripted logits."""

    def __init__(
        self,
        scripted: list[int],
        *,
        layers: int = 2,
        heads: int = 2,
        head_dim: int = 8,
        vocab: int = 32,
    ) -> None:
        self.scripted = list(scripted)
        self.layers = layers
        self.heads = heads
        self.head_dim = head_dim
        self.vocab = vocab
        self.feeds: dict[str, object] = {}
        self.output_names: list[str] = []
        self.produced: list[list] = []
        self.step = 0
        self._inputs = [
            _Tensor("input_ids", [1, "S"], "tensor(int64)"),
            _Tensor("attention_mask", [1, "T"], "tensor(int64)"),
        ]
        for index in range(layers):
            for suffix in ("key", "value"):
                self._inputs.append(_Tensor(f"past_key_values.{index}.{suffix}", [1, heads, "past", head_dim]))

    def get_inputs(self) -> list[_Tensor]:
        return self._inputs

    def io_binding(self) -> _Binding:
        return _Binding(self)

    def run_with_iobinding(self, binding: _Binding) -> None:
        token = self.scripted[min(self.step, len(self.scripted) - 1)]
        logits = np.full((1, 1, self.vocab), -5.0, dtype=np.float16)
        logits[0, 0, token] = 5.0
        past = [_Value(np.zeros((1, self.heads, 1, self.head_dim), dtype=np.float16)) for _ in range(self.layers * 2)]
        self.produced.append([_Value(logits), *past])
        self.step += 1


def test_kv_geometry_comes_from_the_graph() -> None:
    first = kv_shape_from_session(_FakeSession([], layers=3, heads=2, head_dim=128))
    second = kv_shape_from_session(_FakeSession([], layers=4, heads=1, head_dim=64))

    assert first == KvShape(layers=3, heads=2, head_dim=128, dtype=np.float16)
    assert (second.layers, second.heads, second.head_dim) == (4, 1, 64)


def test_kv_geometry_returns_none_without_kv_inputs() -> None:
    class _NoKv:
        def get_inputs(self) -> list[_Tensor]:
            return [_Tensor("input_ids", [1, "S"], "tensor(int64)")]

    assert kv_shape_from_session(_NoKv()) is None


def test_greedy_decode_uses_graph_geometry_and_stops_at_eos() -> None:
    session = _FakeSession([5, 6, 9])

    produced = generate(
        session=session,
        ort=_FakeOrt,
        prompt_ids=[3, 4],
        max_new_tokens=8,
        eos_ids=(9,),
        temperature=0.0,
        kv_shape=kv_shape_from_session(session),
    )

    assert produced == [5, 6, 9]
    assert session.step == 3


def test_abort_stops_before_the_first_step() -> None:
    session = _FakeSession([5])
    abort = threading.Event()
    abort.set()

    assert generate(session=session, ort=_FakeOrt, prompt_ids=[1], abort_event=abort) == []
    assert session.step == 0
