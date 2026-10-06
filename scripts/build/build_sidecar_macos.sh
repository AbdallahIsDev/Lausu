#!/usr/bin/env bash
# =============================================================================
# Lausu. Nuitka sidecar build (macOS x86_64 + aarch64)
# ADR-0020 §4.3. Nuitka freeze of voice_typer/server/ipc_server.py into
# python-sidecar-<triple>, using python-build-standalone as the base
# interpreter.
#
# Output:
#   src-tauri/bin/python-sidecar-x86_64-apple-darwin
#   src-tauri/bin/python-sidecar-aarch64-apple-darwin
#
# This script is designed to run on a macOS host. For x86_64 on an Apple
# Silicon host, the script relies on Rosetta 2 being installed (the CI
# workflow installs it explicitly).
#
# Usage:
#   bash scripts/build/build_sidecar_macos.sh aarch64   # default (host arch)
#   bash scripts/build/build_sidecar_macos.sh x86_64    # Intel (via Rosetta)
#   bash scripts/build/build_sidecar_macos.sh --check   # verify toolchain
#
# ADR-0020 §4.3 mandates:
#   - python-build-standalone cpython-3.12.x+<arch>-apple-darwin
#   - --standalone --onefile
#   - --nofollow-import-to=faster_whisper --nofollow-import-to=ctranslate2
#     (ADR-0025 C7: ASR lives in the pack worker; the ctranslate2 data-dir
#     copies below were deleted in the same change, the WORKER build owns
#     them now)
#   - --include-package=voice_typer --include-package=websockets
#   - --macos-create-bundle --macos-app-name=LausuSidecar
#   - --macos-signed-app-name=com.Lausu.sidecar
#   - --macos-app-mode=background   (LSUIElement=true, no Dock icon)
#
# Codesign (S5-CR-56): Nuitka's `--macos-signed-app-name` only sets the
# bundle's signed name during bundle creation, it does NOT actually
# invoke codesign on the output binary. This script explicitly signs the
# output binary:
#   - If $MAC_SIGNING_IDENTITY is set (CI release builds), passes
#     `--macos-sign-identity="$MAC_SIGNING_IDENTITY"` to Nuitka so the
#     binary is signed at build time with a Developer ID Application cert.
#   - If $MAC_SIGNING_IDENTITY is empty (local dev builds), falls back to
#     ad-hoc `codesign --force --sign -` on the output binary, mirroring
#     `build_native_listener_macos.sh`. Ad-hoc signing lets the parent
#     `.app` re-sign --deep during the Tauri bundle step.
#
# (C7: the slim sidecar excludes ctranslate2; the note about its wheel
# layout that lived here moved to the WORKER build, which still bundles it.)
# =============================================================================
set -euo pipefail

# ─── Path resolution ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SIDECAR_DIR="$PROJECT_ROOT/src-tauri/bin"

# ─── Args ────────────────────────────────────────────────────────────────────
ARCH="${1:-}"
if [[ "$ARCH" == "--check" ]]; then
    echo "[build_sidecar_macos] --check: verifying toolchain"
    command -v python3 >/dev/null || { echo "MISSING: python3" >&2; exit 1; }
    python3 -c "import nuitka" 2>/dev/null || { echo "MISSING: nuitka" >&2; exit 1; }
    python3 -c "import websockets" 2>/dev/null || { echo "MISSING: websockets" >&2; exit 1; }
    command -v swiftc >/dev/null || { echo "MISSING: swiftc (Xcode CLT)" >&2; exit 1; }
    echo "[build_sidecar_macos] OK: toolchain ready"
    exit 0
fi

if [[ -z "$ARCH" ]]; then
    # Default to host arch.
    case "$(uname -m)" in
        arm64)    ARCH="aarch64" ;;
        x86_64)   ARCH="x86_64" ;;
        *) echo "ERROR: unsupported host arch: $(uname -m)" >&2; exit 1 ;;
    esac
fi

case "$ARCH" in
    x86_64|aarch64) ;;
    *) echo "ERROR: arch must be x86_64 or aarch64 (got: $ARCH)" >&2; exit 1 ;;
esac

TRIPLE="${ARCH}-apple-darwin"
OUTPUT_NAME="python-sidecar-${TRIPLE}"
OUTPUT_PATH="$SIDECAR_DIR/$OUTPUT_NAME"

echo "[build_sidecar_macos] ARCH=$ARCH TRIPLE=$TRIPLE"
echo "[build_sidecar_macos] OUTPUT=$OUTPUT_PATH"

# ─── Locate the python-build-standalone interpreter ──────────────────────────
# Priority:
#   1. $VOICE_TYPER_PYBS_DIR/python/bin/python3 (set by CI workflow)
#   2. $PYBS env var
#   3. `python3` from PATH (dev fallback)
PYBS_DIR="${VOICE_TYPER_PYBS_DIR:-}"
if [[ -n "$PYBS_DIR" && -f "$PYBS_DIR/python/bin/python3" ]]; then
    PY="$PYBS_DIR/python/bin/python3"
elif [[ -n "${PYBS:-}" && -f "$PYBS" ]]; then
    PY="$PYBS"
else
    PY="$(command -v python3)"
    if [[ -z "$PY" ]]; then
        echo "ERROR: no python3 interpreter found." >&2
        exit 1
    fi
    echo "[build_sidecar_macos] WARNING: using 'python3' from PATH ($PY)." >&2
    echo "  For release builds, use a python-build-standalone install (ADR-0020 §4.3)." >&2
