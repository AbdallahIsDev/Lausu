"""Where the plugin workspace lives, and how a packaged install gets one.

A development checkout runs straight out of ``tools/internal_plugins``: the
source is tracked in the repository and the directory is writable, so plugin
state (``config.json``, ``settings.json``, ``debug/``) sits beside it.

A packaged app cannot work that way. The sidecar ships that same tree as
read-only data inside the binary (``--include-data-dir`` lands it in the
Nuitka onefile extraction directory, which is temporary), so the first
developer-mode unlock copies it into a writable per-user workspace and every
runtime write goes there. Local state is never copied out of the bundle: only
the shipped source is.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

log = logging.getLogger("voice_typer.server.plugins.workspace")

#: Workspace path, relative to the root that contains it (repository root in a
#: checkout, the per-user developer root for a packaged install).
WORKSPACE_RELATIVE = Path("tools") / "internal_plugins"

#: Explicit workspace override (tests, and a developer running a packaged
#: build against a checkout).
ENV_FLAG = "VOICE_TYPER_PLUGINS_DIR"

#: The owner's in-app unlock writes this marker into the prepared workspace.
MARKER_NAME = "PLUGINS_ENABLED"

# Never copied into the writable workspace: local runtime state, generated
# artifacts and interpreter caches. Copying these would move one machine's
# session into the bundle or resurrect state the owner deleted.
_RUNTIME_STATE = frozenset(
    {
        MARKER_NAME,
        "config.json",
        "settings.json",
        "last_error.json",
        "STOP",
        "debug",
        "generated",
        "node_modules",
        "__pycache__",
    }
)

_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _bundle_root() -> Path | None:
    """The directory that holds ``tools/internal_plugins`` for this process.

    A Nuitka onefile bootstrap repoints the main module's ``__file__`` at the
    directory it unpacked the bundle into, and that is where data files land
    (``sys.argv[0]`` still names the original executable).
    """
    if not _is_frozen():
        # voice_typer/server/plugins/workspace.py -> repository root.
        return Path(__file__).resolve().parents[3]
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if isinstance(main_file, str) and main_file:
        return Path(main_file).resolve().parent
    return None


def bundled_plugins_dir() -> Path | None:
    """The shipped (read-only) plugin source, or ``None`` when there is none."""
    root = _bundle_root()
    if root is None:
        return None
    candidate = root / WORKSPACE_RELATIVE
    return candidate if candidate.is_dir() else None


def user_workspace_root() -> Path:
    """Per-user root that mirrors the repository layout for a packaged app."""
    from voice_typer.server.config_internals.paths import _config_dir

    return _config_dir() / "developer_plugins"


def user_plugins_dir() -> Path:
    """The writable workspace a packaged install seeds from the bundle."""
    return user_workspace_root() / WORKSPACE_RELATIVE


def resolve_plugins_dir() -> Path | None:
    """The workspace plugin state belongs to, or ``None`` when there is none.

    Order: explicit override, then (packaged) the seeded user copy, then the
    checkout. A packaged install deliberately does NOT fall back to the
    read-only bundle: discovery would list plugins whose settings, daemon
    config and browser debug all fail to write.
    """
    override = os.environ.get(ENV_FLAG)
    if override:
        candidate = Path(override)
        return candidate if candidate.is_dir() else None
    if _is_frozen():
        seeded = user_plugins_dir()
        return seeded if seeded.is_dir() else None
    return bundled_plugins_dir()


def plugin_import_root() -> Path | None:
    """``sys.path`` entry that makes ``tools.internal_plugins`` importable."""
    workspace = resolve_plugins_dir()
    if workspace is None:
        return None
    parents = workspace.parents
    # <root>/tools/internal_plugins -> <root>
    return parents[1] if len(parents) >= 2 else None


def _copy_source(source: Path, dest: Path) -> None:
    for entry in sorted(source.iterdir()):
        if entry.name in _RUNTIME_STATE or entry.name.startswith("."):
            continue
        target = dest / entry.name
        if entry.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            _copy_source(entry, target)
            continue
        if entry.suffix in _IGNORED_SUFFIXES:
            continue
        try:
            if (
                target.is_file()
                and target.stat().st_size == entry.stat().st_size
                and target.stat().st_mtime >= entry.stat().st_mtime
            ):
                continue
            shutil.copy2(entry, target)
        except OSError:
            log.warning("[PLUGINS] could not copy %s into the workspace", entry.name, exc_info=True)


def seed_workspace(source: Path, dest: Path) -> Path:
    """Copy shipped plugin source into ``dest``, preserving local state."""
    dest.mkdir(parents=True, exist_ok=True)
    _copy_source(source, dest)
    (dest / MARKER_NAME).touch(exist_ok=True)
    return dest


def ensure_developer_workspace() -> Path | None:
    """Make the plugin workspace usable, seeding it when the build is frozen.

    Idempotent and cheap after the first run: source files are refreshed only
    when they actually changed, and runtime state is never touched. Called
    from the unlock path and once at startup for an already-unlocked install,
    so a normal (non-developer) launch never reaches this function.
    """
    if not _is_frozen():
        return bundled_plugins_dir()
    source = bundled_plugins_dir()
    if source is None:
        log.warning("[PLUGINS] bundled plugin source is missing from this build")
        return None
    try:
        return seed_workspace(source, user_plugins_dir())
    except OSError:
        log.error("[PLUGINS] could not prepare the plugin workspace", exc_info=True)
        return None


__all__ = [
    "ENV_FLAG",
    "MARKER_NAME",
    "bundled_plugins_dir",
    "ensure_developer_workspace",
    "plugin_import_root",
    "resolve_plugins_dir",
    "seed_workspace",
    "user_plugins_dir",
    "user_workspace_root",
]
