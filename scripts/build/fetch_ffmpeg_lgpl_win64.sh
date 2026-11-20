#!/usr/bin/env bash
# Fetch, verify and install the pinned LGPL-only win64 ffmpeg/ffprobe pair.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MANIFEST="$REPO_ROOT/scripts/ffmpeg-lgpl-win64.json"
BIN_DIR="$REPO_ROOT/src-tauri/bin"
TRIPLE="x86_64-pc-windows-msvc"

# x264/x265 are only GPL-licensed when ENABLED; the LGPL build disables them.
FORBIDDEN_TOKENS=(--enable-gpl --enable-nonfree --enable-libx264 --enable-libx265)

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

# Config gate: exit 0 when the configuration is LGPL-only, 1 otherwise.
config_gate() {
    local config="$1" token
    for token in "${FORBIDDEN_TOKENS[@]}"; do
        if printf '%s\n' "$config" | grep -qiF -- "$token"; then
            printf 'ERROR: forbidden license token in ffmpeg configuration: %s\n' "$token" >&2
            return 1
        fi
    done
    return 0
}

if [[ "${1:-}" == "--check-config" ]]; then
    [[ $# -eq 2 ]] || die "--check-config needs exactly one configuration string"
    config_gate "$2"
    printf 'OK: LGPL-only configuration accepted\n'
    exit 0
fi

[[ -f "$MANIFEST" ]] || die "manifest not found: $MANIFEST"

if command -v python >/dev/null 2>&1; then
    PY=python
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    die "python is required"
fi

# Native Python cannot resolve MSYS /c/... paths under git-bash.
to_native() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}

MANIFEST_NATIVE="$(to_native "$MANIFEST")"

manifest_get() {
    "$PY" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])' \
        "$MANIFEST_NATIVE" "$1"
}

ASSET="$(manifest_get asset_name)"
DOWNLOAD_URL="$(manifest_get download_url)"
EXPECTED_SHA="$(manifest_get sha256)"

[[ "$DOWNLOAD_URL" == *"$(manifest_get release_tag)"* ]] || die "download_url is not pinned to the release tag"
[[ "$DOWNLOAD_URL" == *"$ASSET" ]] || die "download_url does not end with asset_name"
[[ "$EXPECTED_SHA" =~ ^[0-9a-fA-F]{64}$ ]] || die "manifest sha256 is not 64 hex chars"

# Naming authority: scripts/build/artifact_names.py (single source of truth).
NAMING="$REPO_ROOT/scripts/build/artifact_names.py"
NAMING_NATIVE="$(to_native "$NAMING")"
triple_ok="$("$PY" -c 'import importlib.util,sys; s=importlib.util.spec_from_file_location("an",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(sys.argv[2] in m.SUPPORTED_TRIPLES)' "$NAMING_NATIVE" "$TRIPLE")"
[[ "$triple_ok" == "True" ]] || die "unsupported target triple: $TRIPLE"
EXE_SUFFIX="$("$PY" -c 'import importlib.util,sys; s=importlib.util.spec_from_file_location("an",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m._exe_suffix(sys.argv[2]))' "$NAMING_NATIVE" "$TRIPLE")"

if [[ -x /ucrt64/bin/curl ]]; then
    CURL=/ucrt64/bin/curl
else
    CURL="$(command -v curl)" || die "curl is required"
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Native curl needs a native path; mktemp gives an MSYS path under git-bash.
if command -v cygpath >/dev/null 2>&1; then
    WORK_NATIVE="$(cygpath -w "$WORK")"
else
    WORK_NATIVE="$WORK"
fi

if [[ -n "${FFMPEG_LOCAL_ARCHIVE:-}" ]]; then
    printf 'Using local archive: %s\n' "$FFMPEG_LOCAL_ARCHIVE"
    cp -f "$FFMPEG_LOCAL_ARCHIVE" "$WORK/archive.zip"
