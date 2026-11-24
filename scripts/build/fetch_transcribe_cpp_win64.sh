#!/usr/bin/env bash
# Fetch and verify the pinned transcribe.cpp Windows x86_64 native bundle.
# The archive contains DLLs only (NO CLI executable); they ship as bundle
# resources, beside the sidecar under resources/transcribe-cpp.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MANIFEST="$ROOT/scripts/transcribe-cpp-win64.json"

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
mkdir -p "$INSTALL_DIR"
python - "$MANIFEST" "$WORK" "$INSTALL_DIR" <<'PY'
import json
import shutil
import sys
from pathlib import Path

manifest, work, install_dir = map(Path, sys.argv[1:4])
names = json.loads(manifest.read_text(encoding="utf-8"))["install_names"]
for name in names:
    sources = [p for p in work.rglob(name) if p.is_file()]
    if not sources:
        raise SystemExit(f"Native bundle is missing expected file: {name}")
    shutil.copy2(sources[0], install_dir / name)
contracts = list(work.rglob("contract.json"))
if not contracts:
    raise SystemExit("Native bundle is missing contract.json")
shutil.copy2(contracts[0], install_dir / "contract.json")
PY

echo "transcribe.cpp native bundle installed into $INSTALL_DIR"
