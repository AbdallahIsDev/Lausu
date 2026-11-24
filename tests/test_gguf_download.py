"""Download wiring tests: consent, verification, local-only inference lookup."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from voice_typer.server import gguf_download
from voice_typer.server.gguf_model_registry import GgufModelSpec


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
        family="whisper",
        quantization="Q8_0",
    )
    return spec, file_path


def _use_spec(monkeypatch: pytest.MonkeyPatch, spec: GgufModelSpec) -> None:
    """Inject a resolved spec at the downloader seam (no raw catalogue writes)."""
    monkeypatch.setattr(gguf_download, "resolve_gguf_spec", lambda _key, **_kw: spec)


def test_placeholder_refuses_before_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec, _ = _real_spec(tmp_path)
    placeholder = GgufModelSpec(**{**spec.__dict__, "sha256": "FILL_ME"})
    _use_spec(monkeypatch, placeholder)
    hub = _FakeHub(tmp_path / "unused.gguf")
    _install_hub(monkeypatch, hub)
    ok, code = gguf_download.download_gguf_model("tiny", config=SimpleNamespace(huggingface_consent=True))
    assert (ok, code) == (False, "placeholder_in_registry")
    assert hub.calls == []


def test_dev_only_model_refused_in_frozen_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gguf_download, "_frozen", lambda: True)
    hub = _FakeHub(tmp_path / "unused.gguf")
    _install_hub(monkeypatch, hub)
    ok, code = gguf_download.download_gguf_model("tiny", config=SimpleNamespace(huggingface_consent=True))
    assert (ok, code) == (False, "dev_model_not_allowed")
    assert hub.calls == []


def test_consent_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec, path = _real_spec(tmp_path)
    _use_spec(monkeypatch, spec)
    hub = _FakeHub(path)
    _install_hub(monkeypatch, hub)
    ok, code = gguf_download.download_gguf_model("tiny", config=SimpleNamespace(huggingface_consent=False))
    assert (ok, code) == (False, "huggingface_consent_false")
    assert hub.calls == []


def test_cached_model_passes_without_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec, path = _real_spec(tmp_path)
    _use_spec(monkeypatch, spec)
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
        _use_spec(monkeypatch, bad_spec)
        hub = _FakeHub(tmp_path / "downloaded.gguf")
        (tmp_path / "downloaded.gguf").write_bytes(path.read_bytes())
        _install_hub(monkeypatch, hub)
        ok, code = gguf_download.download_gguf_model("tiny", config=SimpleNamespace(huggingface_consent=True))
        assert (ok, code) == (False, expected)


def test_transport_error_propagates_for_friendly_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The dispatcher owns user-facing error text, so the real cause must escape."""
    spec, _ = _real_spec(tmp_path)
    _use_spec(monkeypatch, spec)

    def failing_download(**kwargs):
        raise ConnectionError("[Errno 11001] getaddrinfo failed")

    hub = ModuleType("huggingface_hub")
    hub.hf_hub_download = failing_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setattr(gguf_download, "ensure_hf_env", lambda: None)

    with pytest.raises(ConnectionError, match="getaddrinfo failed"):
        gguf_download.download_gguf_model("tiny", config=SimpleNamespace(huggingface_consent=True))


def test_gated_tqdm_class_is_forwarded_to_the_transfer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spec, path = _real_spec(tmp_path)
    _use_spec(monkeypatch, spec)
    calls: list[dict] = []

    def fake_download(**kwargs):
        calls.append(kwargs)
        if kwargs.get("local_files_only"):
            raise FileNotFoundError("not cached")
        return str(path)

    hub = ModuleType("huggingface_hub")
    hub.hf_hub_download = fake_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setattr(gguf_download, "ensure_hf_env", lambda: None)

    class GatedTqdm:
        pass

    ok, code = gguf_download.download_gguf_model(
        "tiny", config=SimpleNamespace(huggingface_consent=True), tqdm_class=GatedTqdm
    )
    assert (ok, code) == (True, "")
    assert calls[-1]["tqdm_class"] is GatedTqdm


def test_inference_lookup_is_local_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec, path = _real_spec(tmp_path)
    _use_spec(monkeypatch, spec)
    hub = _FakeHub(path)
    _install_hub(monkeypatch, hub)
    assert gguf_download.resolve_gguf_model_path("tiny") == path
    assert hub.calls == [{"repo_id": spec.repo_id, "filename": spec.filename, "local_files_only": True}]


def test_expected_cache_misses_do_not_dump_tracebacks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    spec, _ = _real_spec(tmp_path)
    _use_spec(monkeypatch, spec)
    hub = _FakeHub(tmp_path / "missing.gguf")
    _install_hub(monkeypatch, hub)

    with caplog.at_level("DEBUG", logger="voice_typer.server.gguf_download"):
        assert gguf_download.resolve_gguf_model_path("parakeet") is None
    records = [r for r in caplog.records if r.name == "voice_typer.server.gguf_download"]
    assert len(records) == 1
    assert "not in local cache" in records[0].getMessage()
    assert records[0].exc_info is None, "an expected cache miss must not print a traceback"


def test_install_from_file_lands_in_the_cache_the_downloader_reads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import huggingface_hub.constants as hf_constants

    spec, source = _real_spec(tmp_path)
    _use_spec(monkeypatch, spec)
    monkeypatch.setattr(gguf_download, "ensure_hf_env", lambda: None)
    cache = tmp_path / "cache"
    monkeypatch.setattr(hf_constants, "HF_HUB_CACHE", str(cache))
    monkeypatch.setenv("HF_HUB_DISABLE_SYMLINKS", "1")

    assert gguf_download.install_gguf_model_from_file("parakeet", source, cache_dir=cache) == (True, "")
    assert gguf_download.resolve_gguf_model_path("parakeet") == (
        cache / f"models--{spec.repo_id.replace('/', '--')}" / "snapshots" / spec.sha256[:40] / spec.filename
    )


def test_install_from_file_refuses_unverified_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec, source = _real_spec(tmp_path)
    _use_spec(monkeypatch, spec)
    monkeypatch.setattr(gguf_download, "ensure_hf_env", lambda: None)
    cache = tmp_path / "cache"
    for spec_override, expected in (
        (GgufModelSpec(**{**spec.__dict__, "size_bytes": 999}), "size_mismatch"),
        (GgufModelSpec(**{**spec.__dict__, "sha256": "b" * 64}), "sha256_mismatch"),
    ):
        _use_spec(monkeypatch, spec_override)
        assert gguf_download.install_gguf_model_from_file("parakeet", source, cache_dir=cache) == (
            False,
            expected,
        )
    assert gguf_download.install_gguf_model_from_file("parakeet", tmp_path / "missing.gguf", cache_dir=cache) == (
        False,
        "source_missing",
    )
    assert not cache.exists()
