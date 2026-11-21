"""Command-line entry point for the release publisher."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from .publisher import publish_release
from .result import DEFAULT_GH_CLI, DEFAULT_REPO

if TYPE_CHECKING:
    from collections.abc import Sequence


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Publish a GitHub Release with the slim-core installer + "
            "runtime-pack zip + pack-manifest.json (asset naming: "
            "plan-runtime-pack-split.md §11.9 / artifact_names.py)."
        ),
    )
    parser.add_argument("--tag", required=True, help="Release tag (e.g. v1.2.3)")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/name repo slug")
    parser.add_argument(
        "--slim-core-windows",
        type=Path,
        default=None,
        help="Path to the Windows slim-core installer (lausu-slim-core-<version>-<triple>.exe)",
    )
    parser.add_argument(
        "--slim-core-macos",
        type=Path,
        default=None,
        help="Path to the macOS slim-core installer (lausu-slim-core-<version>-<triple>)",
    )
    parser.add_argument(
        "--slim-core-linux",
        type=Path,
        default=None,
        help="Path to the Linux slim-core installer (lausu-slim-core-<version>-<triple>)",
    )
    parser.add_argument(
        "--pack-onefile",
        type=Path,
        default=None,
        help="Path to the runtime-pack zip (lausu-runtime-pack-<pack-version>-<triple>.zip)",
    )
    parser.add_argument(
        "--pack-manifest",
        type=Path,
        default=None,
        help="Path to pack-manifest.json",
    )
    parser.add_argument(
        "--asset",
        action="append",
        type=Path,
        default=[],
        help="Additional assets to upload (repeatable)",
    )
    parser.add_argument("--notes", default=None, help="Release notes body (markdown)")
    parser.add_argument(
        "--notes-file",
        type=Path,
        default=None,
        help="Path to release notes file (mutually exclusive with --notes)",
    )
    parser.add_argument("--draft", action="store_true", help="Create as draft")
    parser.add_argument("--prerelease", action="store_true", help="Mark as pre-release")
    parser.add_argument("--target", default=None, help="Target commitish (branch/SHA)")
    parser.add_argument("--title", default=None, help="Release title (defaults to tag)")
    parser.add_argument("--gh-cli", default=DEFAULT_GH_CLI, help="gh CLI binary name")
    parser.add_argument(
        "--backend",
        choices=["gh", "api"],
        default=None,
        help="Force a specific backend (default: auto-select)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="GitHub API token (for --backend=api; defaults to GH_TOKEN/GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as JSON (for CI parsing)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point.

    Returns 0 on success, 1 on failure, 2 on usage error.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )
    # The success/failure lines use the ✓/✗ markers. A Windows console
    # defaults to cp1252, which raises UnicodeEncodeError on them and turns a
    # SUCCESSFUL publish into a traceback + exit 1 (a silent CI false-failure).
    # Reconfigure the stream instead of dropping the markers.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    # Collect assets from the named flags + --asset repeats.
    assets: list[Path] = []
    for path in (
        args.slim_core_windows,
        args.slim_core_macos,
        args.slim_core_linux,
        args.pack_onefile,
        args.pack_manifest,
    ):
        if path is not None:
            assets.append(path)
    assets.extend(args.asset)

    if not assets:
        print("error: at least one asset is required", file=sys.stderr)
        return 2

    if args.notes is not None and args.notes_file is not None:
        print("error: --notes and --notes-file are mutually exclusive", file=sys.stderr)
        return 2

    result = publish_release(
        tag=args.tag,
        assets=assets,
        repo=args.repo,
        notes=args.notes,
        notes_file=args.notes_file,
        draft=args.draft,
        prerelease=args.prerelease,
        target=args.target,
        title=args.title,
        gh_cli=args.gh_cli,
        token=args.token,
        backend=args.backend,
    )

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        if result.success:
            print(f"✓ Published release {result.tag} ({result.backend} backend)")
            if result.release_url:
                print(f"  URL: {result.release_url}")
            for name in result.uploaded:
                print(f"  uploaded: {name}")
        else:
            print(f"✗ Failed to publish release {result.tag} ({result.backend} backend)", file=sys.stderr)
            for err in result.errors:
                print(f"  error: {err}", file=sys.stderr)

    return 0 if result.success else 1


__all__ = ["main"]
