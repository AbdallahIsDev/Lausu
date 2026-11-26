"""Frozen-build rule: dev-only tiny never reaches a production surface."""

from __future__ import annotations

import json

import pytest
from voice_typer.server import gguf_model_registry as registry
from voice_typer.server.gguf_model_registry import (
    DEFAULT_MODEL_KEY,
    LEGACY_REPO_ID_KEYS as _LEGACY_IDS,
    PRODUCTION_MODEL_KEYS,
    get_all_models,
    get_model_metadata,
)


def _legacy_id(key: str) -> str:
    """Old repo ids live in the one migration map; never duplicate them here."""
    return next(repo for repo, mapped in _LEGACY_IDS.items() if mapped == key)


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "is_frozen", lambda: True)


def test_frozen_catalogue_and_metadata_drop_tiny(frozen: None) -> None:
    assert set(registry.available_models()) == PRODUCTION_MODEL_KEYS
    assert set(registry.production_models()) == PRODUCTION_MODEL_KEYS
    assert "tiny" not in {meta.name for meta in get_all_models()}
    assert get_model_metadata("tiny") is None
    assert get_model_metadata("large-v3-turbo") is not None


def test_frozen_default_is_a_production_model(frozen: None) -> None:
    from voice_typer.server.gguf_model_registry import default_model_size_for_build

    assert default_model_size_for_build() == DEFAULT_MODEL_KEY
    assert DEFAULT_MODEL_KEY in registry.production_models()


def test_frozen_config_migrates_dev_legacy_empty_and_unknown(tmp_config_dir, frozen: None) -> None:
    from voice_typer.server.config import Config

    for stored in ("tiny", _legacy_id("tiny"), "", "unregistered-id"):
        config_file = tmp_config_dir / "config.json"
        config_file.write_text(
            json.dumps({"schema_version": 8, "model_size": stored}),
            encoding="utf-8",
        )
        loaded = Config.load()
        assert loaded.model_size == DEFAULT_MODEL_KEY, (stored, loaded.model_size)


def test_frozen_download_endpoint_refuses_dev_model_without_network(
    frozen: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from voice_typer.server.service.model._download_dispatch import DownloadDispatchMixin

    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no download branch may run for a dev-only model")

    class _Service(DownloadDispatchMixin):
        def _download_whisper_family(self, *_args: object, **_kwargs: object):
            _forbidden()

        def _download_qwen(self, *_args: object, **_kwargs: object):
            _forbidden()

        def _download_parakeet(self, *_args: object, **_kwargs: object):
            _forbidden()

        def _download_translation(self, *_args: object, **_kwargs: object):
            _forbidden()

        def _start_next_queued_download(self) -> None:
            return None

    result = _Service().download_model("tiny")
    assert result["success"] is False
    assert result["error"] == "dev_model_not_allowed"
    assert result["code"] == "server.dev_model_not_allowed"


def test_frozen_gguf_download_refuses_without_network(
    frozen: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from voice_typer.server import gguf_download

    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network path reached for a dev-only model")

    monkeypatch.setattr(gguf_download, "ensure_hf_env", _forbidden)
    ok, code = gguf_download.download_gguf_model(
        "tiny", config=SimpleNamespace(huggingface_consent=True)
    )
    assert (ok, code) == (False, "dev_model_not_allowed")


def test_source_catalogue_still_offers_tiny() -> None:
    if registry.is_frozen():
        pytest.skip("source-build check")
    assert "tiny" in registry.available_models()
    tiny = registry.resolve_gguf_spec("tiny", allow_dev=True)
    assert tiny.size_bytes == 45_981_088
    assert tiny.sha256 == "325b9c7997cd1eff81ef709d55766565e71be696130cc3a3d444713798706834"
