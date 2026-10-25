"""Qwen3-ASR on-disk identity: variant detection, override matching, cache scan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from voice_typer.server import model_availability
from voice_typer.server.qwen_layout import (
    DEFAULT_QWEN_VARIANT,
    VARIANT_HIDDEN_SIZES,
    cached_qwen_model_dir,
    canonical_qwen_name,
    detect_qwen_variant,
    is_complete_qwen_dir,
    is_qwen_variant_name,
    override_matches_variant,
    qwen_repo_id,
    qwen_repo_ids,
    qwen_variant_names,
    read_decoder_hidden_size,
    read_dir_decoder_hidden_size,
    resolve_qwen_model_dir,
)

_PINNED_1_7B = "df916193ac67e59347769891a21e10d81d12acdd"
_REPO_1_7B = "andrewleech/qwen3-asr-1.7b-onnx"
_REPO_0_6B = "andrewleech/qwen3-asr-0.6b-onnx"


def _write_config(directory: Path, payload: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps(payload), encoding="utf-8")
    return directory


def _write_export(directory: Path, *, complete: bool = True) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("encoder.int4.onnx", "embed_tokens.bin", "tokenizer.json", "decoder_init.int4.onnx"):
        (directory / name).write_bytes(b"x")
    if complete:
        (directory / "decoder_step.int4.onnx").write_bytes(b"x")
    return directory


class TestRegistryNames:
    def test_two_variants_are_known(self):
        assert set(qwen_variant_names()) == {"qwen3-1.7b", "qwen3-0.6b"}
        assert is_qwen_variant_name("qwen3-1.7b") is True
        assert is_qwen_variant_name("qwen3-0.6b") is True
        assert is_qwen_variant_name("tiny") is False

    def test_hidden_sizes_match_the_two_exports(self):
        assert VARIANT_HIDDEN_SIZES == {"qwen3-1.7b": 2048, "qwen3-0.6b": 1024}
        assert DEFAULT_QWEN_VARIANT == "qwen3-1.7b"

    def test_repo_ids_come_from_the_registry(self):
        assert qwen_repo_id("qwen3-1.7b") == _REPO_1_7B
        assert qwen_repo_id("qwen3-0.6b") == _REPO_0_6B
        assert qwen_repo_id("tiny") is None
        assert qwen_repo_ids() == (_REPO_1_7B, _REPO_0_6B)

    def test_legacy_keys_still_resolve_to_the_renamed_entries(self):
        assert canonical_qwen_name("qwen") == "qwen3-1.7b"
        assert canonical_qwen_name("qwen-0.6b") == "qwen3-0.6b"
        assert canonical_qwen_name("qwen3-1.7b") == "qwen3-1.7b"
        assert canonical_qwen_name("tiny") is None
        assert is_qwen_variant_name("qwen") is True
        assert qwen_repo_id("qwen") == _REPO_1_7B


class TestReadDecoderHiddenSize:
    @pytest.mark.parametrize("width", [2048, 1024])
    def test_reads_decoder_block(self, width):
        assert read_decoder_hidden_size({"decoder": {"hidden_size": width}}) == width

    def test_falls_back_to_text_config_then_top_level(self):
        assert read_decoder_hidden_size({"text_config": {"hidden_size": 1024}}) == 1024
        assert read_decoder_hidden_size({"hidden_size": 2048}) == 2048

    @pytest.mark.parametrize("payload", [{}, {"decoder": {"hidden_size": 0}}, {"decoder": {"hidden_size": "2048"}}])
    def test_rejects_missing_or_non_positive_values(self, payload):
        assert read_decoder_hidden_size(payload) is None

    def test_dir_reader_handles_absent_and_corrupt_files(self, tmp_path):
        assert read_dir_decoder_hidden_size(tmp_path) is None
        (tmp_path / "config.json").write_text("{not json", encoding="utf-8")
        assert read_dir_decoder_hidden_size(tmp_path) is None
        _write_config(tmp_path / "ok", {"decoder": {"hidden_size": 1024}})
        assert read_dir_decoder_hidden_size(tmp_path / "ok") == 1024


class TestDetectVariant:
    def test_17b_width_is_the_1_7b_entry(self, tmp_path):
        assert detect_qwen_variant(_write_config(tmp_path / "a", {"decoder": {"hidden_size": 2048}})) == "qwen3-1.7b"

    def test_06b_width_is_the_0_6b_entry(self, tmp_path):
        assert detect_qwen_variant(_write_config(tmp_path / "b", {"decoder": {"hidden_size": 1024}})) == "qwen3-0.6b"

    def test_unknown_width_is_unidentified(self, tmp_path):
        assert detect_qwen_variant(_write_config(tmp_path / "c", {"decoder": {"hidden_size": 4096}})) is None
        assert detect_qwen_variant(tmp_path / "missing") is None


class TestOverrideMatching:
    def test_empty_or_non_string_override_never_matches(self):
        assert override_matches_variant("qwen3-1.7b", None) is False
        assert override_matches_variant("qwen3-1.7b", "") is False
        assert override_matches_variant("qwen3-1.7b", 42) is False

    def test_missing_directory_never_matches(self, tmp_path):
        assert override_matches_variant("qwen3-1.7b", str(tmp_path / "nope")) is False

    def test_identified_override_matches_only_its_variant(self, tmp_path):
        small = _write_config(tmp_path / "small", {"decoder": {"hidden_size": 1024}})
        assert override_matches_variant("qwen3-0.6b", str(small)) is True
        assert override_matches_variant("qwen3-1.7b", str(small)) is False

    def test_unidentified_override_is_assumed_to_be_the_default_variant(self, tmp_path):
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        assert override_matches_variant("qwen3-1.7b", str(legacy)) is True
        assert override_matches_variant("qwen3-0.6b", str(legacy)) is False


class TestCompleteDir:
    def test_requires_every_loader_file(self, tmp_path):
        assert is_complete_qwen_dir(_write_export(tmp_path / "full")) is True
        assert is_complete_qwen_dir(_write_export(tmp_path / "partial", complete=False)) is False
        assert is_complete_qwen_dir(tmp_path / "absent") is False

    def test_accepts_unquantized_session_files(self, tmp_path):
        export = tmp_path / "fp32"
        export.mkdir()
        for name in (
            "encoder.onnx",
            "embed_tokens.bin",
            "tokenizer.json",
            "decoder_init.onnx",
            "decoder_step.onnx",
        ):
            (export / name).write_bytes(b"x")
        assert is_complete_qwen_dir(export) is True


class TestCachedModelDir:
    @pytest.fixture(autouse=True)
    def _isolated_hub(self, tmp_path, monkeypatch):
        hub = tmp_path / "hub"
        hub.mkdir()
        monkeypatch.setattr(model_availability, "shared_hub_dir", lambda: hub)
        return hub

    def test_finds_the_pinned_snapshot(self, tmp_path, _isolated_hub):
        snapshot = _write_export(
            _isolated_hub / "models--andrewleech--qwen3-asr-1.7b-onnx" / "snapshots" / _PINNED_1_7B
        )
        found = cached_qwen_model_dir(_REPO_1_7B)
        assert found == snapshot

    def test_ignores_incomplete_snapshots(self, tmp_path, _isolated_hub):
        _write_export(
            _isolated_hub / "models--andrewleech--qwen3-asr-1.7b-onnx" / "snapshots" / _PINNED_1_7B,
            complete=False,
        )
        assert cached_qwen_model_dir(_REPO_1_7B) is None

    def test_other_repo_is_not_shared(self, tmp_path, _isolated_hub):
        _write_export(_isolated_hub / "models--andrewleech--qwen3-asr-1.7b-onnx" / "snapshots" / _PINNED_1_7B)
        assert cached_qwen_model_dir(_REPO_0_6B) is None


class TestResolveModelDir:
    @pytest.fixture(autouse=True)
    def _isolated_hub(self, tmp_path, monkeypatch):
        hub = tmp_path / "hub"
        hub.mkdir()
        monkeypatch.setattr(model_availability, "shared_hub_dir", lambda: hub)
        monkeypatch.setattr("voice_typer.server.config._config_dir", lambda: tmp_path / "config")
        return hub

    def test_matching_override_wins(self, tmp_path):
        override = _write_config(tmp_path / "override", {"decoder": {"hidden_size": 1024}})
        assert resolve_qwen_model_dir("qwen3-0.6b", str(override)) == str(override)

    def test_non_matching_override_falls_back_to_the_cache(self, tmp_path):
        override = _write_config(tmp_path / "override", {"decoder": {"hidden_size": 1024}})
        assert resolve_qwen_model_dir("qwen3-1.7b", str(override)) is None

    def test_cache_is_used_when_no_override(self, tmp_path, _isolated_hub):
        snapshot = _write_export(_isolated_hub / "models--andrewleech--qwen3-asr-0.6b-onnx" / "snapshots" / "rev1")
        assert resolve_qwen_model_dir("qwen3-0.6b", None) == str(snapshot)

    def test_unknown_name_resolves_to_the_default_variant(self, tmp_path):
        override = _write_config(tmp_path / "override", {"decoder": {"hidden_size": 2048}})
        assert resolve_qwen_model_dir(None, str(override)) == str(override)
        assert resolve_qwen_model_dir("not-a-model", str(override)) == str(override)
