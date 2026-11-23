"""Worker onefile is covered by the extraction-dir name scan; default stays 0."""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.verify_windows_bundle as gate


def test_enforce_default_is_still_zero() -> None:
    # ADR-0031: nobody can verify a frozen build from the cloud sandbox, so
    # the owner flips this later. The gate logic itself is unchanged.
    source = (Path(gate.__file__)).read_text(encoding="utf-8")
    assert 'os.environ.get("ENFORCE_NO_GPL_DLLS", "0")' in source
    assert 'os.environ.get("ENFORCE_NO_GPL_DLLS", "1")' not in source


def test_worker_product_and_spec_are_separate(tmp_path: Path) -> None:
    assert gate.freeze_product_name(gate.FREEZE_SCRIPT) == "LausuSidecar"
    assert gate.freeze_product_name(gate.WORKER_FREEZE_SCRIPT) == "LausuWorker"
    assert gate.pinned_onefile_tempdir_spec(gate.WORKER_FREEZE_SCRIPT) == gate.pinned_onefile_tempdir_spec(
        gate.FREEZE_SCRIPT
    )


def test_worker_extract_dir_override_is_used(tmp_path: Path) -> None:
    worker_dir = tmp_path / "worker-onefile-tmp"
    worker_dir.mkdir()
    assert gate.worker_onefile_extraction_dir(str(worker_dir)) == worker_dir


def test_worker_gpl_dll_fails_under_enforcement(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sidecar_dir = tmp_path / "sidecar-onefile-tmp"
    worker_dir = tmp_path / "worker-onefile-tmp"
    sidecar_dir.mkdir()
    worker_dir.mkdir()
    (sidecar_dir / "readme.txt").write_text("ok")
    (worker_dir / "libx264-165-deadbeef.dll").write_bytes(b"")
    with pytest.raises(gate.BundleVerificationError):
        gate.gpl_gate(
            tmp_path / "python-sidecar.exe",
            gate.DEFAULT_TARGET,
            "1",
            sidecar_dir,
            worker_dir,
        )
    output = capsys.readouterr().out
    assert "worker onefile extraction-dir name scan" in output
    assert "libx264-165-deadbeef.dll" in output


def test_clean_worker_dir_is_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sidecar_dir = tmp_path / "sidecar-onefile-tmp"
    worker_dir = tmp_path / "worker-onefile-tmp"
    sidecar_dir.mkdir()
    worker_dir.mkdir()
    (sidecar_dir / "readme.txt").write_text("ok")
    (worker_dir / "readme.txt").write_text("ok")
    lines = gate.gpl_gate(
        tmp_path / "python-sidecar.exe",
        gate.DEFAULT_TARGET,
        "1",
        sidecar_dir,
        worker_dir,
    )
    assert lines and "extraction-name hit(s) (0 in worker)" in lines[0]
    assert "No GPL-named DLLs found in the worker extraction dir." in capsys.readouterr().out
