"""Self-check shares the ffmpeg resolver base and uses public filter accessors."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from voice_typer.server.audio_filters import noise_suppressor as ns_module
from voice_typer.server.audio_filters.noise_suppressor import NoiseSuppressor
from voice_typer.server.media_ingest import decoder, ffmpeg_binaries, selfcheck


def test_bundled_bin_dir_is_the_resolver_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_exe = tmp_path / "python-sidecar.exe"
    fake_exe.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert ffmpeg_binaries.bundled_bin_dir() == tmp_path
    shipped = ffmpeg_binaries._shipped_dirs()
    assert shipped[0] == tmp_path
    assert tmp_path / "resources" in shipped


def test_selfcheck_checks_ffmpeg_against_the_shared_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "bundle"
    base.mkdir()
    ffmpeg = base / "ffmpeg.exe"
    ffmpeg.write_bytes(b"")
    wav = tmp_path / "tone.wav"
    wav.write_bytes(b"")
    monkeypatch.setattr(ffmpeg_binaries, "bundled_bin_dir", lambda: base)
    monkeypatch.setattr(
        ffmpeg_binaries,
        "resolve_binaries",
        lambda: ffmpeg_binaries.BinaryPair(ffmpeg=str(ffmpeg), ffprobe=None),
    )
    monkeypatch.setattr(decoder, "decode_chunks", lambda *_a, **_k: [b"x" * 8000, b"y" * 8000])

    class _FakeSuppressor:
        method = "rnnoise"
        degraded = False

        def __init__(self, **_kwargs: object) -> None:
            self.effective_method = self.method
            self.is_degraded = self.degraded

    monkeypatch.setattr(ns_module, "NoiseSuppressor", _FakeSuppressor)
    assert selfcheck.run(str(wav)) == 0
    out = capsys.readouterr().out
    assert "SELFCHECK: PASS bundled-ffmpeg" in out
    assert "SELFCHECK: PASS decode-samples=16000" in out
    assert "SELFCHECK: PASS rnnoise-active" in out

    class _DegradedSuppressor(_FakeSuppressor):
        degraded = True

    monkeypatch.setattr(ns_module, "NoiseSuppressor", _DegradedSuppressor)
    assert selfcheck.run(str(wav)) == 1
    assert "SELFCHECK: FAIL AssertionError: RNNoise not active" in capsys.readouterr().out


def test_selfcheck_rejects_ffmpeg_outside_the_shared_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "bundle"
    base.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    ffmpeg = elsewhere / "ffmpeg.exe"
    ffmpeg.write_bytes(b"")
    wav = tmp_path / "tone.wav"
    wav.write_bytes(b"")
    monkeypatch.setattr(ffmpeg_binaries, "bundled_bin_dir", lambda: base)
    monkeypatch.setattr(
        ffmpeg_binaries,
        "resolve_binaries",
        lambda: ffmpeg_binaries.BinaryPair(ffmpeg=str(ffmpeg), ffprobe=None),
    )
    assert selfcheck.run(str(wav)) == 1
    assert "SELFCHECK: FAIL AssertionError: ffmpeg resolved to" in capsys.readouterr().out


def test_noise_public_accessors_are_read_only_and_truthful() -> None:
    suppressor = NoiseSuppressor.__new__(NoiseSuppressor)
    suppressor._method = "gtcrn"
    suppressor._degraded = True
    suppressor._degraded_reason = "synthetic"
    assert suppressor.effective_method == "gtcrn"
    assert suppressor.is_degraded is True
    assert suppressor.degraded_reason == "synthetic"
    assert type(suppressor).effective_method.fset is None
    assert type(suppressor).is_degraded.fset is None
