"""Tests for TTS artifact verify-before-use."""

from __future__ import annotations

from pathlib import Path

import pytest
from voice_typer.server.tts.packs import (
    AUDIO8_REALISTIC_BF16,
    Artifact,
    total_bytes,
    verify_gguf,
    verify_model,
)
from voice_typer.server.tts.types import TtsError


def _artifact(payload: bytes) -> Artifact:
    return Artifact(filename="model.gguf", url="https://example.invalid/model.gguf", size_bytes=len(payload))


def test_verify_accepts_matching_gguf(tmp_path: Path) -> None:
    payload = b"GGUF" + b"\x00" * 8
    (tmp_path / "model.gguf").write_bytes(payload)

    assert _artifact(payload).verify(tmp_path).name == "model.gguf"


def test_verify_rejects_size_mismatch(tmp_path: Path) -> None:
    payload = b"GGUF" + b"\x00" * 8
    (tmp_path / "model.gguf").write_bytes(payload[:-2])

    with pytest.raises(TtsError, match="incomplete"):
        _artifact(payload).verify(tmp_path)


def test_verify_rejects_non_gguf(tmp_path: Path) -> None:
    payload = b"<html>" + b" " * 8
    (tmp_path / "model.gguf").write_bytes(payload)

    with pytest.raises(TtsError, match="not a GGUF"):
        _artifact(payload).verify(tmp_path)


def test_is_present_requires_exact_size(tmp_path: Path) -> None:
    payload = b"GGUF" + b"\x00" * 8
    (tmp_path / "model.gguf").write_bytes(payload + b"x")

    assert _artifact(payload).is_present(tmp_path) is False


def test_total_bytes_sums_pack() -> None:
    assert total_bytes((_artifact(b"GGUF"), _artifact(b"GGUFGGUF"))) == 12


def test_truncated_pinned_artifact_reports_incomplete(tmp_path: Path) -> None:
    """A mid-transfer file keeps the GGUF magic, so only the size check catches it."""
    path = tmp_path / AUDIO8_REALISTIC_BF16.filename
    path.write_bytes(b"GGUF" + b"\x00" * 12)

    with pytest.raises(TtsError, match="incomplete"):
        verify_model(path, AUDIO8_REALISTIC_BF16)


def test_unpinned_small_gguf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "custom-q8_0.gguf"
    path.write_bytes(b"GGUF" + b"\x00" * 12)

    with pytest.raises(TtsError, match="too small"):
        verify_gguf(path)
