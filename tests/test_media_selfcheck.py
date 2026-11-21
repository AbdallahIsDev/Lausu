"""Self-check shares the ffmpeg resolver base and uses public filter accessors."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

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


def _fake_sys(**attrs: object) -> ModuleType:
    module = ModuleType("fake_sys")
    for name, value in attrs.items():
        setattr(module, name, value)
    return module


def test_is_frozen_build_detects_nuitka_and_pyinstaller() -> None:
    assert ffmpeg_binaries.is_frozen_build(
        {"__compiled__": SimpleNamespace()}, _fake_sys()
    )
    assert ffmpeg_binaries.is_frozen_build(
        {}, _fake_sys(frozen=True, _MEIPASS=None)
    )
    assert ffmpeg_binaries.is_frozen_build(
        {}, _fake_sys(frozen=False, _MEIPASS="/tmp/_MEI123")
    )
    assert not ffmpeg_binaries.is_frozen_build(
        {}, _fake_sys(frozen=False, _MEIPASS=None)
    )


def test_bundled_bin_dir_uses_original_exe_dir_in_onefile(tmp_path: Path) -> None:
    original_dir = tmp_path / "install"
    extraction = tmp_path / "lausu" / "onefile-tmp"
    original_dir.mkdir()
    extraction.mkdir(parents=True)
    fake_sys = _fake_sys(executable=str(extraction / "python.exe"))
    g: dict[str, object] = {"__compiled__": SimpleNamespace(containing_dir=str(original_dir))}
    assert ffmpeg_binaries.bundled_bin_dir(g, fake_sys) == original_dir.resolve()
    assert (
        ffmpeg_binaries.bundled_bin_dir({}, fake_sys)
        == extraction.resolve()
    )


def test_frozen_resolver_ignores_path_and_uses_original_exe_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original_dir = tmp_path / "install"
    extraction = tmp_path / "lausu" / "onefile-tmp"
    path_dir = tmp_path / "path"
    original_dir.mkdir()
    extraction.mkdir(parents=True)
    path_dir.mkdir()
    shipped = original_dir / "ffmpeg.exe"
    shipped.write_bytes(b"real")
    on_path = path_dir / "ffmpeg.exe"
    on_path.write_bytes(b"gpl")
    monkeypatch.setattr(
        ffmpeg_binaries,
        "__compiled__",
        SimpleNamespace(containing_dir=str(original_dir)),
        raising=False,
    )
    monkeypatch.setattr(sys, "executable", str(extraction / "python.exe"))
    monkeypatch.setenv("PATH", str(path_dir))
    for var in (ffmpeg_binaries.ENV_FFMPEG, ffmpeg_binaries.ENV_FFPROBE):
        monkeypatch.delenv(var, raising=False)
    pair = ffmpeg_binaries.resolve_binaries()
    assert pair is not None
    assert Path(pair.ffmpeg).resolve() == shipped.resolve()
    assert pair.ffprobe is None


def test_selfcheck_checks_ffmpeg_against_the_shared_base(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = tmp_path / "bundle"
    base.mkdir()
    ffmpeg = base / "ffmpeg.exe"
    ffmpeg.write_bytes(b"")
    wav = tmp_path / "tone.wav"
    wav.write_bytes(b"")
    monkeypatch.setattr(ffmpeg_binaries, "is_frozen_build", lambda: True)
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
    assert "SELFCHECK: PASS frozen-build" in out
    assert "SELFCHECK: PASS no-path-fallback" in out
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
    monkeypatch.setattr(ffmpeg_binaries, "is_frozen_build", lambda: True)
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
