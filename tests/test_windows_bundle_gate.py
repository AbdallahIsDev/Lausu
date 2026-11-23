"""GPL-DLL gate: exe byte scan + authoritative onefile extraction-dir name scan."""

from __future__ import annotations

import importlib.util
import os as _os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = ROOT / "scripts" / "verify_windows_bundle.py"

_spec = importlib.util.spec_from_file_location("_verify_windows_bundle_gate", GATE_SCRIPT)
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _make_dlls(root: Path, names: list[str]) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")


def test_extraction_scan_detects_gpl_names(tmp_path: Path) -> None:
    _make_dlls(tmp_path, ["avcodec-62-xxxx.dll", "libx264-165-xxxx.dll", "readme.txt"])
    gpl_hits, av_hits = gate.extraction_dll_scan(tmp_path)
    assert {hit.path.name for hit in gpl_hits} == {
        "avcodec-62-xxxx.dll",
        "libx264-165-xxxx.dll",
    }
    assert av_hits == []


def test_extraction_scan_inventory_under_av_libs(tmp_path: Path) -> None:
    _make_dlls(
        tmp_path,
        [
            "av.libs/avutil-59.dll",
            "av.libs/nested/avformat-61.dll",
            "other/avcodec-62-9f3a.dll",
        ],
    )
    gpl_hits, av_hits = gate.extraction_dll_scan(tmp_path)
    assert {hit.path.name for hit in gpl_hits} == {"avcodec-62-9f3a.dll"}
    assert {hit.path.name for hit in av_hits} == {"avutil-59.dll", "avformat-61.dll"}
    assert all(hit.reason == "av.libs" for hit in av_hits)


def test_extraction_scan_clean_dir(tmp_path: Path) -> None:
    _make_dlls(tmp_path, ["onefile.bin", "rnnoise.dll"])
    assert gate.extraction_dll_scan(tmp_path) == ([], [])
    assert gate.extraction_dll_scan(tmp_path / "absent") == ([], [])


def test_pinned_spec_is_per_build_and_per_product(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = gate.pinned_onefile_tempdir_spec()
    assert spec == "{CACHE_DIR}/{PRODUCT}/{VERSION}/onefile-tmp"
    assert gate.freeze_product_name() == "LausuSidecar"
    assert gate.expand_onefile_cache_spec(spec.split("/{VERSION}/")[0], r"C:\cache", "LausuSidecar") == Path(
        r"C:\cache/LausuSidecar"
    )
    assert gate.expand_onefile_cache_spec("{TEMP}/onefile_{PID}_{TIME}", "C:\\cache") is None

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # Patch only the gate module's `os` reference. Patching the global os.name
    # would make pytest's own pathlib.Path resolve to WindowsPath on POSIX.
    monkeypatch.setattr(gate, "os", SimpleNamespace(name="nt", environ=_os.environ))
    old = tmp_path / "LausuSidecar" / "2026.01.01.0000" / "onefile-tmp"
    new = tmp_path / "LausuSidecar" / "2026.11.21.1635" / "onefile-tmp"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    # The version stamp, not filesystem mtime, decides "newest": make the old
    # dir look newer on disk so an mtime-based pick fails deterministically.
    _os.utime(old, (2_000_000_000, 2_000_000_000))
    _os.utime(new, (1_000_000_000, 1_000_000_000))
    assert gate.onefile_extraction_dir() == new


def test_gpl_gate_soft_mode_warns_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    _make_dlls(tmp_path / "extract", ["avcodec-62-xxxx.dll", "libx264-165-xxxx.dll"])
    passed = gate.gpl_gate(tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "0", tmp_path / "extract")
    out = capsys.readouterr().out
    assert "exe string scan (blind to compressed onefile payloads)" in out
    assert "onefile extraction-dir name scan (authoritative" in out
    assert "avcodec-62-xxxx.dll" in out
    assert "libx264-165-xxxx.dll" in out
    assert "ENFORCE_NO_GPL_DLLS=0 so this is informational" in out
    assert "2 extraction-name hit(s)" in passed[0]


def test_gpl_gate_enforce_one_fails_on_named_dll(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    _make_dlls(tmp_path / "extract", ["libx264-165-xxxx.dll"])
    with pytest.raises(gate.BundleVerificationError, match="GPL DLLs found"):
        gate.gpl_gate(tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "1", tmp_path / "extract")


def test_gpl_gate_enforce_one_clean_dir_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    extract = tmp_path / "extract"
    _make_dlls(extract, ["rnnoise.dll"])
    gate.gpl_gate(tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "1", extract)
    assert "ENFORCE_NO_GPL_DLLS check: clean." in capsys.readouterr().out


def test_gpl_gate_empty_extraction_dir_is_inconclusive_not_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    empty = tmp_path / "empty-extract"
    empty.mkdir()
    with pytest.raises(gate.BundleVerificationError, match="nothing to scan"):
        gate.gpl_gate(tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "1", empty)
    gate.gpl_gate(tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "0", empty)
    out = capsys.readouterr().out
    assert "INCONCLUSIVE, not clean" in out
    assert "ENFORCE_NO_GPL_DLLS check: clean." not in out


def test_gpl_gate_missing_extraction_dir_warns_when_soft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    missing = tmp_path / "absent"
    with pytest.raises(gate.BundleVerificationError, match="does not exist"):
        gate.gpl_gate(tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "1", missing)
    gate.gpl_gate(tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "0", missing)
    assert "does not exist" in capsys.readouterr().out


def test_gpl_gate_requires_a_resolvable_extraction_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    with pytest.raises(gate.BundleVerificationError, match="could not be determined"):
        gate.gpl_gate(tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "0", None)


def test_main_collects_all_failures_but_still_runs_gpl_scan_and_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)

    def _bad_bundle(_target: str) -> list[str]:
        raise gate.BundleVerificationError("bundle contents: missing ffmpeg")

    def _bad_selfcheck(*_args: object) -> list[str]:
        raise gate.BundleVerificationError("frozen self-check: SELFCHECK failed")

    def _gpl(*_args: object) -> list[str]:
        print("### GPL DLL scan")
        print("| DLL | matched |")
        return ["GPL DLL scan: 0 token(s)"]

    monkeypatch.setattr(gate, "check_bundle_contents", _bad_bundle)
    monkeypatch.setattr(gate, "run_sidecar_smoke", _bad_selfcheck)
    monkeypatch.setattr(gate, "onefile_extraction_dir", lambda *_args, **_kwargs: tmp_path / "extract")
    monkeypatch.setattr(gate, "gpl_gate", _gpl)
    sidecar = tmp_path / "sidecar.exe"
    sidecar.write_bytes(b"")
    wav = tmp_path / "tone.wav"
    wav.write_bytes(b"")
    summary = tmp_path / "summary.md"

    rc = gate.main(
        [
            "--sidecar",
            str(sidecar),
            "--wav",
            str(wav),
            "--summary",
            str(summary),
            "--onefile-extract-dir",
            str(tmp_path / "extract"),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "### GPL DLL scan" in out
    assert "Wrote size summary to" in out
    assert "Windows bundle verification FAILED CHECKS:" in out
    assert "bundle contents: bundle contents: missing ffmpeg" in out
    assert "frozen self-check: frozen self-check: SELFCHECK failed" in out
