"""Catalogue tests: real hashes/sizes, five production models, dev-only tiny."""

from __future__ import annotations

import re

import pytest
from voice_typer.server import gguf_model_registry as registry
from voice_typer.server.gguf_model_registry import (
    DEFAULT_MODEL_KEY,
    GGUF_MODELS,
    PRODUCTION_MODEL_KEYS,
    all_placeholders,
    available_models,
    is_placeholder_hash,
    is_placeholder_size,
    is_registered_model_key,
    production_models,
    require_complete_spec,
    resolve_gguf_spec,
)

EXPECTED = {
    "parakeet": (
        "parakeet-ultra-Q8_0.gguf",
        740_363_168,
        "007a59761e9258779f189df396b50d12b83bb5b79e66df4b955c230d2f2a0a59",
    ),
    "large-v3-turbo": (
        "whisper-large-v3-turbo-Q8_0.gguf",
        886_381_728,
        "257aa7ec9121c22c167d5e2c49e3e76b4ba0e6e27ebc13074eba0a80f8190220",
    ),
    "qwen3-1.7b": (
        "Qwen3-ASR-1.7B-Q4_K_M.gguf",
        1_319_830_496,
        "b7afe3674f653fa84f712ed2440353c6e7cf7f93697fef76b05a26538b24844e",
    ),
    "qwen3-0.6b": (
        "Qwen3-ASR-0.6B-Q8_0.gguf",
        850_423_456,
        "f081b2d5e23bd669d92cc331d722a8a0681943b8e6f34b48996fd5c319b5acd8",
    ),
    "large-v3": (
        "whisper-large-v3-Q6_K.gguf",
        1_297_130_208,
        "88e6dc60bd0538da145a50c19f4778e4a106fe28713adeeca43163215ee02805",
    ),
}


def test_no_placeholders_or_invalid_values() -> None:
    assert all_placeholders() == ()
    for spec in GGUF_MODELS.values():
        assert re.fullmatch(r"[0-9a-f]{64}", spec.sha256), spec.model_key
        assert spec.size_bytes > 0, spec.model_key
        require_complete_spec(spec)


def test_production_catalogue_is_exactly_the_five_owner_models() -> None:
    assert set(production_models()) == PRODUCTION_MODEL_KEYS
    assert set(PRODUCTION_MODEL_KEYS) == set(EXPECTED)
    assert "tiny" not in production_models()
    assert DEFAULT_MODEL_KEY in PRODUCTION_MODEL_KEYS


def test_exact_files_sizes_and_hashes() -> None:
    for key, (filename, size, digest) in EXPECTED.items():
        spec = resolve_gguf_spec(key, allow_dev=False)
        assert (spec.filename, spec.size_bytes, spec.sha256) == (filename, size, digest)
        assert spec.repo_id.startswith("handy-computer/")


def test_tiny_is_dev_only_and_not_production() -> None:
    spec = resolve_gguf_spec("tiny", allow_dev=True)
    assert spec.dev_only
    assert spec.filename == "whisper-tiny-Q8_0.gguf"
    assert spec.size_bytes == 45_981_088
    with pytest.raises(KeyError):
        resolve_gguf_spec("tiny", allow_dev=False)


def test_available_models_respects_frozen_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "is_frozen", lambda: True)
    assert "tiny" not in available_models()
    monkeypatch.setattr(registry, "is_frozen", lambda: False)
    assert "tiny" in available_models()


