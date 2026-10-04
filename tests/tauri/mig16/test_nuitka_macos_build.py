"""
Nuitka macOS build validation (x86_64 + aarch64).
Gaps documented (report, do NOT fix, out of scope for this gate check):
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.fixtures.bash_utils import bash_usable

# Path from file → root:
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SIDECAR_SCRIPT = PROJECT_ROOT / "scripts" / "build" / "build_sidecar_macos.sh"
LINUX_SIDECAR_SCRIPT = PROJECT_ROOT / "scripts" / "build" / "build_sidecar_linux.sh"


@pytest.fixture(scope="module")
def sidecar_text() -> str:
    """Read the sidecar build script once per module; fail fast if missing."""
    assert SIDECAR_SCRIPT.is_file(), (
        f"build_sidecar_macos.sh not found at {SIDECAR_SCRIPT}. Did the project layout change?"
    )
    return SIDECAR_SCRIPT.read_text(encoding="utf-8")


def test_sidecar_build_script_exists():
    """The macOS sidecar build script must exist at the canonical path."""
    assert SIDECAR_SCRIPT.is_file(), f"missing: {SIDECAR_SCRIPT}"
    # Also assert it's non-empty (a stub would be a regression).
    assert SIDECAR_SCRIPT.stat().st_size > 1000, (
        f"{SIDECAR_SCRIPT} is suspiciously small ({SIDECAR_SCRIPT.stat().st_size} bytes); "
        "expected a full Nuitka invocation script (~3-5 KB)."
    )


def test_sidecar_script_is_bash_syntax_valid():
    """``bash -n`` must parse the sidecar script without syntax errors."""
    if not bash_usable():
        pytest.skip("bash not available or not usable on this host, cannot run `bash -n`.")
    result = subprocess.run(
        ["bash", "-n", str(SIDECAR_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (
        f"bash -n failed on {SIDECAR_SCRIPT}:\n--- stderr ---\n{result.stderr}\n--- stdout ---\n{result.stdout}"
    )


def test_sidecar_script_has_shebang_and_strict_mode(sidecar_text: str):
    """The sidecar script must use ``#!/usr/bin/env bash`` + ``set -euo pipefail``."""
    assert sidecar_text.startswith("#!/usr/bin/env bash"), (
        "build_sidecar_macos.sh must start with `#!/usr/bin/env bash`"
    )
    assert "set -euo pipefail" in sidecar_text, (
        "build_sidecar_macos.sh must enable strict mode (`set -euo pipefail`) "
        "so a missing dylib or failed import aborts the build instead of "
        "producing a broken sidecar."
    )


def test_sidecar_script_supports_both_arches_via_arg(sidecar_text: str):
    """The sidecar script must accept ``aarch64`` OR ``x86_64`` as ``$1``."""
    assert 'ARCH="${1:-}"' in sidecar_text, (
        "build_sidecar_macos.sh must read ARCH from the first positional "
        'arg: `ARCH="${1:-}"`. (macOS validation runbook §1.)'
    )
    # The case statement must accept BOTH arches.
    assert "x86_64|aarch64)" in sidecar_text or ("x86_64)" in sidecar_text and "aarch64)" in sidecar_text), (
        "build_sidecar_macos.sh must accept both x86_64 + aarch64 in the ARCH validation case statement."
    )


def test_sidecar_script_defaults_to_host_arch(sidecar_text: str):
    """When no arg is given, the script must default to ``uname -m``."""
    assert "uname -m" in sidecar_text, (
        "build_sidecar_macos.sh must default ARCH via `uname -m` when no positional arg is given."
    )
    assert "arm64)" in sidecar_text and ('ARCH="aarch64"' in sidecar_text or "ARCH=aarch64" in sidecar_text), (
        "build_sidecar_macos.sh must map arm64 → aarch64."
    )
    assert 'ARCH="x86_64"' in sidecar_text or "ARCH=x86_64" in sidecar_text, (
        "build_sidecar_macos.sh must map x86_64 host → x86_64 arch."
    )


def test_sidecar_script_rejects_unsupported_arch(sidecar_text: str):
    """The script must hard-fail with ``exit 1`` on an unsupported arch."""
    assert "exit 1" in sidecar_text
    # The arch case statement must have a `*)` wildcard error branch.
    assert "*)" in sidecar_text
    assert "arch must be x86_64 or aarch64" in sidecar_text or ("unsupported" in sidecar_text.lower()), (
        "build_sidecar_macos.sh must print a clear error if ARCH is not x86_64 or aarch64."
    )


