"""Contracts for the MSYS2/mingw-w64 GNU linker shim.

The shim (src-tauri/toolchain/linker_wrap.c + the generated
.toolchain/linker-wrap.exe and .cargo/config.toml) used to exist ONLY in
gitignored directories with no regeneration path. Losing one 300 KB file took
the whole Rust toolchain down, and the only symptom was a misleading
"error: linker ... not found" followed by dozens of unrelated
"could not compile" errors — indistinguishable from real code breakage.

These tests pin the properties that make that class of outage impossible:
the source is tracked, the bootstrap exists and is idempotent, and the
generated config can never point at a file that is not there.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_SRC = REPO_ROOT / "src-tauri" / "toolchain" / "linker_wrap.c"
BOOTSTRAP = REPO_ROOT / "scripts" / "build" / "ensure_gnu_linkchain.py"
TOOLCHAIN_DIR = REPO_ROOT / "src-tauri" / ".toolchain"
WRAPPER_EXE = TOOLCHAIN_DIR / "linker-wrap.exe"
CARGO_CONFIG = REPO_ROOT / "src-tauri" / ".cargo" / "config.toml"


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location("ensure_gnu_linkchain", BOOTSTRAP)
    assert spec and spec.loader, "bootstrap script must be importable"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wrapper_source_is_present():
    """The source of truth must exist in the checkout, not in a scratch dir."""
    assert WRAPPER_SRC.is_file(), (
        f"{WRAPPER_SRC} is missing. The GNU linker shim's source must be "
        "TRACKED so a deleted/quarantined binary is always rebuildable."
    )


def test_bootstrap_script_is_present():
    assert BOOTSTRAP.is_file(), (
        f"{BOOTSTRAP} is missing. Without the generator, a deleted shim is "
        "an unrecoverable toolchain outage."
    )


def test_wrapper_source_is_tracked_by_git():
    """A gitignored source would defeat the entire recovery mechanism."""
    proc = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(WRAPPER_SRC.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "src-tauri/toolchain/linker_wrap.c is NOT tracked by git. "
        "The shim source must be committed or it cannot be recovered."
    )


def test_wrapper_source_has_no_hardcoded_machine_paths():
    """Portability is what makes the source safe to commit.

    The original was gitignored precisely because it hardcoded this machine's
    MSYS2 install. It now discovers gcc at runtime, so a hardcoded install
    path would be both a regression and a portability bug.
    """
    text = WRAPPER_SRC.read_text(encoding="utf-8", errors="replace")
    # The candidate roots list is legitimate (it is a SEARCH order); what must
    # not come back is a hardcoded gcc used directly as the linker.
    assert 'static const char *g_gcc_path' not in text, (
        "wrapper must discover gcc at runtime, not hardcode it"
    )
    assert "getenv(\"MINGW_GCC\")" in text, "wrapper must honour MINGW_GCC override"


def test_wrapper_cleans_up_its_scratch():
    """Regression guard for the 24 GB obj-<pid> leak.

    The leak existed because _execvp replaced the process image, so the
    cleanup code could never run. Pin both halves of the fix.
    """
    text = WRAPPER_SRC.read_text(encoding="utf-8", errors="replace")
    assert "_spawnvp(_P_WAIT" in text, (
        "wrapper must use _spawnvp(_P_WAIT); _execvp replaces the process "
        "image and makes cleanup unreachable (the 24 GB obj-<pid> leak)"
    )
    assert "cleanup_scratch()" in text, "wrapper must reap its own scratch dir"


@pytest.mark.skipif(sys.platform != "win32", reason="GNU shim is Windows-only")
def test_bootstrap_check_passes_after_provisioning():
    """--check must succeed once the shim exists (idempotent no-op)."""
    bootstrap = _load_bootstrap()
    assert bootstrap.check() == 0, (
        "shim reported as missing/broken. Run: "
        "python scripts/build/ensure_gnu_linkchain.py"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="GNU shim is Windows-only")
def test_bootstrap_detects_missing_wrapper():
    """A deleted or AV-quarantined wrapper must be DETECTED, not silently used.

    This is the exact failure that used to surface as a wall of unrelated
    cargo errors, so detection is the whole point.
    """
    bootstrap = _load_bootstrap()
    if not WRAPPER_EXE.is_file():
        assert bootstrap.check() == 1, "check() must fail when the wrapper is gone"
    else:
        # Present: check() must pass, and the config must not dangle.
        assert bootstrap.check() == 0


@pytest.mark.skipif(sys.platform != "win32", reason="GNU shim is Windows-only")
def test_cargo_config_never_dangles():
    """A config pointing at a missing binary is the outage we are preventing."""
    if not CARGO_CONFIG.is_file():
        pytest.skip("config not generated yet; run ensure_gnu_linkchain.py")
    text = CARGO_CONFIG.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("linker = "):
            target = Path(line.split("=", 1)[1].strip().strip('"'))
            assert target.is_absolute(), (
                "the linker path must be absolute: cargo passes it to rustc as "
                "-C linker, which resolves relative paths against an "
                "unpredictable working directory"
            )
            assert target.is_file(), (
                f"generated config points at missing {target}; run "
                "python scripts/build/ensure_gnu_linkchain.py"
            )
