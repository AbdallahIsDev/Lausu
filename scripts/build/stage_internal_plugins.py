"""Stage the internal plugin source that the packaged sidecar ships.

This file exists so that a Nuitka build has one curated directory to embed:
``--include-data-dir=<staged>/tools/internal_plugins=tools/internal_plugins``.
The app never runs plugins from inside the binary - developer mode seeds a
writable per-user workspace from that read-only copy (see
``voice_typer/server/plugins/workspace.py``).

Runtime state is never staged. ``config.json``, ``settings.json``, ``debug/``
and the generated extension config belong to one machine's session, and the
extension's relay token is per-workspace, so shipping them would leak one
install into every build and pin a token that a fresh seed then changes.

Usage:
    python scripts/build/stage_internal_plugins.py
    python scripts/build/stage_internal_plugins.py --output build/plugins-stage
"""

from __future__ import annotations

import argparse
import fnmatch
import shutil
import sys
from pathlib import Path

SOURCE_RELATIVE = Path("tools") / "internal_plugins"
DEFAULT_OUTPUT = Path("build") / "internal_plugins_bundle"

# Directories that are never part of what the daemon imports at runtime.
SKIPPED_DIRECTORIES = frozenset(
    {
        "__pycache__",
        "node_modules",
        "debug",
        "generated",
        "test",
        "tests",
    }
)

# Per-workspace runtime state + local toggles.
SKIPPED_FILES = frozenset(
    {
        "PLUGINS_ENABLED",
        "config.json",
        "settings.json",
        "last_error.json",
        "STOP",
    }
)

SKIPPED_SUFFIXES = frozenset({".pyc", ".pyo", ".log"})

# Verification scripts stay in the repository; they are not imported by the
# daemon and a shipped build has no checkout to verify against.
SKIPPED_PATTERNS = ("test_*.py", "*_test.py", "verify_*.py", "verify_*.js")


def _should_skip_file(name: str) -> bool:
    if name in SKIPPED_FILES or name.startswith("."):
        return True
    if Path(name).suffix in SKIPPED_SUFFIXES:
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in SKIPPED_PATTERNS)


def stage(source: Path, destination: Path) -> int:
    """Copy ``source`` into ``destination``; return the number of files."""
    if not source.is_dir():
        raise SystemExit(f"plugin source not found: {source}")
    if destination.resolve().is_relative_to(source.resolve()):
        raise SystemExit("refusing to stage into the plugin source itself")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    copied = 0
    for entry in sorted(source.rglob("*")):
        relative = entry.relative_to(source)
        if any(part in SKIPPED_DIRECTORIES for part in relative.parts[:-1]):
            continue
        if entry.is_dir() or _should_skip_file(entry.name):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, target)
        copied += 1
    return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="staging root (default: build/internal_plugins_bundle)",
    )
    args = parser.parse_args(argv)
    repository_root = Path(__file__).resolve().parents[2]
    source = repository_root / SOURCE_RELATIVE
    destination = (repository_root / args.output).resolve() / SOURCE_RELATIVE
    copied = stage(source, destination)
    print(f"[stage_internal_plugins] staged {copied} files -> {destination}")
    print(f"[stage_internal_plugins] --include-data-dir={destination}=tools/internal_plugins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
