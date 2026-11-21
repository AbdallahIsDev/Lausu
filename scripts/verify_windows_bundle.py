#!/usr/bin/env python3
"""Post-build verification gate for the Windows Tauri bundle (CI round 10).

Runs after ``cargo tauri build`` in ``tauri-windows-build`` and is also fully
runnable locally (no network, no new dependencies):

    python scripts/verify_windows_bundle.py --self-test
    python scripts/verify_windows_bundle.py --target x86_64-pc-windows-msvc \
        --sidecar <frozen exe> --wav tests/fixtures/test_440hz_1s_16k.wav \
        --nsis <installer> --msi <msi> --summary "$GITHUB_STEP_SUMMARY"

Hard gates (always fail the job):
  * bundle declares + ships ffmpeg, never ffprobe;
  * THIRD_PARTY_NOTICES.md is declared as a resource and present on disk;
  * frozen-sidecar self-check (frozen build, no PATH fallback, bundled ffmpeg,
    16000 decoded samples, RNNoise).

The GPL gate runs after the frozen self-check and scans both the exe bytes
(blind to compressed onefile payloads) and, authoritatively, DLL file names
under the pinned Nuitka onefile extraction dir. Nuitka creates that dir, not
this script, so it is left in place.

Single SOFT gate -- ``ENFORCE_NO_GPL_DLLS`` (workflow env / repo variable,
default ``'0'``): with '0' a WARNING table of libx264*/libx265*/avcodec*
sightings is printed and exit is 0 (PyAV is intentionally still bundled);
with '1' any sighting is a hard failure. No other gate in this script is soft.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = "x86_64-pc-windows-msvc"
FFMPEG_EXE = f"ffmpeg-{DEFAULT_TARGET}.exe"
FFPROBE_EXE = f"ffprobe-{DEFAULT_TARGET}.exe"
NOTICES_REL = "docs/THIRD_PARTY_NOTICES.md"
NOTICES_CONFIG_ENTRY = "../docs/THIRD_PARTY_NOTICES.md"
WINDOWS_X64_CONFIGS = (
    "tauri.windows-x86_64.conf.json",
    "tauri.windows-x86_64-slim.conf.json",
)
# Explicit, single switch. Case-insensitive: DLL names on Windows are not
# case-sensitive and Nuitka may embed mixed-case paths in the onefile.
GPL_PATTERNS = ("libx264", "libx265", "avcodec")
_GPL_RE = re.compile("|".join(re.escape(p) for p in GPL_PATTERNS), re.IGNORECASE)
# The bytes of a onefile are compressed, so the string scan above is blind to
# the payload. These filename patterns run against the extraction dir instead.
GPL_DLL_GLOBS = ("avcodec*.dll", "libx264*.dll", "libx265*.dll")
ONEFILE_SPEC_RE = re.compile(r"--onefile-tempdir-spec=[\"']([^\"'\n]+)[\"']")
PRODUCT_NAME_RE = re.compile(r"--product-name=[\"']?([^\"'\s]+)")
ONEFILE_EXTRACT_DIR_ENV = "LAUSU_ONEFILE_EXTRACT_DIR"
FREEZE_SCRIPT = REPO_ROOT / "scripts" / "build" / "build_sidecar_windows.sh"


class ExtractionHit(NamedTuple):
    """One DLL found by name in the onefile extraction dir."""

    path: Path
    reason: str


class BundleVerificationError(RuntimeError):
    """A hard gate failed."""


def _bundle_roots(target: str) -> list[Path]:
    """All locations Tauri/Nuitka stage a Windows x64 payload into."""
    base = REPO_ROOT / "src-tauri"
    return [
        base / "bin",
        base / "target" / target / "release",
        base / "target" / target / "release" / "bundle",
        base / "target" / target / "release" / "resources",
        base / "target" / "release",
        base / "target" / "release" / "bundle",
        base / "target" / "release" / "resources",
    ]


def _find_files(roots: list[Path], predicate) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            try:
                if path.is_file() and predicate(path):
                    found.append(path)
            except OSError:
                continue
    # Deterministic output; de-dupe on resolved path.
    return sorted(set(found), key=lambda p: str(p.resolve()))


def check_bundle_contents(target: str) -> list[str]:
    """a. ffmpeg shipped, no ffprobe, notices declared AND present. Hard gate."""
    problems: list[str] = []
    roots = _bundle_roots(target)

    # Config declarations (both full + slim x64 configs).
    for cfg_name in WINDOWS_X64_CONFIGS:
        cfg_path = REPO_ROOT / "src-tauri" / cfg_name
        if not cfg_path.is_file():
            problems.append(f"missing tauri config: {cfg_name}")
            continue
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        bundle = cfg.get("bundle", {})
        external = bundle.get("externalBin", [])
        resources = bundle.get("resources", [])
        if "bin/ffmpeg" not in external:
            problems.append(f"{cfg_name}: externalBin missing bin/ffmpeg ({external!r})")
        if any("ffprobe" in str(entry) for entry in external):
            problems.append(f"{cfg_name}: ffprobe must NOT be an externalBin ({external!r})")
        if NOTICES_CONFIG_ENTRY not in [str(entry) for entry in resources]:
            problems.append(f"{cfg_name}: bundle.resources missing {NOTICES_CONFIG_ENTRY!r} ({resources!r})")

    # On-disk payload.
    ffmpeg_files = _find_files(roots, lambda p: p.name.lower().startswith("ffmpeg") and p.suffix.lower() == ".exe")
    ffprobe_files = _find_files(roots, lambda p: p.name.lower().startswith("ffprobe") and p.suffix.lower() == ".exe")
    if not ffmpeg_files:
        problems.append(f"no ffmpeg exe found under bundle roots: {[str(r) for r in roots]}")
    if ffprobe_files:
        problems.append(f"ffprobe must not ship; found: {[str(p) for p in ffprobe_files]}")

    notices = REPO_ROOT / NOTICES_REL
    if not notices.is_file():
        problems.append(f"THIRD_PARTY_NOTICES.md missing at {notices}")
    staged_notices = _find_files(roots, lambda p: p.name == "THIRD_PARTY_NOTICES.md")
    if not staged_notices:
        problems.append("THIRD_PARTY_NOTICES.md not staged into any bundle resource dir")

    if problems:
        raise BundleVerificationError("bundle contents:\n  - " + "\n  - ".join(problems))
    return [
        f"ffmpeg exe present: {ffmpeg_files[0]}",
        "ffprobe absent (duration probing uses ffmpeg stderr)",
        f"THIRD_PARTY_NOTICES.md declared + staged ({len(staged_notices)} copy/copies)",
    ]


def run_sidecar_smoke(sidecar: Path, wav: Path, target: str) -> list[str]:
    """b. Frozen-sidecar self-check in an install-like layout. Hard gate.

    Tauri strips the ``-<triple>`` suffix from externalBin when installing, so
    we stage ``ffmpeg-<triple>.exe`` as plain ``ffmpeg.exe`` next to the
    sidecar before invoking ``--self-check``. That exercises the exact lookup
    path the shipped app uses; PATH fallback is impossible in a frozen build
    and the self-check also asserts the resolved ffmpeg is exe-adjacent.
    """
    if not sidecar.is_file():
        raise BundleVerificationError(f"sidecar not found: {sidecar} (cannot run frozen smoke test)")
    if not wav.is_file():
        raise BundleVerificationError(f"decoding fixture not found: {wav}")

    fetched = REPO_ROOT / "src-tauri" / "bin" / f"ffmpeg-{target}.exe"
    if not fetched.is_file():
        raise BundleVerificationError(f"fetched ffmpeg not found: {fetched} (fetch step must run first)")

    with tempfile.TemporaryDirectory(prefix="lausu-sidecar-smoke-") as tmp:
        stage = Path(tmp)
        staged_sidecar = stage / sidecar.name
        staged_ffmpeg = stage / "ffmpeg.exe"
        shutil.copy2(sidecar, staged_sidecar)
        shutil.copy2(fetched, staged_ffmpeg)
        # Strip every credential/token from the child env; the self-check
        # needs neither network nor secrets, only the staged ffmpeg + WAV.
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper() not in {"GITHUB_TOKEN", "GH_TOKEN", "LAUSU_FFMPEG", "LAUSU_FFPROBE"}
        }
        proc = subprocess.run(
            [str(staged_sidecar), "--self-check", str(wav.resolve())],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd=str(stage),
            check=False,
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        print(output, flush=True)
        if proc.returncode != 0:
            raise BundleVerificationError(
                f"frozen-sidecar --self-check exited {proc.returncode} (expected 0):\n{output}"
            )
        for marker in (
            "SELFCHECK: PASS frozen-build",
            "SELFCHECK: PASS no-path-fallback",
            "SELFCHECK: PASS bundled-ffmpeg",
            "SELFCHECK: PASS decode-samples=16000",
            "SELFCHECK: PASS rnnoise-active",
        ):
            if marker not in output:
                raise BundleVerificationError(f"frozen-sidecar self-check missing marker {marker!r}")
    return [
        "frozen sidecar resolved ffmpeg next to itself (no PATH fallback)",
        "decoded test_440hz_1s_16k.wav to 16,000 samples",
        "RNNoise active (no GTCRN fallback)",
    ]


def gpl_dll_table(paths: list[Path]) -> list[tuple[str, str, int]]:
    """c. Scan sidecar/worker onefiles + loose DLLs for GPL ffmpeg tokens.

    Chunked (1 MB) scan with a bounded carry so a 200 MB onefile never has to
    be held in memory. GPL token names are short (< 32 bytes), so a 64-byte
    carry is enough to catch a hit straddling a chunk boundary.
    """
    rows: dict[str, tuple[str, int]] = {}
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in {".dll", ".exe"}:
            continue
        carry = b""
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                buf = carry + chunk
                carry_len = len(carry)
                text = (carry + chunk).decode("latin-1", "replace")
                for match in _GPL_RE.finditer(text):
                    if match.end() <= carry_len:
                        continue  # already counted in the previous chunk
                    token = match.group(0).lower()
                    prev = rows.get(token, (str(path), 0))
                    rows[token] = (prev[0], prev[1] + 1)
                carry = buf[-64:]
    return [(token, where, count) for token, (where, count) in sorted(rows.items())]


def pinned_onefile_tempdir_spec(script: Path | None = None) -> str | None:
    """Read the sidecar's pinned Nuitka onefile spec from its freeze script."""
    path = script or FREEZE_SCRIPT
    if not path.is_file():
        return None
    match = ONEFILE_SPEC_RE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def freeze_product_name(script: Path | None = None) -> str | None:
    """Read the sidecar's --product-name from its freeze script."""
    path = script or FREEZE_SCRIPT
    if not path.is_file():
        return None
    match = PRODUCT_NAME_RE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def expand_onefile_cache_spec(spec: str, cache_dir: str, product: str | None = None) -> Path | None:
    """Expand the pinned spec's cache/product tokens.

    A spec with {PID}/{TIME}/{PROGRAM} names a throwaway dir that Nuitka
    deletes on exit; it cannot be inspected afterwards, so refuse to guess.
    """
    if any(token in spec for token in ("{PID}", "{TIME}", "{PROGRAM}")):
        return None
    prefix = "{CACHE_DIR}"
    if not spec.startswith(prefix) or not cache_dir:
        return None
    suffix = spec[len(prefix) :].lstrip("/\\")
    if "{PRODUCT}" in suffix:
        if not product:
            return None
        suffix = suffix.replace("{PRODUCT}", product)
    return Path(cache_dir) / suffix


