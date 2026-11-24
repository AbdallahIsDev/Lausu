#!/usr/bin/env bash
# Fetch and verify the pinned transcribe.cpp Windows x86_64 runner.
# Mirrors scripts/build/fetch_ffmpeg_lgpl_win64.sh: hash + size gate first,
# install beside the Nuitka sidecar in src-tauri/bin. No model is downloaded.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="$ROOT/scripts/transcribe-cpp-win64.json"
BIN_DIR="$ROOT/src-tauri/bin"

read_field() {
  python -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); print(d[sys.argv[2]])' "$MANIFEST" "$1"
}

ASSET="$(read_field asset_name)"
URL="$(read_field download_url)"
EXPECTED_SHA="$(read_field sha256)"
EXPECTED_SIZE="$(read_field archive_size_bytes)"
INSTALL_DIR="$ROOT/$(read_field install_dir)"

case "$ASSET" in
  *cpu-vulkan.tar.gz) ;;
  *) echo "Unexpected runner asset name: $ASSET" >&2; exit 1 ;;
esac

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
ARCHIVE="$WORK/$ASSET"

echo "Fetching $ASSET ..."
curl -fsSL --retry 3 -o "$ARCHIVE" "$URL"

ACTUAL_SIZE="$(python -c 'import os,sys; print(os.path.getsize(sys.argv[1]))' "$ARCHIVE")"
if [ "$ACTUAL_SIZE" != "$EXPECTED_SIZE" ]; then
  echo "Size mismatch: expected $EXPECTED_SIZE, got $ACTUAL_SIZE" >&2
  exit 1
fi
ACTUAL_SHA="$(python -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$ARCHIVE")"
if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
  echo "SHA-256 mismatch: expected $EXPECTED_SHA, got $ACTUAL_SHA" >&2
  exit 1
fi

tar -xzf "$ARCHIVE" -C "$WORK"
mkdir -p "$INSTALL_DIR" "$BIN_DIR"
python - "$MANIFEST" "$WORK" "$INSTALL_DIR" "$BIN_DIR" <<'PY'
import json
import shutil
import sys
from pathlib import Path

manifest, work, install_dir, bin_dir = map(Path, sys.argv[1:5])
names = json.loads(manifest.read_text(encoding="utf-8"))["install_names"]
for name in names:
    sources = [p for p in work.rglob(name) if p.is_file()]
    if not sources:
        raise SystemExit(f"Runner archive is missing expected file: {name}")
    for target_dir in (install_dir, bin_dir):
        shutil.copy2(sources[0], target_dir / name)
PY

echo "transcribe.cpp runner installed into $INSTALL_DIR and $BIN_DIR"
