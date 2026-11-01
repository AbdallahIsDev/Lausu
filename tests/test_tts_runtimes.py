"""Tests for the TTS runtime installer (archives built locally, no network)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from voice_typer.server.tts import runtimes
from voice_typer.server.tts.types import TtsError


def _zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as bundle:
        for name, data in members.items():
            bundle.writestr(name, data)
    return path


def test_install_places_executable_dlls_and_specs(tmp_path: Path) -> None:
    archive = _zip(
        tmp_path / "runtime.zip",
        {
            "pkg/bin/tool.exe": b"MZ",
            "pkg/bin/tool.dll": b"dll",
            "pkg/model_specs/audio8_tts.json": b"{}",
        },
    )
    dest = tmp_path / "bin"

    installed = runtimes.install_from_archive(archive, dest, exe_name="tool.exe")

    assert installed == dest / "tool.exe"
    assert (dest / "tool.dll").is_file()
    assert (dest / "model_specs" / "audio8_tts.json").is_file()
    # The staging directory never survives a successful install.
    assert not (dest / "._unpack").exists()


def test_install_handles_flat_archive_with_specs_beside_exe(tmp_path: Path) -> None:
    """audio.cpp ships the exe at the archive root, not under bin/."""
    archive = _zip(
        tmp_path / "flat.zip",
        {
            "tool.exe": b"MZ",
            "tool.dll": b"dll",
            "model_specs/audio8_tts.json": b"{}",
        },
    )
    dest = tmp_path / "bin"

    installed = runtimes.install_from_archive(archive, dest, exe_name="tool.exe")

    assert installed == dest / "tool.exe"
    assert (dest / "model_specs" / "audio8_tts.json").is_file()


def test_install_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "evil.zip", {"../escape.exe": b"MZ"})

    with pytest.raises(TtsError, match="unsafe path"):
        runtimes.install_from_archive(archive, tmp_path / "bin", exe_name="escape.exe")

    assert not (tmp_path / "escape.exe").exists()


def test_install_rejects_absolute_member_path(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "abs.zip", {"C:/Windows/evil.exe": b"MZ"})

    with pytest.raises(TtsError, match="unsafe path"):
        runtimes.install_from_archive(archive, tmp_path / "bin", exe_name="evil.exe")


def test_install_rejects_archive_without_executable(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "empty.zip", {"pkg/readme.txt": b"hi"})

    with pytest.raises(TtsError, match="does not contain"):
        runtimes.install_from_archive(archive, tmp_path / "bin", exe_name="tool.exe")


def test_install_is_idempotent_and_skips_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "bin"
    dest.mkdir()
    (dest / "audiocpp_server.exe").write_bytes(b"MZ")
    monkeypatch.setattr(runtimes, "bin_dir", lambda engine: dest)

    def _fail(release: runtimes.RuntimeRelease) -> dict[str, object]:
        raise AssertionError("install() must not resolve a release when the exe exists")

    monkeypatch.setattr(runtimes, "_latest_asset", _fail)

    assert runtimes.install("audio8") == dest / "audiocpp_server.exe"


def test_install_rejects_unknown_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtimes, "bin_dir", lambda engine: tmp_path / engine)

    with pytest.raises(TtsError, match="unknown tts engine"):
        runtimes.install("piper")
