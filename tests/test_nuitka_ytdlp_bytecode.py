"""yt-dlp extractors must ship as bytecode in every Nuitka freeze.

``yt_dlp.extractor`` holds ~940 extractor modules plus the 781KB
``lazy_extractors`` hub. Compiling them to C OOMs MSVC (C1060/C1002 on
the 7GB CI runner) and bloats the binary; yt-dlp lazy-loads extractors
via ``importlib`` at runtime, which resolves bytecode modules fine
(Nuitka anti-bloat "bytecode" mode, same mechanism as its
eventlet/matplotlib rules).
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FLAG = "--noinclude-custom-mode=yt_dlp.extractor:bytecode"

INVOCATIONS = [
    ".github/workflows/tauri-windows-build.yml",
    "scripts/build/build_sidecar_windows.sh",
    "scripts/build/build_sidecar_macos.sh",
    "scripts/build/build_sidecar_linux.sh",
    "scripts/build/build_worker_windows.sh",
    "scripts/build/build_worker_macos.sh",
    "scripts/build/build_worker_linux.sh",
]


@pytest.mark.parametrize("relative", INVOCATIONS)
def test_extractor_bytecode_flag_present(relative: str):
    """Every Nuitka invocation pulling yt-dlp must bytecode the extractors."""
    path = PROJECT_ROOT / relative
    assert path.is_file(), f"missing Nuitka invocation file: {relative}"
    assert FLAG in path.read_text(encoding="utf-8"), (
        f"{relative} is missing {FLAG!r}; without it Nuitka compiles all "
        "~940 yt-dlp extractor modules to C and MSVC runs out of heap "
        "(C1060/C1002)."
    )


class TestFreezeJobSplit:
    """Sidecar + worker freezes run in parallel jobs (JOB SPLIT)."""

    WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "tauri-windows-build.yml"

    def _text(self) -> str:
        return self.WORKFLOW.read_text(encoding="utf-8")

    def test_three_jobs_exist(self):
        text = self._text()
        for job in ("build-sidecar-exe:", "build-worker-exe:", "tauri-windows-build:"):
            assert job in text, f"expected job {job} in tauri-windows-build.yml"

    def test_tauri_job_needs_both_freeze_jobs(self):
        text = self._text()
        assert "needs: [build-sidecar-exe, build-worker-exe]" in text, (
            "tauri-windows-build must wait for both freeze jobs so one "
            "240min budget is never shared by two Nuitka freezes"
        )

    def test_binaries_pass_via_artifacts(self):
        text = self._text()
        assert "name: windows-sidecar-exe" in text
        assert "name: windows-worker-exe" in text
        assert text.count("uses: actions/download-artifact@v6") >= 2, (
            "tauri-windows-build must download both intermediate binaries"
        )

    def test_no_nuitka_invocation_left_in_tauri_job(self):
        """The Tauri job compiles nothing: no PYBS download, no Nuitka run."""
        import yaml

        jobs = yaml.safe_load(self.WORKFLOW.read_text(encoding="utf-8"))["jobs"]
        steps = jobs["tauri-windows-build"]["steps"]
        names = [s.get("name", "") for s in steps]
        assert not any("python-build-standalone" in n for n in names), (
            "tauri-windows-build must not download PYBS, nothing there runs Nuitka"
        )
        assert not any(n.startswith("Build the sidecar") or n.startswith("Build the worker") for n in names)
