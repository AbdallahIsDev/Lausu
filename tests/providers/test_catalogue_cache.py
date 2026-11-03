"""Catalogue cache: TTL freshness and stale-tolerant reads."""

from __future__ import annotations

from pathlib import Path

from voice_typer.server.model_providers.catalogue import CatalogueCache


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    cache = CatalogueCache(tmp_path / "catalogue.json", ttl_seconds=60)
    cache.write("openrouter", [{"id": "a/b", "domains": ["llm"]}])
    snap = cache.read("openrouter")
    assert snap is not None
    assert snap.model_ids() == ["a/b"]
    assert snap.stale is False


def test_a_stale_snapshot_still_serves_the_selected_id(tmp_path: Path) -> None:
    cache = CatalogueCache(tmp_path / "catalogue.json", ttl_seconds=0)
    cache.write("openrouter", [{"id": "old/model", "domains": ["llm"]}])
    snap = cache.read("openrouter")
    assert snap is not None
    assert snap.stale is True
    assert "old/model" in snap.model_ids()


def test_persisted_cache_survives_a_new_instance(tmp_path: Path) -> None:
    path = tmp_path / "catalogue.json"
    CatalogueCache(path, ttl_seconds=60).write("ollama", [{"id": "llama3"}])
    assert CatalogueCache(path).read("ollama").model_ids() == ["llama3"]


def test_invalidate_drops_one_provider_only(tmp_path: Path) -> None:
    cache = CatalogueCache(tmp_path / "catalogue.json")
    cache.write("a", [{"id": "a1"}])
    cache.write("b", [{"id": "b1"}])
    cache.invalidate("a")
    assert cache.read("a") is None
    assert cache.read("b").model_ids() == ["b1"]


def test_corrupt_cache_file_is_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "catalogue.json"
    path.write_text("{not json", encoding="utf-8")
    assert CatalogueCache(path).read("x") is None
