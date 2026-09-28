#!/usr/bin/env python3
"""Build ``pack-manifest.json`` for a runtime-pack zip (schema §4.6).

Emits the exact ``OfflinePackManifest`` shape the downloader validates
(``voice_typer.server.service.offline_pack``): the top-level ``sha256`` is
the hash of the zip ARCHIVE (what ``download_offline_pack_with_resume``
verifies), and ``files[]`` lists every file member inside the zip (what
``_verify_manifest_files`` checks after extraction). The output is run
through the SAME validator the client uses before it is written, so a
manifest this script emits is guaranteed to be accepted on the download
side (E7: one authoritative schema).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Make ``voice_typer`` + ``scripts.build.artifact_names`` importable under
# every execution mode (direct script run, flat test import, package
# import). Same bootstrap pattern as ``scripts/release/publish_pack_release.py``.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from voice_typer.server.service.offline_pack import (  # noqa: E402
    OFFLINE_PACK_MAX_PER_FILE_BYTES,
    OfflinePackManifest,
    validate_offline_pack_manifest_dict,
)
from voice_typer.server.service.offline_pack.core import _safe_pack_member_name  # noqa: E402

# Worker wire-protocol floor. The worker handshake reports ``protocol=1``
# (ADR-0024 Step 6 evidence); a pack may only declare a floor it satisfies.
DEFAULT_MIN_PROTO_VERSION = 1

# Written by ``install_offline_pack`` AFTER file verification, so it must
# never travel inside the archive itself.
MANIFEST_BASENAME = "pack-manifest.json"


def _sha256_file(path: Path, *, chunk_bytes: int = 1 << 20) -> str:
    """Stream-hash *path* with SHA-256 (1 MB chunks)."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            buf = fh.read(chunk_bytes)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def iter_zip_file_members(zip_path: Path) -> list[tuple[str, int, bytes]]:
    """Return ``(name, size, sha256_hex)`` for every file member of *zip_path*.

    Directory entries are skipped (``_extract_pack_archive`` skips them too),
    so only real files reach the manifest.
    """
    entries: list[tuple[str, int, bytes]] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not _safe_pack_member_name(name):
                raise ValueError(f"unsafe archive member {name!r} (path traversal)")
            if name == MANIFEST_BASENAME:
                raise ValueError(
                    f"archive must not contain {MANIFEST_BASENAME} (install_offline_pack writes it after verification)"
                )
            if info.file_size > OFFLINE_PACK_MAX_PER_FILE_BYTES:
                raise ValueError(
                    f"archive member {name!r} size {info.file_size} exceeds "
                    f"per-file cap {OFFLINE_PACK_MAX_PER_FILE_BYTES}"
                )
            digest = hashlib.sha256()
            with zf.open(info) as src:
                while True:
                    buf = src.read(1 << 20)
                    if not buf:
                        break
                    digest.update(buf)
            entries.append((name, info.file_size, digest.hexdigest()))
    return entries


def build_pack_manifest(
    zip_path: Path,
    *,
    version: str,
    min_proto_version: int = DEFAULT_MIN_PROTO_VERSION,
) -> OfflinePackManifest:
    """Build the ``OfflinePackManifest`` describing *zip_path*.

    Raises ``ValueError`` when the archive is unusable or when the built
    manifest would be rejected by the client-side validator.
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise ValueError(f"pack zip not found: {zip_path}")
    if not version:
        raise ValueError("pack version must be non-empty")

    members = iter_zip_file_members(zip_path)
    if not members:
        raise ValueError(f"pack zip {zip_path} contains no files")

    manifest: OfflinePackManifest = {
        "version": version,
        "sha256": _sha256_file(zip_path),
        "files": [{"name": name, "sha256": digest, "size": size} for name, size, digest in members],
        "min_proto_version": min_proto_version,
    }

    validated = validate_offline_pack_manifest_dict(dict(manifest), source=str(zip_path))
    if validated is None:
        raise ValueError(f"built manifest for {zip_path} failed schema validation")
    return validated


def write_pack_manifest(manifest: OfflinePackManifest, output: Path) -> Path:
    """Write *manifest* to *output* as UTF-8 JSON and return the path."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(manifest), indent=2) + "\n", encoding="utf-8")
    return output


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build pack-manifest.json for a runtime-pack zip "
            "(OfflinePackManifest schema, plan-runtime-pack-split.md §4.6)."
        ),
    )
    parser.add_argument("--zip", type=Path, required=True, help="Path to the runtime-pack zip")
    parser.add_argument(
        "--pack-version",
        required=True,
        help="Pack version (plain integer, e.g. 3) — must match the zip's §11.9 name",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(MANIFEST_BASENAME),
        help=f"Output path (default: ./{MANIFEST_BASENAME})",
    )
    parser.add_argument(
        "--min-proto-version",
        type=int,
        default=DEFAULT_MIN_PROTO_VERSION,
        help=f"Worker wire-protocol floor (default: {DEFAULT_MIN_PROTO_VERSION})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 2 on usage/data error."""
    args = _build_arg_parser().parse_args(argv)
    try:
        manifest = build_pack_manifest(
            args.zip,
            version=args.pack_version,
            min_proto_version=args.min_proto_version,
        )
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out = write_pack_manifest(manifest, args.output)
    print(f"wrote {out} (version={manifest['version']} files={len(manifest['files'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_MIN_PROTO_VERSION",
    "MANIFEST_BASENAME",
    "build_pack_manifest",
    "iter_zip_file_members",
    "main",
    "write_pack_manifest",
]