def test_registered_model_key_predicate_matches_the_build_catalogue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch asks the registry, never the raw GGUF_MODELS dict."""
    assert is_registered_model_key(DEFAULT_MODEL_KEY)
    assert not is_registered_model_key("not-a-model")
    monkeypatch.setattr(registry, "is_frozen", lambda: True)
    assert not is_registered_model_key("tiny")
    monkeypatch.setattr(registry, "is_frozen", lambda: False)
    assert is_registered_model_key("tiny")


def test_placeholder_classifiers_reject_garbage() -> None:
    assert is_placeholder_hash("FILL_ME")
    assert not is_placeholder_hash("a" * 64)
    assert is_placeholder_size(None) and is_placeholder_size(0)
    assert not is_placeholder_size(1)


def test_frozen_default_and_catalogue_are_production_only() -> None:
    from voice_typer.server.gguf_model_registry import (
        default_model_size_for_build,
        get_all_models,
        get_model_metadata,
    )

    assert default_model_size_for_build(frozen=True) == DEFAULT_MODEL_KEY
    assert default_model_size_for_build(frozen=False) == ""
    assert set(production_models()) == PRODUCTION_MODEL_KEYS
    if registry.is_frozen():
        assert get_model_metadata("tiny") is None
        assert "tiny" not in {meta.name for meta in get_all_models()}
    else:
        assert get_model_metadata("tiny") is not None


def test_metadata_derives_every_authoritative_field_from_gguf_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UI/API metadata must never restate size, repo id or family by hand."""
    from dataclasses import replace

    monkeypatch.setattr(registry, "is_frozen", lambda: False)
    metadata = registry.available_model_metadata()
    assert set(metadata) == set(GGUF_MODELS)
    for key, spec in GGUF_MODELS.items():
        meta = metadata[key]
        assert meta.name == spec.model_key
        assert meta.download_size_mb == spec.size_bytes // 1_000_000
        assert meta.repo_id == spec.repo_id
        assert meta.backend == spec.family
        changed = registry._metadata_for_spec(replace(spec, size_bytes=spec.size_bytes + 1_000_000))
        assert changed.download_size_mb == meta.download_size_mb + 1
        changed = registry._metadata_for_spec(replace(spec, repo_id="example/new-repo"))
        assert changed.repo_id == "example/new-repo"


def test_production_metadata_has_no_dev_model_or_legacy_repo() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(registry, "is_frozen", lambda: True)
    try:
        metadata = registry.available_model_metadata()
        assert registry.get_all_models() == list(metadata.values())
    finally:
        monkeypatch.undo()
    assert set(metadata) == PRODUCTION_MODEL_KEYS
    assert "tiny" not in metadata
    from voice_typer.server.gguf_model_registry import LEGACY_REPO_ID_KEYS

    for meta in metadata.values():
        assert meta.repo_id.startswith("handy-computer/")
        assert meta.repo_id not in LEGACY_REPO_ID_KEYS
        assert "onnx" not in meta.repo_id.lower()


def test_client_sample_size_matches_the_downloaded_byte_size() -> None:
    """The skeleton and the download button show the registry's byte size."""
    from pathlib import Path

    sample = (
        Path(registry.__file__).parents[1]
        / "client"
        / "src"
        / "renderer"
        / "src"
        / "pages"
        / "models"
        / "lib"
        / "sample.ts"
    ).read_text(encoding="utf-8")
    shown = dict(re.findall(r'name: "([^"]+)",\s*\n\s*display_name:.*?\n\s*download_size_mb: (\d+)', sample))
    shown.update(dict(re.findall(r'name: "([^"]+)",\s*\n\s*download_size_mb: (\d+)', sample)))
    for key, spec in GGUF_MODELS.items():
        if spec.dev_only:
            continue
        assert shown.get(key) == str(spec.size_bytes // 1_000_000), key


def test_only_the_registry_module_reads_raw_gguf_models() -> None:
    """AST scan: every other production module goes through the catalogue API."""
    import ast
    from pathlib import Path

    server_dir = Path(registry.__file__).parent
    registry_file = Path(registry.__file__).resolve()
    offenders: list[str] = []
    for path in server_dir.rglob("*.py"):
        if path.resolve() == registry_file:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.Attribute):
                names.append(node.attr)
            if "GGUF_MODELS" in names:
                offenders.append(f"{path.relative_to(server_dir)}:{node.lineno}")
                break
    assert offenders == [], f"raw GGUF_MODELS readers: {offenders}"

    shim = (server_dir / "model_registry.py").read_text(encoding="utf-8")
    shim_tree = ast.parse(shim)
    assert not any(isinstance(node, ast.ClassDef) for node in shim_tree.body), (
        "model_registry.py must stay a pure re-export shim"
    )
    assert not any(
        isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODEL_REGISTRY" for t in node.targets)
        for node in shim_tree.body
    ), "model_registry.py must not define another MODEL_REGISTRY"