else
    printf 'Downloading %s\n' "$DOWNLOAD_URL"
    "$CURL" -L --fail --retry 3 --retry-delay 5 -o "$WORK_NATIVE/archive.zip" "$DOWNLOAD_URL"
fi
[[ -s "$WORK/archive.zip" ]] || die "empty download"

ACTUAL_SHA="$(sha256sum "$WORK/archive.zip" | awk '{print $1}')"
[[ "$ACTUAL_SHA" == "$EXPECTED_SHA" ]] || die "SHA-256 mismatch: expected $EXPECTED_SHA got $ACTUAL_SHA"
printf 'SHA-256 verified: %s\n' "$ACTUAL_SHA"

"$PY" - "$WORK_NATIVE/archive.zip" "$WORK_NATIVE/extract" <<'PY'
import pathlib
import sys
import zipfile

archive, dest = sys.argv[1], sys.argv[2]
pathlib.Path(dest).mkdir(parents=True, exist_ok=True)
wanted = ("ffmpeg.exe", "ffprobe.exe")
found = {}
with zipfile.ZipFile(archive) as zf:
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        base = name.rsplit("/", 1)[-1]
        if base in wanted and "/bin/" in name:
            found[base] = name
    for tool in wanted:
        if tool not in found:
            raise SystemExit(f"archive is missing a bin/{tool} member")
        target = pathlib.Path(dest, tool)
        target.write_bytes(zf.read(found[tool]))
PY

FFMPEG="$WORK/extract/ffmpeg.exe"
FFPROBE="$WORK/extract/ffprobe.exe"

"$FFMPEG" -version >"$WORK/ffmpeg-version.txt" 2>&1 || die "ffmpeg -version failed"
"$FFMPEG" -L >"$WORK/ffmpeg-L.txt" 2>&1 || die "ffmpeg -L failed"
"$FFPROBE" -version >"$WORK/ffprobe-version.txt" 2>&1 || die "ffprobe -version failed"

CONFIG_LINE="$(grep -m1 '^ *configuration:' "$WORK/ffmpeg-version.txt" || true)"
[[ -n "$CONFIG_LINE" ]] || die "no configuration line in ffmpeg -version"
config_gate "$CONFIG_LINE"

PINNED_CONFIG="$(manifest_get configuration)"
if [[ -n "$PINNED_CONFIG" && "$PINNED_CONFIG" != TODO* ]]; then
    normalize() { tr -s '[:space:]' ' ' <<<"$1" | sed 's/^ *//; s/ *$//'; }
    [[ "$(normalize "$CONFIG_LINE")" == "$(normalize "$PINNED_CONFIG")" ]] || die "ffmpeg configuration drifted from the pinned manifest"
fi

mkdir -p "$BIN_DIR"
FFMPEG_OUT="$BIN_DIR/ffmpeg-${TRIPLE}${EXE_SUFFIX}"
FFPROBE_OUT="$BIN_DIR/ffprobe-${TRIPLE}${EXE_SUFFIX}"
cp -f "$FFMPEG" "$FFMPEG_OUT"
cp -f "$FFPROBE" "$FFPROBE_OUT"

REPO_ROOT_NATIVE="$(to_native "$REPO_ROOT")"
git -C "$REPO_ROOT_NATIVE" check-ignore -q "src-tauri/bin/$(basename "$FFMPEG_OUT")" || die "install path is not gitignored"
git -C "$REPO_ROOT_NATIVE" check-ignore -q "src-tauri/bin/$(basename "$FFPROBE_OUT")" || die "install path is not gitignored"

printf '\n=== ffmpeg -version ===\n'
cat "$WORK/ffmpeg-version.txt"
printf '\n=== ffmpeg -L ===\n'
cat "$WORK/ffmpeg-L.txt"
printf '\n=== ffprobe -version ===\n'
cat "$WORK/ffprobe-version.txt"
printf '\nInstalled:\n  %s\n  %s\n' "$FFMPEG_OUT" "$FFPROBE_OUT"
