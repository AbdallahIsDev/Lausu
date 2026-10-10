"""Log file locations and legacy-log migration for the log package.

One concern only: where log files live on disk (``<config_dir>/logs/``), the
per-process filename routing, and the one-time migration of pre-``logs/``
files. The session-start retention sweep (Tier 1 + Tier 2) and the one-time
``setup_logging`` configuration live in
:mod:`voice_typer.server.log.setup`; both are re-exported from there so every
existing import path keeps resolving.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

# Keep the historical logger name so ``caplog.at_level(logger="voice_typer.server.log")``
# and the per-module level overrides keep routing every ``[LOG-SETUP]`` line
# through the same logger as the rest of the package.
log = logging.getLogger("voice_typer.server.log")


# All log files live under a ``logs/`` subdirectory of the config dir
LOG_SUBDIR = "logs"

# Legacy pre-O1 log files that once lived directly in the config dir.
_LEGACY_LOG_NAMES: tuple[str, ...] = (
    "lausu.log",
    "prewarm.log",
    "worker.log",
    "startup-error.log",
    "lausu-crash-buffer.log",
)
_LEGACY_LOG_GLOBS: tuple[str, ...] = (
    "lausu.log.*",  # legacy main-process rotations
    "prewarm.log.*",  # legacy prewarm rotations
    "lausu-prewarm.log.*",  # legacy prewarm rotations (file no longer created)
)


def get_logs_dir(config_dir: Path) -> Path:
    """Return the directory that holds all log files."""
    return Path(config_dir) / LOG_SUBDIR


def _maybe_migrate_legacy_logs(config_dir: Path) -> None:
    """Move pre-``logs/`` log files from the config-dir root into ``logs/``."""
    try:
        src_root = Path(config_dir)
        dst_root = get_logs_dir(config_dir)
        if not src_root.is_dir():
            return
        for name in _LEGACY_LOG_NAMES:
            _maybe_move_legacy_log_file(src_root, dst_root, name)
        for pattern in _LEGACY_LOG_GLOBS:
            for src in src_root.glob(pattern):
                if not src.is_file() or src.name.endswith(".lock"):
                    continue
                _maybe_move_legacy_log_file(src_root, dst_root, src.name)
    except Exception as exc:  # noqa: BLE001, best-effort migration
        log.debug("[LOG-SETUP] legacy log migration failed: %s", exc)


def _maybe_move_legacy_log_file(src_root: Path, dst_root: Path, name: str) -> None:
    """Move one legacy log file from ``src_root`` to ``dst_root`` if safe."""
    try:
        src = src_root / name
        dst = dst_root / name
        if not src.is_file() or dst.exists():
            return
        dst_root.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
        log.info("[LOG-SETUP] migrated legacy log file %s -> %s", src, dst)
    except Exception as exc:  # noqa: BLE001, best-effort migration
        log.debug("[LOG-SETUP] legacy log migration skipped %s: %s", name, exc)


def get_log_file_path(config_dir: Path | None = None, *, process_name: str = "main") -> Path:
    """Return the absolute path to the log file for the given process.

    used by agent 2-y for the in-app log viewer (``View Main
    Log`` button alongside ``Open Log Folder``).  Centralising the
    literal here means the viewer and ``setup_logging`` agree on the
    filename even if it ever changes.

    The ``process_name`` parameter routes each long-lived process to
    its OWN file so concurrent writers never share a file descriptor
    on the same file (which would race on the
    :class:`_SecureTruncatingFileHandler`'s in-place truncation
    rotation: see ``tests/test_log_multiprocess.py`` for
    the failure mode).

    Routing table:

    - ``"main"`` (default) and any unrecognised value → ``lausu.log``
    - ``"prewarm"`` → ``prewarm.log``
    - ``"worker"`` → ``worker.log`` (the runtime-pack WebSocket worker
      spawned by the Tauri host; without this case it would fall
      through to ``lausu.log`` and race the slim-core sidecar's
      rotation, the same race that motivated the ``prewarm`` case).

    Parameters
    ----------
    config_dir:
        Optional override (e.g. tests pointing at ``tmp_path``).  When
        ``None``, the canonical config dir is resolved via
        :func:`voice_typer.server._paths.config_dir` (lazy import to
        avoid circular imports at module load time).
    process_name:
        ``"main"`` (default), ``"prewarm"``, or ``"worker"``. Controls
        which log file is returned.  An unrecognised value falls back
        to the main log path (defensive: see
        ``test_get_log_file_path_unknown_process_name_falls_back_to_main``).

    Returns
    -------
    Path
        ``<config_dir>/logs/lausu.log`` / ``<config_dir>/logs/prewarm.log`` /
        ``<config_dir>/logs/worker.log``.  The path may not yet exist on disk —
        callers should check ``.exists()`` before opening.
    """
    if config_dir is None:
        from voice_typer.server import _paths

        config_dir = _paths.config_dir()
    logs_dir = get_logs_dir(config_dir)
    if process_name == "prewarm":
        # Single-file policy: the prewarm process writes to ONE file —
        return logs_dir / "prewarm.log"
    if process_name == "worker":
        # Single-file policy: the runtime-pack WebSocket worker
        return logs_dir / "worker.log"
    return logs_dir / "lausu.log"