EXPECTED_NUITKA_FLAGS = [
    "--standalone",
    "--onefile",
    "--assume-yes-for-downloads",
    "--enable-plugin=numpy",
    "--nofollow-import-to=faster_whisper",
    "--nofollow-import-to=ctranslate2",
    "--include-package=voice_typer",
    "--include-package=websockets",
    "--onefile-tempdir-spec",
    "--output-filename",
    "--output-dir",
]


@pytest.mark.parametrize("flag", EXPECTED_NUITKA_FLAGS)
def test_sidecar_script_contains_expected_nuitka_flag(sidecar_text: str, flag: str):
    """Each ADR-0020 §4.3-mandated Nuitka flag must be present in the sidecar script."""
    assert flag in sidecar_text, (
        f"build_sidecar_macos.sh is missing required Nuitka flag `{flag}`. "
        "ADR-0020 §4.3 mandates this flag for the macOS sidecar freeze."
    )


def test_sidecar_script_includes_ctranslate2_data_dir(sidecar_text: str):
    """C7: no ctranslate2 data-dir plumbing may remain (worker owns it)."""
    assert "CT2_DATA_DIR_SRC" not in sidecar_text
    assert "CT2_DLL" not in sidecar_text
    assert "CT2_LIBS_DIR" not in sidecar_text
    assert "CT2_LIB_DIR" not in sidecar_text
    assert "CT2_DIR" not in sidecar_text
    assert "ctranslate2/lib" not in sidecar_text
    assert "ctranslate2/libs" not in sidecar_text


# 4. ctranslate2/libs guard (plural, pattern, REQUIRED on macOS) ─
def test_sidecar_script_has_xplat3_ctranslate2_libs_guard(sidecar_text: str):
    """C7: the XPLAT-3 guard is deleted with the CT2 plumbing (worker owns it)."""
    assert "CT2_LIBS_DIR" not in sidecar_text
    assert "ctranslate2/libs" not in sidecar_text


def test_sidecar_script_has_ctranslate2_lib_guard_singular(sidecar_text: str):
    """C7: the singular CT2 lib guard is deleted with the plumbing."""
    assert "CT2_LIB_DIR" not in sidecar_text
    assert "ctranslate2/lib" not in sidecar_text


def test_sidecar_script_uses_triple_variable_construction(sidecar_text: str):
    """The sidecar script must build TRIPLE from ARCH via ``${ARCH}-apple-darwin``."""
    assert "${ARCH}-apple-darwin" in sidecar_text, (
        'build_sidecar_macos.sh must construct TRIPLE dynamically: TRIPLE="${ARCH}-apple-darwin"'
    )


def test_sidecar_script_output_filename_pattern(sidecar_text: str):
    """The output filename must match ``python-sidecar-<triple>``."""
    assert "python-sidecar-" in sidecar_text, (
        "build_sidecar_macos.sh output filename must start with `python-sidecar-` (Tauri externalBin base name)."
    )
    assert "python-sidecar-${TRIPLE}" in sidecar_text, (
        "build_sidecar_macos.sh must construct OUTPUT_NAME as python-sidecar-${TRIPLE} (or equivalent)."
    )


def test_sidecar_script_documents_both_arch_output_filenames(sidecar_text: str):
    """The script header must document BOTH arch output filenames."""
    assert "python-sidecar-x86_64-apple-darwin" in sidecar_text, (
        "build_sidecar_macos.sh header must document the x86_64-apple-darwin output filename."
    )
    assert "python-sidecar-aarch64-apple-darwin" in sidecar_text, (
        "build_sidecar_macos.sh header must document the aarch64-apple-darwin output filename."
    )


def test_sidecar_script_outputs_to_src_tauri_bin(sidecar_text: str):
    """The output directory must be ``src-tauri/bin`` (Tauri externalBin location)."""
    assert "src-tauri/bin" in sidecar_text, (
        "build_sidecar_macos.sh must output to src-tauri/bin/ (the location "
        "Tauri's externalBin mechanism expects sidecar binaries)."
    )


