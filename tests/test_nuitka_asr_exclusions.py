"""Pin the C7 Nuitka ASR exclusions across every sidecar invocation.

ADR-0025 C7: the slim sidecar must exclude faster_whisper/ctranslate2
(they live in the pack worker) while keeping every hard gate intact:
no torch-distributed-style exclusions (C-CI-8), package-data + console
+ tempdir flags (C-CI-9), nuitka==2.8.10 (C-CI-6). Four invocations
carry the flags: three build_sidecar_*.sh scripts + the inline command
in tauri-windows-build.yml.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_SCRIPTS = [
    REPO_ROOT / "scripts" / "build" / "build_sidecar_windows.sh",
    REPO_ROOT / "scripts" / "build" / "build_sidecar_linux.sh",
    REPO_ROOT / "scripts" / "build" / "build_sidecar_macos.sh",
]
_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tauri-windows-build.yml"

_ALL = _SCRIPTS + [_WORKFLOW]

_FORBIDDEN_EXCLUDES = (
    "torch.utils.data.distributed",
    "torch.export",
    "torch._functorch",
    "torch.testing",
    "torch.package",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestAsrExclusionsPresent:
    def test_faster_whisper_excluded_everywhere(self):
        for path in _ALL:
            text = _read(path)
            assert "--nofollow-import-to=faster_whisper" in text, f"{path.name} must exclude faster_whisper"

    def test_ctranslate2_excluded_everywhere(self):
        for path in _ALL:
            text = _read(path)
            assert "--nofollow-import-to=ctranslate2" in text, f"{path.name} must exclude ctranslate2"

    def test_torch_excluded_everywhere(self):
        # Top-level torch nofollow (our code never imports torch; only
        # onnxruntime's guarded probe does, which Nuitka follows blindly
        # and then crashes on torch 2.13). Whole-tree exclusion in every
        # sidecar invocation + the workflow.
        for path in _ALL:
            text = _read(path)
            assert "--nofollow-import-to=torch" in text, f"{path.name} must exclude torch"

    def test_no_include_package_for_asr_libs(self):
        for path in _ALL:
            text = _read(path)
            assert "--include-package=faster_whisper" not in text, f"{path.name} must not bundle faster_whisper"
            assert "--include-package=ctranslate2" not in text, f"{path.name} must not bundle ctranslate2"

    def test_no_ct2_data_plumbing(self):
        for path in _SCRIPTS:
            text = _read(path)
            for token in ("CT2_DATA_DIR_SRC", "CT2_DLL", "CT2_LIBS_DIR", "CT2_LIB_DIR", "CT2_DIR"):
                assert token not in text, f"{path.name} must not reference {token} (worker owns CT2 data)"


class TestHardGatesIntact:
    def test_no_torch_distributed_style_excludes(self):
        for path in _ALL:
            text = _read(path)
            for mod in _FORBIDDEN_EXCLUDES:
                assert f"--nofollow-import-to={mod}" not in text, f"{path.name} must not exclude {mod} (C-CI-8)"

    def test_package_data_flag_kept(self):
        for path in _ALL:
            assert "--include-package-data=voice_typer.server" in _read(path), f"{path.name} (C-CI-9)"

    def test_console_and_tempdir_flags_kept(self):
        # Console mode is Windows-only (C-CI-9); Linux has no console
        # subsystem and macOS uses --macos-app-mode=background instead.
        # Tempdir spec applies everywhere.
        for path in _ALL:
            assert "onefile-tempdir-spec" in _read(path), f"{path.name} tempdir spec (C-CI-9)"
        for path in [f for f in _ALL if "linux" not in f.name and "macos" not in f.name]:
            text = _read(path)
            assert ("--windows-console-mode=disable" in text) or ("--windows-disable-console" in text), (
                f"{path.name} console mode (C-CI-9)"
            )

    def test_nuitka_pin_in_workflow(self):
        assert "nuitka==2.8.10" in _read(_WORKFLOW), "workflow must pin nuitka==2.8.10 (C-CI-6)"
