"""Contract + frozen-path tests for the sibling transcribe.cpp runner."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tests.fixtures.fake_asr_runner import FIXED_TEXT, write_fake_runner
from voice_typer.server.media_ingest import ffmpeg_binaries
from voice_typer.worker.asr_runner import GgufRunner, RunnerError
from voice_typer.worker.asr_runner.contract import parse_runner_line, parse_runner_output
from voice_typer.worker.asr_runner.runner import resolve_runner_path


def test_upstream_json_shape_is_pinned() -> None:
    """No model needed: the JSONL shape comes from upstream CLI source."""
    line = (
        '{"file":"input.wav","text":"hello world","segments":['
        '{"t0_ms":0,"t1_ms":640,"text":"hello"},'
        '{"t0_ms":640,"t1_ms":1210,"speaker_id":2,"text":"world"}],'
        '"mel_ms":1.0,"encode_ms":2.0,"decode_ms":3.0}'
    )
    result = parse_runner_line(line)
    assert result.text == "hello world"
    assert [seg.start for seg in result.segments] == [0.0, 0.64]
    assert [seg.end for seg in result.segments] == [0.64, 1.21]
    assert result.segments[1].speaker_id == 2
    assert result.error is None
    # transcribe.cpp publishes no calibrated confidence; never invent one.
    assert result.language is None


def test_error_field_is_surfaced_but_not_fabricated_confidence() -> None:
    result = parse_runner_output('{"text":"","segments":[],"error":"TRANSCRIBE_ERR_GGUF"}\n')
    assert result.error == "TRANSCRIBE_ERR_GGUF"
    assert result.text == ""


def test_invalid_output_raises() -> None:
    with pytest.raises(ValueError):
        parse_runner_output("not json\n")


def test_fake_runner_end_to_end(tmp_path: Path) -> None:
    launcher = write_fake_runner(tmp_path)
    audio = np.zeros(16000, dtype=np.float32)
    result = GgufRunner("model.gguf", executable=str(launcher)).transcribe(audio)
    assert result.text == FIXED_TEXT
    assert len(result.segments) == 2


def test_runner_error_mapping(tmp_path: Path) -> None:
    launcher = write_fake_runner(tmp_path)
    runner = GgufRunner("model.gguf", executable=str(launcher))
    with pytest.raises(RunnerError):
        runner.transcribe(np.zeros(400, dtype=np.float32), language="--fail")
    with pytest.raises(RunnerError):
        runner.transcribe(np.zeros(400, dtype=np.float32), language="--emit-invalid")


def test_frozen_resolution_uses_original_exe_dir_and_ignores_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original = tmp_path / "install"
    extraction = tmp_path / "lausu" / "onefile-tmp"
    on_path = tmp_path / "path"
    original.mkdir()
    extraction.mkdir(parents=True)
    on_path.mkdir()
    name = "transcribe-cli.exe" if sys.platform == "win32" else "transcribe-cli"
    shipped = original / name
    shipped.write_bytes(b"real")
    decoy = on_path / name
    decoy.write_bytes(b"decoy")
    monkeypatch.setattr(
        ffmpeg_binaries,
        "__compiled__",
        SimpleNamespace(containing_dir=str(original)),
        raising=False,
    )
    monkeypatch.setattr(sys, "executable", str(extraction / "python-sidecar.exe"))
    monkeypatch.setenv("PATH", str(on_path))
    monkeypatch.delenv("LAUSU_TRANSCRIBE_CLI", raising=False)
    assert Path(resolve_runner_path()).resolve() == shipped.resolve()