def onefile_extraction_dir(explicit: str | None = None) -> Path | None:
    """Resolve the extraction dir left on disk after the frozen self-check."""
    if explicit:
        return Path(explicit).expanduser()
    spec = pinned_onefile_tempdir_spec()
    if spec is None:
        return None
    if os.name == "nt":
        cache = os.environ.get("LOCALAPPDATA", "")
    elif sys.platform == "darwin":
        cache = str(Path.home() / "Library" / "Caches")
    else:
        cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    product = freeze_product_name()
    if "{VERSION}" in spec:
        root = expand_onefile_cache_spec(spec.split("/{VERSION}/")[0], cache, product)
        if root is None or not root.is_dir():
            return None
        candidates = sorted(
            (p for p in root.glob("*/onefile-tmp") if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
        )
        return candidates[-1] if candidates else None
    return expand_onefile_cache_spec(spec, cache, product)


def extraction_dll_scan(root: Path) -> tuple[list[ExtractionHit], list[ExtractionHit]]:
    """Recursive name scan: GPL-name hits + the full av.libs DLL inventory."""
    gpl: list[ExtractionHit] = []
    av_libs: list[ExtractionHit] = []
    if not root.is_dir():
        return gpl, av_libs
    for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        try:
            if not path.is_file() or path.suffix.lower() != ".dll":
                continue
        except OSError:
            continue
        name = path.name.lower()
        for pattern in GPL_DLL_GLOBS:
            if fnmatch.fnmatchcase(name, pattern):
                gpl.append(ExtractionHit(path, pattern))
                break
        rel = path.relative_to(root)
        if any(part.lower() == "av.libs" for part in rel.parts[:-1]):
            av_libs.append(ExtractionHit(path, "av.libs"))
    return gpl, av_libs


def gpl_gate(sidecar: Path, target: str, enforce: str, extraction_dir: Path | None = None) -> list[str]:
    """Name scan of the onefile payload is authoritative; byte scan is not."""
    worker = REPO_ROOT / "src-tauri" / "bin" / f"lausu-worker-{target}.exe"
    loose = _find_files(_bundle_roots(target), lambda p: p.suffix.lower() == ".dll")
    rows = gpl_dll_table([sidecar, worker, *loose])
    if extraction_dir is None:
        raise BundleVerificationError(
            "onefile extraction dir could not be determined; pass --onefile-extract-dir "
            f"or set {ONEFILE_EXTRACT_DIR_ENV} to the pinned cached extraction dir"
        )
    gpl_hits, av_hits = extraction_dll_scan(extraction_dir)
    enforce_on = enforce.strip() == "1"
    has_files = extraction_dir.is_dir() and any(path.is_file() for path in extraction_dir.rglob("*"))
    reason = ""
    if not has_files:
        reason = (
            f"onefile extraction dir has nothing to scan: {extraction_dir}"
            if extraction_dir.is_dir()
            else f"onefile extraction dir does not exist: {extraction_dir}"
        )
        if enforce_on:
            raise BundleVerificationError(reason)
    lines = [
        "### GPL DLL scan",
        "",
        "exe string scan (blind to compressed onefile payloads)",
        "",
    ]
    if rows:
        lines += [
            "| token | first seen | occurrences |",
            "| --- | --- | ---: |",
        ]
        lines += [f"| `{token}` | `{where}` | {count} |" for token, where, count in rows]
    else:
        lines.append("No libx264*/libx265*/avcodec* strings found in exe bytes.")
    lines += [
        "",
        f"onefile extraction-dir name scan (authoritative; root: {extraction_dir})",
        "",
    ]
    if gpl_hits:
        lines += ["| DLL | matched |", "| --- | --- |"]
        lines += [f"| `{hit.path.name}` | `{hit.reason}` |" for hit in gpl_hits]
    else:
        lines.append("No GPL-named DLLs found in the extraction dir.")
    lines += ["", "DLLs under av.libs (inventory)", ""]
    if av_hits:
        lines += ["| DLL |", "| --- |"]
        lines += [f"| `{hit.path}` |" for hit in av_hits]
    else:
        lines.append("No DLLs under av.libs.")
    lines.append("")
    sightings = bool(rows or gpl_hits)
    if not has_files:
        lines.append(f"::warning::{reason}; extraction scan is INCONCLUSIVE, not clean.")
    if enforce_on and sightings:
        lines.append("::error::ENFORCE_NO_GPL_DLLS=1 and GPL-licensed DLLs were found.")
        print("\n".join(lines), flush=True)
        raise BundleVerificationError("GPL DLLs found while ENFORCE_NO_GPL_DLLS=1")
    if sightings:
        lines.append(
            "::warning::GPL-licensed DLLs present (PyAV is intentionally bundled); "
            "ENFORCE_NO_GPL_DLLS=0 so this is informational."
        )
    elif has_files:
        lines.append("ENFORCE_NO_GPL_DLLS check: clean.")
    print("\n".join(lines), flush=True)
    return [
        f"GPL DLL scan: {len(rows)} exe-string token(s), {len(gpl_hits)} "
        f"extraction-name hit(s), {len(av_hits)} av.libs DLL(s), enforce={enforce!r}"
    ]


def write_summary(
    summary: Path, target: str, nsis: Path | None, msi: Path | None, sidecar: Path, wav: Path, passed: list[str]
) -> None:
    """d. Sizes into GITHUB_STEP_SUMMARY (append, never overwrite)."""

    def size(p: Path | None) -> str:
        if p is None or not p.is_file():
            return "n/a"
        return f"{p.stat().st_size / (1024 * 1024):.2f} MB"

    worker = REPO_ROOT / "src-tauri" / "bin" / f"lausu-worker-{target}.exe"
    ffmpeg = REPO_ROOT / "src-tauri" / "bin" / f"ffmpeg-{target}.exe"
    lines = [
        "## Windows bundle verification gate",
        "",
        "| artifact | size |",
        "| --- | ---: |",
        f"| NSIS installer | {size(nsis)} |",
        f"| MSI installer | {size(msi)} |",
        f"| frozen sidecar | {size(sidecar)} |",
        f"| worker exe | {size(worker) if worker.is_file() else 'not in slim bundle'} |",
        f"| ffmpeg exe | {size(ffmpeg)} |",
        "",
        "### Hard checks passed",
        "",
    ]
    lines += [f"- {item}" for item in passed]
    with summary.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"Wrote size summary to {summary}", flush=True)


