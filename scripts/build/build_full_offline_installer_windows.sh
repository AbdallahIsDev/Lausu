#!/usr/bin/env bash
# =============================================================================
# Lausu. Full-offline NSIS installer build (Windows x86_64 + aarch64).
# Wraps the slim-core installer .exe + a runtime-pack zip into
# lausu-full-offline-<app-version>-<triple>.exe via makensis on
# scripts/windows/full-offline-installer.nsi (plan §4.1 / §11.9).
#
# The slim-core installer and the pack zip are built by their own jobs
# (cargo tauri build + runtime-pack-publish.yml); this script only binds
# them. Output name is canonicalized through artifact_names.py
# (C-CI-13: never invent a second naming scheme).
#
# Usage (Git Bash on Windows, or any host with makensis + python):
#   bash scripts/build/build_full_offline_installer_windows.sh \
#     --slim-core <path> --pack-zip <path> --pack-version <n> \
#     [--triple x86_64-pc-windows-msvc] [--app-version auto] [--out-dir .]
#
# Requires makensis 3.x on PATH (preinstalled on GitHub windows-latest).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SLIM_EXE=""
PACK_ZIP=""
PACK_VERSION=""
TRIPLE="x86_64-pc-windows-msvc"
APP_VERSION="auto"
OUT_DIR="."

usage() {
    echo "Usage: $0 --slim-core <path> --pack-zip <path> --pack-version <n> [--triple T] [--app-version V|auto] [--out-dir D]" >&2
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --slim-core) SLIM_EXE="$2"; shift 2 ;;
        --pack-zip) PACK_ZIP="$2"; shift 2 ;;
        --pack-version) PACK_VERSION="$2"; shift 2 ;;
        --triple) TRIPLE="$2"; shift 2 ;;
        --app-version) APP_VERSION="$2"; shift 2 ;;
        --out-dir) OUT_DIR="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "ERROR: unknown arg: $1" >&2; usage ;;
    esac
done

[[ -n "$SLIM_EXE" ]] || { echo "ERROR: --slim-core is required" >&2; usage; }
[[ -n "$PACK_ZIP" ]] || { echo "ERROR: --pack-zip is required" >&2; usage; }
[[ -n "$PACK_VERSION" ]] || { echo "ERROR: --pack-version is required" >&2; usage; }
[[ "$PACK_VERSION" =~ ^[0-9]+$ ]] || { echo "ERROR: --pack-version must be a plain integer, got '$PACK_VERSION'" >&2; exit 2; }
[[ -f "$SLIM_EXE" ]] || { echo "ERROR: slim installer not found: $SLIM_EXE" >&2; exit 1; }
[[ -f "$PACK_ZIP" ]] || { echo "ERROR: pack zip not found: $PACK_ZIP" >&2; exit 1; }
command -v makensis >/dev/null || { echo "ERROR: makensis not on PATH (NSIS 3.x required)" >&2; exit 1; }
command -v python >/dev/null || { echo "ERROR: python not on PATH (artifact_names.py)" >&2; exit 1; }

if [[ "$APP_VERSION" == "auto" ]]; then
    APP_VERSION="$(python -c "import json; print(json.load(open('$PROJECT_ROOT/src-tauri/tauri.conf.json'))['version'])")"
    echo "[full-offline] APP_VERSION=$APP_VERSION (from tauri.conf.json)"
fi

OUT_NAME="$(python "$PROJECT_ROOT/scripts/build/artifact_names.py" --full-offline --app-version "$APP_VERSION" --triple "$TRIPLE")"
mkdir -p "$OUT_DIR"
echo "[full-offline] slim=$SLIM_EXE pack=$PACK_ZIP out=$OUT_DIR/$OUT_NAME"
# The .nsi writes OutFile relative to CWD, so run from OUT_DIR (absolute
# paths keep the !defines valid regardless of working directory).
SLIM_ABS="$(cd "$(dirname "$SLIM_EXE")" && pwd)/$(basename "$SLIM_EXE")"
PACK_ABS="$(cd "$(dirname "$PACK_ZIP")" && pwd)/$(basename "$PACK_ZIP")"
OUT_ABS="$(cd "$OUT_DIR" && pwd)"
cd "$OUT_ABS"
makensis \
    "-DSLIM_CORE_EXE=$SLIM_ABS" \
    "-DPACK_ZIP=$PACK_ABS" \
    "-DPACK_VERSION=$PACK_VERSION" \
    "-DAPP_VERSION=$APP_VERSION" \
    "-DPRODUCT_TRIPLE=$TRIPLE" \
    "-Ofull-offline-installer-build.log" \
    "$PROJECT_ROOT/scripts/windows/full-offline-installer.nsi"
test -f "$OUT_ABS/$OUT_NAME" || { echo "ERROR: expected output missing: $OUT_ABS/$OUT_NAME" >&2; exit 1; }
echo "[full-offline] OK: $OUT_ABS/$OUT_NAME"
