#!/usr/bin/env bash
# Fetch, verify and install the pinned LGPL-only win64 ffmpeg executable.
# ffprobe is NOT shipped: duration probing parses ffmpeg's own stderr header.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MANIFEST="$REPO_ROOT/scripts/ffmpeg-lgpl-win64.json"
BIN_DIR="$REPO_ROOT/src-tauri/bin"
TRIPLE="x86_64-pc-windows-msvc"

# x264/x265 are only GPL-licensed when ENABLED: `--disable-libx264` is the
# LGPL build and MUST be accepted. Gate on the full --enable-* token, never a
# bare `libx264` substring.
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
EXPECTED_SIZE="$(manifest_get archive_size_bytes)"
MIRROR_URL="$(manifest_get mirror_url)"
MIRROR_SHA="$(manifest_get mirror_sha256)"

[[ "$DOWNLOAD_URL" == *"$(manifest_get release_tag)"* ]] || die "download_url is not pinned to the release tag"
[[ "$DOWNLOAD_URL" == *"$ASSET" ]] || die "download_url does not end with asset_name"
[[ "$EXPECTED_SHA" =~ ^[0-9a-fA-F]{64}$ ]] || die "manifest sha256 is not 64 hex chars"
[[ "$EXPECTED_SIZE" =~ ^[0-9]+$ ]] || die "manifest archive_size_bytes is not an integer"
[[ "$MIRROR_URL" == https://github.com/*/releases/download/*/* ]] || die "mirror_url is not a GitHub release asset URL"
[[ "$MIRROR_URL" == *"$ASSET" ]] || die "mirror_url does not end with asset_name"
[[ "$MIRROR_SHA" =~ ^[0-9a-fA-F]{64}$ ]] || die "manifest mirror_sha256 is not 64 hex chars"
[[ "$MIRROR_SHA" == "$EXPECTED_SHA" ]] || die "mirror_sha256 differs from sha256; the mirror must be byte-identical"

# Pure, network-free fetch plan: ordered sources with their expected sha256.
if [[ "${1:-}" == "--fetch-plan" ]]; then
    printf 'mirror\t%s\t%s\n' "$MIRROR_URL" "$MIRROR_SHA"
    printf 'fallback\t%s\t%s\n' "$DOWNLOAD_URL" "$EXPECTED_SHA"
    exit 0
fi

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

# Download a GitHub release asset: gh when authenticated, else Bearer curl.
# Public fallback may use plain curl; a private source needs gh or a token.
download_asset() {
    local url="$1" out="$2" require_auth="$3"
    local repo tag asset token=""
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then token="$GITHUB_TOKEN"
    elif [[ -n "${GH_TOKEN:-}" ]]; then token="$GH_TOKEN"; fi

    if [[ "$url" =~ ^https://github\.com/([^/]+/[^/]+)/releases/download/([^/]+)/([^/]+)$ ]]; then
        repo="${BASH_REMATCH[1]}"; tag="${BASH_REMATCH[2]}"; asset="${BASH_REMATCH[3]}"
        if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
            printf 'Downloading via gh release download: %s @ %s\n' "$asset" "$tag"
            if gh release download "$tag" --repo "$repo" --pattern "$asset" --output "$out" --clobber; then
                return 0
            fi
            printf 'ERROR: gh release download failed; trying token/curl\n' >&2
            rm -f "$out"
        fi
    fi

    if [[ -n "$token" ]]; then
        printf 'Downloading via authenticated curl\n'
        if "$CURL" -L --fail --retry 3 --retry-delay 5 -H "Authorization: Bearer $token" -o "$out" "$url"; then
            return 0
        fi
        printf 'ERROR: authenticated curl download failed\n' >&2
        rm -f "$out"
        return 1
    fi

    if [[ "$require_auth" == "yes" ]]; then
        printf 'ERROR: private release source needs credentials: authenticate gh (gh auth login) or set GITHUB_TOKEN/GH_TOKEN\n' >&2
        return 1
    fi

    printf 'Downloading via curl\n'
    if "$CURL" -L --fail --retry 3 --retry-delay 5 -o "$out" "$url"; then
        return 0
    fi
    printf 'ERROR: curl download failed\n' >&2
    rm -f "$out"
    return 1
}

# Size + SHA-256 gate for one candidate; return status so the caller can try the next source.
archive_ok() {
    local path="$1" expected="$2" label="$3"
    [[ -s "$path" ]] || { printf 'ERROR: %s: empty download\n' "$label" >&2; return 1; }
    local size sha
    size="$(wc -c < "$path" | tr -d '[:space:]')"
    if [[ "$size" != "$EXPECTED_SIZE" ]]; then
        printf 'ERROR: %s: archive size mismatch: expected %s got %s\n' "$label" "$EXPECTED_SIZE" "$size" >&2
        return 1
    fi
    sha="$(sha256sum "$path" | awk '{print $1}')"
    if [[ "$sha" != "$expected" ]]; then
        printf 'ERROR: %s: SHA-256 mismatch: expected %s got %s\n' "$label" "$expected" "$sha" >&2
        return 1
    fi
    printf 'Size verified: %s bytes\nSHA-256 verified: %s\n' "$size" "$sha"
    return 0
}

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
    archive_ok "$WORK/archive.zip" "$EXPECTED_SHA" "local" || die "local archive failed verification"
else
    verified_source=""
    for label in mirror fallback; do
        if [[ "$label" == "mirror" ]]; then
            url="$MIRROR_URL"; expected="$MIRROR_SHA"; require_auth="yes"
        else
            url="$DOWNLOAD_URL"; expected="$EXPECTED_SHA"; require_auth="no"
        fi
        printf 'Trying %s source: %s\n' "$label" "$url"
        rm -f "$WORK/archive.zip"
        if download_asset "$url" "$WORK_NATIVE/archive.zip" "$require_auth" \
            && archive_ok "$WORK/archive.zip" "$expected" "$label"; then
            verified_source="$label"
            break
        fi
        printf 'Source %s did not verify; trying next source\n' "$label" >&2
    done
    [[ -n "$verified_source" ]] || die "neither mirror nor fallback produced an archive matching the pinned SHA-256"
    printf 'Verified source: %s\n' "$verified_source"
fi

"$PY" - "$WORK_NATIVE/archive.zip" "$WORK_NATIVE/extract" <<'PY'
import pathlib
import sys
import zipfile

archive, dest = sys.argv[1], sys.argv[2]
pathlib.Path(dest).mkdir(parents=True, exist_ok=True)
wanted = ("ffmpeg.exe",)
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

"$FFMPEG" -version >"$WORK/ffmpeg-version.txt" 2>&1 || die "ffmpeg -version failed"
"$FFMPEG" -L >"$WORK/ffmpeg-L.txt" 2>&1 || die "ffmpeg -L failed"

CONFIG_LINE="$(grep -m1 '^ *configuration:' "$WORK/ffmpeg-version.txt" || true)"
[[ -n "$CONFIG_LINE" ]] || die "no configuration line in ffmpeg -version"
config_gate "$CONFIG_LINE"
grep -qiF -- 'Lesser General Public License' "$WORK/ffmpeg-L.txt" || die "ffmpeg -L does not declare the LGPL"

PINNED_CONFIG="$(manifest_get configuration)"
if [[ -n "$PINNED_CONFIG" && "$PINNED_CONFIG" != TODO* ]]; then
    normalize() { tr -s '[:space:]' ' ' <<<"$1" | sed 's/^ *//; s/ *$//'; }
    [[ "$(normalize "$CONFIG_LINE")" == "$(normalize "$PINNED_CONFIG")" ]] || die "ffmpeg configuration drifted from the pinned manifest"
fi

mkdir -p "$BIN_DIR"
FFMPEG_OUT="$BIN_DIR/ffmpeg-${TRIPLE}${EXE_SUFFIX}"
cp -f "$FFMPEG" "$FFMPEG_OUT"

REPO_ROOT_NATIVE="$(to_native "$REPO_ROOT")"
git -C "$REPO_ROOT_NATIVE" check-ignore -q "src-tauri/bin/$(basename "$FFMPEG_OUT")" || die "install path is not gitignored"

printf '\n=== ffmpeg -version ===\n'
cat "$WORK/ffmpeg-version.txt"
printf '\n=== ffmpeg -L ===\n'
cat "$WORK/ffmpeg-L.txt"
printf '\nInstalled:\n  %s\n' "$FFMPEG_OUT"
