"""Guard the inline Windows Nuitka commands against drift from freeze scripts.

The Windows workflow freezes the sidecar inline in PowerShell while the worker
step delegates to ``build_worker_windows.sh``.  Critical Nuitka flags must stay
identical to the bash scripts: a silent omission (rnnoise.dll, Crypto, the
versioned cache spec) builds a green exe that fails the post-build gate.
"""

from __future__ import annotations

import importlib.util
import os as _os
import re
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "tauri-windows-build.yml"
SIDECAR_SCRIPT = ROOT / "scripts" / "build" / "build_sidecar_windows.sh"
WORKER_SCRIPT = ROOT / "scripts" / "build" / "build_worker_windows.sh"
GATE_SCRIPT = ROOT / "scripts" / "verify_windows_bundle.py"


def _step(name_fragment: str) -> str:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in data.get("jobs", {}).values():
        for step in job.get("steps", []):
            if name_fragment in step.get("name", ""):
                return str(step["run"])
    pytest.fail(f"workflow step containing {name_fragment!r} not found")


def _value(text: str, flag: str) -> str | None:
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        match = re.search(rf"{re.escape(flag)}=[\"']?([^\"'`\s]+)", line)
        if match:
            return match.group(1)
    return None


def _tokens(text: str, flag: str) -> set[str]:
    """Collect ``flag=value`` tokens for one flag family, normalized."""
    out: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip().rstrip("`\\").strip()
        for token in line.split():
            if token.startswith(flag):
                out.add(token.strip("\"'"))
    return out


def _includes(text: str) -> set[str]:
    return {token.split("=", 1)[1] for token in _tokens(text, "--include-package=") if "=" in token}


def test_inline_sidecar_matches_freeze_script_on_critical_flags() -> None:
    inline = _step("Build the sidecar with Nuitka")
    script = SIDECAR_SCRIPT.read_text(encoding="utf-8")

    # Versioned, per-product onefile cache spec must match exactly; the gate
    # derives the extraction dir from the script, not from the workflow.
    inline_spec = _value(inline, "--onefile-tempdir-spec")
    script_spec = _value(script, "--onefile-tempdir-spec")
    assert inline_spec == script_spec == "{CACHE_DIR}/{PRODUCT}/{VERSION}/onefile-tmp", (
        f"--onefile-tempdir-spec drift: inline={inline_spec!r} script={script_spec!r}"
    )

    inline_product = _value(inline, "--product-name")
    script_product = _value(script, "--product-name")
    assert inline_product == script_product == "LausuSidecar", (
        f"--product-name drift: inline={inline_product!r} script={script_product!r}"
    )

    # Round-8 native RNNoise data include: required by the self-check marker.
    rnnoise = r"--include-data-file=[\"']?\$SITE/pyrnnoise/rnnoise\.dll=rnnoise\.dll"
    assert re.search(rnnoise, script), f"--include-data-file (rnnoise.dll) missing from {SIDECAR_SCRIPT}"
    assert re.search(rnnoise, inline), "--include-data-file (rnnoise.dll) missing from inline sidecar freeze"

    assert "Crypto" in _includes(script), "--include-package=Crypto missing from sidecar script"
    assert "Crypto" in _includes(inline), "--include-package=Crypto missing from inline sidecar freeze"
    assert "av" not in _includes(script), "bundled decoder must stay out of the sidecar (GPL DLLs)"
    assert "av" not in _includes(inline), "bundled decoder must stay out of the inline sidecar freeze"

    # SITE must be a real site-packages path; CI logs prove the PowerShell
    # expression resolves it, and the data-file flag expands it in-pipeline.
    assert "site.getsitepackages()" in inline, "PowerShell SITE computation missing"


def test_worker_step_delegates_to_script_and_script_has_worker_excludes() -> None:
    worker_step = _step("Build the worker binary with Nuitka")
    assert "bash scripts/build/build_worker_windows.sh" in worker_step, (
        "worker freeze must delegate to build_worker_windows.sh (single source of truth)"
    )
    script = WORKER_SCRIPT.read_text(encoding="utf-8")
    nofollows = {token.split("=", 1)[1] for token in _tokens(script, "--nofollow-import-to=") if "=" in token}
    for module in ("pyrnnoise", "audiolab", "Crypto"):
        assert module in nofollows, f"--nofollow-import-to={module} missing from worker script"
    assert _value(script, "--product-name") == "LausuWorker"
    assert _value(script, "--onefile-tempdir-spec") == ("{CACHE_DIR}/{PRODUCT}/{VERSION}/onefile-tmp")


def test_ffmpeg_fetch_is_present_for_both_freeze_paths() -> None:
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    assert "fetch_ffmpeg_lgpl_win64.sh" in workflow_text, "LGPL ffmpeg fetch step missing"
    assert "Fetch + verify LGPL ffmpeg" in workflow_text, "LGPL ffmpeg fetch label missing"
    assert "av" not in _includes(_step("Build the sidecar with Nuitka")), (
        "--include-package=av must be gone: the pinned LGPL ffmpeg carries no GPL DLLs"
    )
    assert "fetch_transcribe_cpp_win64.sh" in workflow_text, "GGUF runner fetch step missing"


def test_gate_resolves_newest_versioned_extraction_dir_without_build_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate scans version siblings; it never needs the freeze job's stamp."""
    spec = importlib.util.spec_from_file_location("_windows_bundle_gate", GATE_SCRIPT)
    assert spec is not None and spec.loader is not None
    gate: ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # Patch only the gate module's `os` reference; the global module must stay
    # untouched so pytest/pathlib keep the host platform's Path flavour.
    monkeypatch.setattr(gate, "os", SimpleNamespace(name="nt", environ=_os.environ))
    old = tmp_path / "LausuSidecar" / "2026.01.01.0000" / "onefile-tmp"
    new = tmp_path / "LausuSidecar" / "2026.11.22.1234" / "onefile-tmp"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    # The version stamp, not filesystem mtime, decides "newest": make the old
    # dir look newer on disk so an mtime-based pick fails deterministically.
    _os.utime(old, (2_000_000_000, 2_000_000_000))
    _os.utime(new, (1_000_000_000, 1_000_000_000))

    assert gate.onefile_extraction_dir() == new, (
        "gate must pick the newest versioned onefile-tmp; it must not depend on "
        "the freeze job's BUILD_STAMP (different job/runner)"
    )