def self_test() -> int:
    """Pure, network-free checks of the gate's own logic (runnable locally)."""
    rows = gpl_dll_table([])
    assert rows == [], rows
    assert len(GPL_PATTERNS) == 3
    assert NOTICES_CONFIG_ENTRY.startswith("../")
    assert FFMPEG_EXE.startswith("ffmpeg-") and not FFPROBE_EXE.startswith("ffmpeg-")
    # Synthetic binary with a GPL token must be detected.
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "fake.dll"
        p.write_bytes(b"avcodec-61.dll")
        rows = gpl_dll_table([p])
        assert any(token == "avcodec" for token, _, _ in rows), rows
    spec = pinned_onefile_tempdir_spec() or ""
    assert spec == "{CACHE_DIR}/{PRODUCT}/{VERSION}/onefile-tmp", spec
    assert expand_onefile_cache_spec(spec.split("/{VERSION}/")[0], "/cache", "LausuSidecar") == Path(
        "/cache/LausuSidecar"
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "onefile-tmp"
        av_libs = root / "av.libs"
        av_libs.mkdir(parents=True)
        (root / "avcodec-62-xxxx.dll").write_bytes(b"")
        (root / "libx264-165-xxxx.dll").write_bytes(b"")
        (av_libs / "avutil-59.dll").write_bytes(b"")
        gpl_hits, av_hits = extraction_dll_scan(root)
        assert {hit.path.name for hit in gpl_hits} == {"avcodec-62-xxxx.dll", "libx264-165-xxxx.dll"}, gpl_hits
        assert {hit.path.name for hit in av_hits} == {"avutil-59.dll"}, av_hits
    with tempfile.TemporaryDirectory() as tmp:
        assert extraction_dll_scan(Path(tmp)) == ([], [])
        # An empty/missing extraction dir is never reported as "clean".
        try:
            gpl_gate(Path(tmp) / "sidecar.exe", DEFAULT_TARGET, "1", Path(tmp))
        except BundleVerificationError:
            pass
        else:
            raise AssertionError("empty extraction dir must fail under ENFORCE=1")
    print("verify_windows_bundle.py self-test: PASS", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--sidecar", type=Path)
    parser.add_argument("--wav", type=Path, default=REPO_ROOT / "tests/fixtures/test_440hz_1s_16k.wav")
    parser.add_argument("--nsis", type=Path)
    parser.add_argument("--msi", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument(
        "--enforce-no-gpl-dlls",
        default=os.environ.get("ENFORCE_NO_GPL_DLLS", "0"),
        help="0 (default): warn only. 1: fail on libx264*/libx265*/avcodec*.",
    )
    parser.add_argument(
        "--onefile-extract-dir",
        default=os.environ.get(ONEFILE_EXTRACT_DIR_ENV),
        help=(
            f"Override the Nuitka onefile extraction dir (env: {ONEFILE_EXTRACT_DIR_ENV}). "
            "Default: derive from the pinned --onefile-tempdir-spec."
        ),
    )
    parser.add_argument("--self-test", action="store_true", help="run pure logic checks only")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    passed: list[str] = []
    failed: list[str] = []

    def collect(label: str, fn) -> None:
        try:
            result = fn()
        except Exception as exc:
            detail = f"{label}: {exc}"
            failed.append(detail)
            print(f"::error::Windows bundle verification FAILED: {detail}", flush=True)
        else:
            passed.extend(result or [])

    collect("bundle contents", lambda: check_bundle_contents(args.target))
    if args.sidecar is not None:
        collect("frozen self-check", lambda: run_sidecar_smoke(args.sidecar, args.wav, args.target))
    else:
        print("verify_windows_bundle.py: no --sidecar supplied; frozen smoke SKIPPED", flush=True)
    sidecar = args.sidecar or (REPO_ROOT / "src-tauri" / "bin" / f"python-sidecar-{args.target}.exe")
    extraction_dir = onefile_extraction_dir(args.onefile_extract_dir)
    source = "explicit override" if args.onefile_extract_dir else "pinned spec (Nuitka cached mode)"
    print(
        f"onefile extraction dir: {extraction_dir} (from {source}; "
        "left in place — this script does not create or delete it)",
        flush=True,
    )
    collect(
        "GPL DLL scan",
        lambda: gpl_gate(sidecar, args.target, args.enforce_no_gpl_dlls, extraction_dir),
    )
    if args.summary is not None:
        collect(
            "size summary",
            lambda: write_summary(args.summary, args.target, args.nsis, args.msi, sidecar, args.wav, passed),
        )

    if failed:
        print(
            "Windows bundle verification FAILED CHECKS: " + " | ".join(failed),
            flush=True,
        )
        return 1
    print("Windows bundle verification gate: PASS", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
