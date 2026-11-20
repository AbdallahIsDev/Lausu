"""GPL-DLL gate: exe byte scan + authoritative onefile extraction-dir name scan."""

from __future__ import annotations

import importlib.util
from pathlib import Path

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


def test_pinned_spec_expands_to_cached_extraction_dir() -> None:
    spec = gate.pinned_onefile_tempdir_spec()
    assert spec == "{CACHE_DIR}/lausu/onefile-tmp"
    assert gate.expand_onefile_cache_spec(spec, r"C:\cache") == Path(
        r"C:\cache/lausu/onefile-tmp"
    )
    assert gate.expand_onefile_cache_spec("{TEMP}/onefile_{PID}_{TIME}", "C:\\cache") is None


def test_gpl_gate_soft_mode_warns_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    _make_dlls(tmp_path / "extract", ["avcodec-62-xxxx.dll", "libx264-165-xxxx.dll"])
    passed = gate.gpl_gate(
        tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "0", tmp_path / "extract"
    )
    out = capsys.readouterr().out
    assert "exe string scan (blind to compressed onefile payloads)" in out
    assert "onefile extraction-dir name scan (authoritative" in out
    assert "avcodec-62-xxxx.dll" in out
    assert "libx264-165-xxxx.dll" in out
    assert "ENFORCE_NO_GPL_DLLS=0 so this is informational" in out
    assert "2 extraction-name hit(s)" in passed[0]


def test_gpl_gate_enforce_one_fails_on_named_dll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    _make_dlls(tmp_path / "extract", ["libx264-165-xxxx.dll"])
    with pytest.raises(gate.BundleVerificationError, match="GPL DLLs found"):
        gate.gpl_gate(
            tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "1", tmp_path / "extract"
        )


def test_gpl_gate_enforce_one_clean_dir_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    extract = tmp_path / "extract"
    _make_dlls(extract, ["rnnoise.dll"])
    gate.gpl_gate(
        tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "1", extract
    )
    assert "ENFORCE_NO_GPL_DLLS check: clean." in capsys.readouterr().out


def test_gpl_gate_requires_a_resolvable_extraction_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    with pytest.raises(gate.BundleVerificationError, match="could not be determined"):
        gate.gpl_gate(tmp_path / "sidecar.exe", "x86_64-pc-windows-msvc", "0", None)