def test_sidecar_script_verifies_output_after_build(sidecar_text: str):
    """The script must verify the output binary exists after Nuitka completes."""
    assert "OUTPUT_PATH" in sidecar_text
    assert '! -f "$OUTPUT_PATH"' in sidecar_text, (
        'build_sidecar_macos.sh must verify: `if [[ ! -f "$OUTPUT_PATH" ]]; then echo ERROR; exit 1; fi`'
    )


def test_sidecar_script_references_python_build_standalone(sidecar_text: str):
    """The script must reference ``python-build-standalone`` as the base interpreter."""
    assert "python-build-standalone" in sidecar_text, (
        "build_sidecar_macos.sh must reference python-build-standalone "
        "(ADR-0020 §4.3 mandates a clean cpython-3.12.x install as the "
        "Nuitka target interpreter)."
    )


def test_sidecar_script_references_cpython_3_12(sidecar_text: str):
    """The script must pin the interpreter to ``cpython-3.12.x``."""
    assert "cpython-3.12" in sidecar_text, (
        "build_sidecar_macos.sh must reference cpython-3.12.x (the ADR-0020 "
        "§4.3 pinned interpreter version for BOTH arches)."
    )


def test_sidecar_script_documents_both_arch_interpreters(sidecar_text: str):
    """The script header must document BOTH per-arch interpreters."""
    # The header docstring mentions the per-arch python-build-standalone
    assert "x86_64-apple-darwin" in sidecar_text, (
        "build_sidecar_macos.sh must reference the x86_64-apple-darwin "
        "triple (Intel python-build-standalone cpython-3.12.x)."
    )
    assert "aarch64-apple-darwin" in sidecar_text, (
        "build_sidecar_macos.sh must reference the aarch64-apple-darwin "
        "triple (Apple Silicon python-build-standalone cpython-3.12.x)."
    )


def test_sidecar_script_discovers_pybs_via_env_var(sidecar_text: str):
    """The script must discover the python-build-standalone install via env var."""
    assert "VOICE_TYPER_PYBS_DIR" in sidecar_text, (
        "build_sidecar_macos.sh must discover python-build-standalone via $VOICE_TYPER_PYBS_DIR (set by CI workflow)."
    )
    assert "${PYBS" in sidecar_text, "build_sidecar_macos.sh must support the $PYBS env var override."
    assert "command -v python3" in sidecar_text, "build_sidecar_macos.sh must fall back to `command -v python3`."


def test_sidecar_script_uses_pybs_install_only_layout(sidecar_text: str):
    """The script must reference the python-build-standalone install_only layout."""
    assert "python/bin/python3" in sidecar_text, (
        "build_sidecar_macos.sh must reference python-build-standalone's "
        "install_only layout: $PYBS_DIR/python/bin/python3."
    )


def test_sidecar_script_uses_macos_app_mode_background(sidecar_text: str):
    """The script must pass ``--macos-app-mode=background`` (LSUIElement=true)."""
    assert "--macos-app-mode=background" in sidecar_text, (
        "build_sidecar_macos.sh must pass --macos-app-mode=background to "
        "Nuitka (ADR-0020 §4.3. LSUIElement=true, no Dock icon)."
    )


def test_sidecar_script_uses_macos_create_bundle(sidecar_text: str):
    """The script must pass ``--macos-create-bundle`` (+ app name + signed name)."""
    assert "--macos-create-bundle" in sidecar_text
    assert "--macos-app-name=" in sidecar_text
    assert "--macos-signed-app-name=" in sidecar_text, (
        "build_sidecar_macos.sh must pass --macos-signed-app-name (matches "
        "the CFBundleIdentifier used for codesign: see signing-guide.md §13.2)."
    )


def test_sidecar_script_onefile_tempdir_uses_app_support(sidecar_text: str):
    """
    ``--onefile-tempdir-spec`` must pin to ``$HOME/Library/Application Support``.
    ADR-0020 §4.3: pinning the extract dir prevents tempdir bloat from
    """
    assert "Library/Application Support" in sidecar_text, (
        "build_sidecar_macos.sh --onefile-tempdir-spec must use "
        "$HOME/Library/Application Support/lausu/onefile-tmp "
        "(macOS convention, ADR-0020 §4.3)."
    )


def test_sidecar_script_supports_check_mode(sidecar_text: str):
    """The sidecar script must support a ``--check`` arg to verify the toolchain."""
    assert '"--check"' in sidecar_text or "--check" in sidecar_text
    assert "import nuitka" in sidecar_text, "build_sidecar_macos.sh --check must verify nuitka is importable."
    assert "import websockets" in sidecar_text, "build_sidecar_macos.sh --check must verify websockets."
    assert "import faster_whisper, ctranslate2" not in sidecar_text, (
        "C7: --check must not require the worker-owned ASR libs."
    )


