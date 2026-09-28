#!/usr/bin/env bash
# =============================================================================
# Lausu. Nuitka sidecar build (Windows x86_64 + aarch64)
# ADR-0020 §4.2. Nuitka freeze of voice_typer/server/ipc_server.py into
# python-sidecar-<triple>.exe, using python-build-standalone as the base
# interpreter.
#
# Output:
#   src-tauri/bin/python-sidecar-x86_64-pc-windows-msvc.exe
#   src-tauri/bin/python-sidecar-aarch64-pc-windows-msvc.exe
#
# This script is designed to run on a Windows host under Git Bash / MSYS2 /
# WSL. From native PowerShell, use the inline Nuitka command in
# .github/workflows/tauri-windows-build.yml instead (it's the same command,
# just expressed in PowerShell syntax).
#
# Usage (Git Bash on Windows):
#   bash scripts/build/build_sidecar_windows.sh x86_64      # default
#   bash scripts/build/build_sidecar_windows.sh aarch64     # Windows-on-ARM
#   bash scripts/build/build_sidecar_windows.sh --check     # verify toolchain
#
# ADR-0020 §4.2 mandates:
#   - python-build-standalone cpython-3.12.x
#   - --standalone --onefile
#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2
#     (ADR-0025 C7: ASR lives in the pack worker; the slim sidecar must
#     neither bundle nor require either library — the faster_whisper /
#     ctranslate2 includes, DLL copies, and import sanity checks below
#     were deleted in the same change; the WORKER build owns them now)
#   - --include-package=voice_typer --include-package=websockets
#   - --windows-disable-console
#   - --onefile-tempdir-spec={CACHE_DIR}/lausu/onefile-tmp
# =============================================================================
set -euo pipefail

# ─── Path resolution ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SIDECAR_DIR="$PROJECT_ROOT/src-tauri/bin"

# ─── Args ────────────────────────────────────────────────────────────────────
ARCH="${1:-x86_64}"
if [[ "$ARCH" == "--check" ]]; then
    echo "[build_sidecar_windows] --check: verifying toolchain"
    command -v python >/dev/null || { echo "MISSING: python (python-build-standalone)" >&2; exit 1; }
    python -c "import nuitka" 2>/dev/null || { echo "MISSING: nuitka (pip install nuitka)" >&2; exit 1; }
    python -c "import websockets" 2>/dev/null || { echo "MISSING: websockets" >&2; exit 1; }
    echo "[build_sidecar_windows] OK: toolchain ready"
    exit 0
fi

case "$ARCH" in
    x86_64|aarch64) ;;
    *) echo "ERROR: arch must be x86_64 or aarch64 (got: $ARCH)" >&2; exit 1 ;;
esac

TRIPLE="${ARCH}-pc-windows-msvc"
EXE_SUFFIX=".exe"
OUTPUT_NAME="python-sidecar-${TRIPLE}${EXE_SUFFIX}"
OUTPUT_PATH="$SIDECAR_DIR/$OUTPUT_NAME"

echo "[build_sidecar_windows] ARCH=$ARCH TRIPLE=$TRIPLE"
echo "[build_sidecar_windows] OUTPUT=$OUTPUT_PATH"

# ─── Locate the python-build-standalone interpreter ──────────────────────────
# Priority:
#   1. $VOICE_TYPER_PYBS_DIR/python/python.exe (set by CI workflow)
#   2. $PYBS env var (explicit path to python.exe)
#   3. `python` from PATH (dev fallback, must already be a python-build-standalone install)
PYBS_DIR="${VOICE_TYPER_PYBS_DIR:-}"
if [[ -n "$PYBS_DIR" && -f "$PYBS_DIR/python/python.exe" ]]; then
    PY="$PYBS_DIR/python/python.exe"
elif [[ -n "${PYBS:-}" && -f "$PYBS" ]]; then
    PY="$PYBS"
else
    PY="$(command -v python)"
    if [[ -z "$PY" ]]; then
        echo "ERROR: no python interpreter found." >&2
        echo "  Set VOICE_TYPER_PYBS_DIR to a python-build-standalone install dir, or" >&2
        echo "  install nuitka + websockets into your dev Python (ASR libs live in the worker build)." >&2
        exit 1
    fi
    echo "[build_sidecar_windows] WARNING: using 'python' from PATH ($PY)." >&2
    echo "  For release builds, use a python-build-standalone install (ADR-0020 §4.2)." >&2
fi
echo "[build_sidecar_windows] PY=$PY"

