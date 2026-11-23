"""Download wiring tests: consent, verification, local-only inference lookup."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from voice_typer.server import gguf_download
from voice_typer.server.gguf_model_registry import GGUF_MODELS, GgufModelSpec


class _FakeHub:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.calls: list[dict] = []

    def hf_hub_download(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("local_files_only"):
            if self.path.is_file():
                return str(self.path)
            raise FileNotFoundError("not cached")
        return str(self.path)


def _install_hub(monkeypatch: pytest.MonkeyPatch, hub: _FakeHub) -> None:
    module = ModuleType("huggingface_hub")
    module.hf_hub_download = hub.hf_hub_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    monkeypatch.setattr(gguf_download, "ensure_hf_env", lambda: None)


def _real_spec(tmp_path: Path, payload: bytes = b"gguf-bytes") -> tuple[GgufModelSpec, Path]:
    file_path = tmp_path / "model.gguf"
    file_path.write_bytes(payload)
    spec = GgufModelSpec(
        model_key="tiny",
        repo_id="handy-computer/whisper-tiny-gguf",
        filename="whisper-tiny-Q8_0.gguf",
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        license="MIT",
    )
    return spec, file_path


def test_placeholder_refuses_before_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hub = _FakeHub(tmp_path / "unused.gguf")
    _install_hub(monkeypatch, hub)
    ok, code = gguf_download.download_gguf_model("tiny", config=SimpleNamespace(huggingface_consent=True))
    assert (ok, code) == (False, "placeholder_in_registry")
    assert hub.calls == []


def test_consent_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec, path = _real_spec(tmp_path)
    monkeypatch.setitem(GGUF_MODELS, "tiny", spec)
    hub = _FakeHub(path)
    _install_hub(monkeypatch, hub)
    ok, code = gguf_download.download_gguf_model("tiny", config=SimpleNamespace(huggingface_consent=False))
    assert (ok, code) == (False, "huggingface_consent_false")
    assert hub.calls == []


def test_cached_model_passes_without_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec, path = _real_spec(tmp_path)
    monkeypatch.setitem(GGUF_MODELS, "tiny", spec)
    hub = _FakeHub(path)
    _install_hub(monkeypatch, hub)
    ok, code = gguf_download.download_gguf_model("tiny", config=SimpleNamespace(huggingface_consent=True))
    assert (ok, code) == (True, "")
    assert hub.calls and hub.calls[0]["local_files_only"] is True
    assert all("local_files_only" in call for call in hub.calls)


def test_mismatch_codes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec, path = _real_spec(tmp_path)
    for bad_spec, expected in (
        (GgufModelSpec(**{**spec.__dict__, "size_bytes": 999}), "size_mismatch"),
        (GgufModelSpec(**{**spec.__dict__, "sha256": "b" * 64}), "sha256_mismatch"),
    ):
        monkeypatch.setitem(GGUF_MODELS, "tiny", bad_spec)
        # No local file: force the download branch.
        hub = _FakeHub(tmp_path / "downloaded.gguf")
        (tmp_path / "downloaded.gguf").write_bytes(path.read_bytes())
        _install_hub(monkeypatch, hub)
        ok, code = gguf_download.download_gguf_model("tiny", config=SimpleNamespace(huggingface_consent=True))
        assert (ok, code) == (False, expected)


def test_inference_lookup_is_local_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec, path = _real_spec(tmp_path)
    monkeypatch.setitem(GGUF_MODELS, "tiny", spec)
    hub = _FakeHub(path)
    _install_hub(monkeypatch, hub)
    assert gguf_download.resolve_gguf_model_path("tiny") == path
    assert hub.calls == [{"repo_id": spec.repo_id, "filename": spec.filename, "local_files_only": True}]