fi
echo "[build_sidecar_macos] PY=$PY"

# ─── Resolve site-packages ───────────────────────────────────────────────────
SITE="$("$PY" -c 'import site; print(site.getsitepackages()[0])')"
echo "[build_sidecar_macos] SITE=$SITE"

"$PY" -c 'import websockets' \
    || { echo "ERROR: build env missing websockets" >&2; exit 1; }

# Nuitka optimizer crashes on av's Cython .py shims
# (assert micro_passes == 0, upstream issue 3970); each has a
# precompiled twin Python prefers, so the helper deletes only those.
"$PY" "$PROJECT_ROOT/scripts/build/strip_av_cython_shims.py" \
    || { echo "ERROR: av shim strip failed" >&2; exit 1; }

# ─── Prepare output dir ──────────────────────────────────────────────────────
mkdir -p "$SIDECAR_DIR"

# ─── Run Nuitka (ADR-0020 §4.3) ──────────────────────────────────────────────
# Parallel C compilation: Nuitka invokes clang per Python module;
# --jobs=N fans those out (the default was sequential). Override with
# NUITKA_JOBS. Default = core count (sysctl), CLAMPED to 4 for CI: this
# script runs in the macOS release workflow on hosted runners with
# limited RAM (each C-compiler job forks ~300-500 MB RSS; the Windows
# release workflow already uses --jobs=3 as precedent). An explicit
# NUITKA_JOBS override bypasses the clamp.
if [[ -z "${NUITKA_JOBS:-}" ]]; then
    NUITKA_JOBS="$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 1)"
    if [[ "$NUITKA_JOBS" -gt 4 ]]; then
        NUITKA_JOBS=4
    fi
fi
echo "[build_sidecar_macos] Nuitka --jobs=$NUITKA_JOBS"
echo "[build_sidecar_macos] Running Nuitka..."
NUITKA_ARGS=(
    --standalone --onefile
    --assume-yes-for-downloads
    --jobs="$NUITKA_JOBS"
    --enable-plugin=numpy
    --enable-plugin=anti-bloat
    # yt-dlp extractors (~940 modules + the 781KB lazy_extractors hub)
    # ship as bytecode: compiling them OOMs the C compiler (MSVC
    # C1060/C1002) and bloats the binary; yt-dlp lazy-loads them via
    # importlib at runtime, which resolves bytecode modules fine
    # (Nuitka anti-bloat "bytecode" mode, same as its eventlet rules).
    --noinclude-custom-mode=yt_dlp.extractor:bytecode
    # Phase 1c torch-free: our code never imports torch. Still nofollow it:
    # onnxruntime's guarded probe import drags torch into Nuitka, which
    # crashes on torch 2.13 (full story in build_sidecar_windows.sh).
    --nofollow-import-to=transformers
    --nofollow-import-to=faster_whisper
    --nofollow-import-to=ctranslate2
    --nofollow-import-to=torch
    --include-package=voice_typer
    --include-package=websockets
    # ADR-0023 packaging: media ingest lazily imports yt_dlp / yt_dlp_ejs /
    # av (decoder.py, downloader.py, subtitles.py, mini_update.py).
    --include-package=yt_dlp
    --include-package=yt_dlp_ejs
    --include-package=av
    --include-package-data=yt_dlp
    --include-package-data=voice_typer.server
    --macos-create-bundle
    --macos-app-name=LausuSidecar
    --macos-signed-app-name=com.Lausu.sidecar
    --macos-app-mode=background
    --onefile-tempdir-spec="$HOME/Library/Application Support/lausu/onefile-tmp"
    --output-filename="$OUTPUT_NAME"
    --output-dir="$SIDECAR_DIR"
    "$PROJECT_ROOT/voice_typer/server/ipc_server.py"
)
if [[ -n "${MAC_SIGNING_IDENTITY:-}" ]]; then
    # S5-CR-56: pass the Developer ID Application identity to Nuitka so it
    # signs the binary at build time. `--macos-signed-app-name` only sets
    # the bundle's signed name; it does not invoke codesign.
    NUITKA_ARGS+=(--macos-sign-identity="$MAC_SIGNING_IDENTITY")
fi
"$PY" -m nuitka "${NUITKA_ARGS[@]}"

# ─── Verify ──────────────────────────────────────────────────────────────────
if [[ ! -f "$OUTPUT_PATH" ]]; then
    echo "ERROR: $OUTPUT_PATH not built" >&2
    exit 1
fi
chmod +x "$OUTPUT_PATH"
SIZE_MB=$(du -m "$OUTPUT_PATH" | cut -f1)
echo "[build_sidecar_macos] OK: $OUTPUT_PATH (${SIZE_MB} MB)"

# S5-CR-56: ad-hoc codesign fallback when no Developer ID identity is set.
# Mirrors `build_native_listener_macos.sh`. When MAC_SIGNING_IDENTITY is set,
# Nuitka already signed the binary at build time via --macos-sign-identity
# (see above), skip the ad-hoc fallback in that case.
if [[ -z "${MAC_SIGNING_IDENTITY:-}" ]] && command -v codesign >/dev/null; then
    echo "[build_sidecar_macos] Ad-hoc codesign (parent .app will re-sign --deep)..."
    codesign --force --sign - "$OUTPUT_PATH" || true
fi

echo "[build_sidecar_macos] NEXT: codesign + notarize (see docs/migration/signing-guide.md §13.2)."