# ─── Resolve the site-packages dir of the build interpreter ──────────────────
SITE="$("$PY" -c 'import site; print(site.getsitepackages()[0])')"
echo "[build_sidecar_windows] SITE=$SITE"

# Sanity-check: the slim sidecar needs websockets only (ASR libs are the
# worker build's business now; requiring them here would re-couple the
# slim bundle to the pack it is slimmed against).
"$PY" -c 'import websockets' \
    || { echo "ERROR: build env is missing websockets" >&2; exit 1; }

# ─── Prepare output dir ──────────────────────────────────────────────────────
mkdir -p "$SIDECAR_DIR"

# ─── Run Nuitka (ADR-0020 §4.2) ──────────────────────────────────────────────
# NOTE: --onefile-tempdir-spec uses the Nuitka-documented {CACHE_DIR}
# token, which expands to the user's AppData\Local (previously
# %LOCALAPPDATA%, which Nuitka 2.8.10 does NOT support as a spec variable
# and rejects with FATAL 'Found unknown variable name').
#
# S4-CR-25 / nu-opt-1: psutil imports ALL platform submodules (_pslinux,
# _psosx, _psbsd, _pssunos, _psaix) at the module root, Nuitka compiles
# ALL of them on every OS, wasting hours. These are conditionally imported
# at runtime via sys.platform guards; exclude the non-Windows ones to save
# ~15 min of C compilation. Also removed deprecated --enable-plugin=numpy.
#
# Parallel C compilation: Nuitka invokes gcc/clang per Python module;
# --jobs=N fans those out (the default was sequential). Override with
# NUITKA_JOBS; default = nproc (present in WSL and Git Bash). Each job
# forks a C compiler (~300-500 MB RSS), so cap high counts on low-RAM hosts.
if [[ -z "${NUITKA_JOBS:-}" ]]; then
    NUITKA_JOBS="$(nproc 2>/dev/null || echo 1)"
fi
echo "[build_sidecar_windows] Nuitka --jobs=$NUITKA_JOBS"
NUITKA_ARGS=(
    --standalone --onefile
    --assume-yes-for-downloads
    --jobs="$NUITKA_JOBS"
    --enable-plugin=anti-bloat
    # NU-106 retired (Phase 1c torch-free): runtime is ONNX-only, our code
    # never imports torch. Still nofollow it: onnxruntime/transformers/
    # machine_info.py has a function-level `import torch` (GPU probe,
    # try/except-guarded, never called by us) that Nuitka follows blindly;
    # compiling torch 2.13 crashes its optimizer (torch._dynamo.pgo).
    --nofollow-import-to=scipy._lib.cobyqa
    --nofollow-import-to=scipy._lib.array_api_extra.testing
    --nofollow-import-to=sympy
    --nofollow-import-to=mpmath
    --nofollow-import-to=psutil._pslinux
    --nofollow-import-to=psutil._psosx
    --nofollow-import-to=psutil._psbsd
    --nofollow-import-to=psutil._pssunos
    --nofollow-import-to=psutil._psaix
    --nofollow-import-to=faster_whisper
    --nofollow-import-to=ctranslate2
    --nofollow-import-to=torch
    --include-package=voice_typer
    --include-package=websockets
    # ADR-0023 packaging: media ingest lazily imports yt_dlp / yt_dlp_ejs /
    # av (decoder.py, downloader.py, subtitles.py, mini_update.py).
    # av wheels bundle FFmpeg DLLs.
    --include-package=yt_dlp
    --include-package=yt_dlp_ejs
    --include-package=av
    --include-package-data=yt_dlp
    --include-package-data=voice_typer.server
    --windows-disable-console
    --onefile-tempdir-spec="{CACHE_DIR}/lausu/onefile-tmp"
    --output-filename="$OUTPUT_NAME"
    --output-dir="$SIDECAR_DIR"
    "$PROJECT_ROOT/voice_typer/server/ipc_server.py"
)
echo "[build_sidecar_windows] Running Nuitka..."
"$PY" -m nuitka "${NUITKA_ARGS[@]}"

# ─── Verify ──────────────────────────────────────────────────────────────────
if [[ ! -f "$OUTPUT_PATH" ]]; then
    echo "ERROR: $OUTPUT_PATH not built" >&2
    exit 1
fi
SIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)
echo "[build_sidecar_windows] OK: $OUTPUT_PATH (${SIZE_MB} MB)"
echo "[build_sidecar_windows] NEXT: sign with signtool (see docs/migration/signing-guide.md §13.1)."