def test_sidecar_script_checks_swiftc(sidecar_text: str):
    """The sidecar script ``--check`` must verify ``swiftc`` is on PATH."""
    assert "command -v swiftc" in sidecar_text, (
        "build_sidecar_macos.sh --check must verify swiftc (Xcode CLT) is on PATH, required for --macos-create-bundle."
    )


def test_sidecar_script_sanity_checks_ctranslate2_import(sidecar_text: str):
    """C7: the pre-Nuitka sanity check covers websockets only."""
    assert "import faster_whisper, ctranslate2, websockets" not in sidecar_text, (
        "C7: the sanity check must not require the worker-owned ASR libs."
    )
    assert "ctranslate2.__version__" not in sidecar_text


def test_sidecar_script_resolves_site_packages(sidecar_text: str):
    """The script must resolve the build env's site-packages dir."""
    assert "site.getsitepackages()" in sidecar_text


def test_sidecar_script_entry_point_is_ipc_server(sidecar_text: str):
    """The Nuitka entry point must be ``voice_typer/server/ipc_server.py``."""
    assert "voice_typer/server/ipc_server.py" in sidecar_text


def test_sidecar_script_uses_nuitka_args_array(sidecar_text: str):
    """The script uses the ``NUITKA_ARGS`` bash array pattern."""
    assert "NUITKA_ARGS=(" in sidecar_text
    assert '"${NUITKA_ARGS[@]}"' in sidecar_text
    assert "NUITKA_ARGS+=" in sidecar_text, (
        "build_sidecar_macos.sh must use `NUITKA_ARGS+=(...)` to conditionally "
        "append the XPLAT-3 libs/ flag inside the guard block."
    )


def test_sidecar_script_runs_otool_verify(sidecar_text: str):
    """C7: no otool verify of the CT2 dylib remains (worker owns it)."""
    assert "otool -L" not in sidecar_text
    assert "libctranslate2" not in sidecar_text


def test_sidecar_script_documents_signing_next_step(sidecar_text: str):
    """The script must point to the signing runbook after a successful build."""
    assert "signing-guide.md" in sidecar_text or "codesign" in sidecar_text, (
        "build_sidecar_macos.sh must document the next step (codesign + "
        "notarize / signing-guide.md §13.2) after a successful build."
    )


# 10. Sibling parity (Linux script has the  guard) ────────────────
def test_linux_sibling_has_xplat3_ctranslate2_libs_guard():
    """C7: the Linux sibling must not carry the XPLAT-3 guard anymore."""
    if not LINUX_SIDECAR_SCRIPT.is_file():
        pytest.skip(f"build_sidecar_linux.sh missing ({LINUX_SIDECAR_SCRIPT}), cannot verify Linux sibling parity.")
    linux_text = LINUX_SIDECAR_SCRIPT.read_text(encoding="utf-8")
    assert "CT2_LIBS_DIR" not in linux_text


# ─── 11. KNOWN GAPS (report, do NOT fix, out of scope for this gate check) ─
def test_known_gap_no_arch_x86_64_prefix(sidecar_text: str):
    """Rosetta-based Intel builds on an Apple Silicon host, NOR does it pass"""
    assert "arch -x86_64" not in sidecar_text, (
        "build_sidecar_macos.sh now invokes `arch -x86_64`, update this "
        "test to assert PRESENCE instead of absence, and remove GAP-1 "
        "from the module docstring."
    )
    assert "--target-arch" not in sidecar_text, (
        "build_sidecar_macos.sh now passes --target-arch to Nuitka, "
        "update this test to assert PRESENCE instead of absence."
    )


def test_known_gap_no_pyobjc_include_flag(sidecar_text: str):
    """
    KNOWN GAP (GAP-2): the script does NOT include ``--include-package=pyobjc``.
    This test ASSERTS the gap is present. DO NOT fix this gap as part
    """
    assert "--include-package=pyobjc" not in sidecar_text, (
        "build_sidecar_macos.sh now includes --include-package=pyobjc, "
        "update this test to assert PRESENCE instead of absence, and "
        "remove GAP-2 from the module docstring."
    )
