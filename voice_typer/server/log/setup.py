"""One-time logging setup and the session-start retention sweep.

One concern only: bring the logging subsystem up once per process, path
routing, directory/file permissions, the rotating file handler, the console
handler, and the session-start retention sweep (Tiers 1 + 2).

Split leaves, both re-exported below so every existing import path keeps
resolving:

- :mod:`voice_typer.server.log.paths`, log dir + filename routing and the
  legacy-log migration (``get_logs_dir``, ``get_log_file_path``,
  ``_maybe_migrate_legacy_logs``).
- :mod:`voice_typer.server.log.levels`, per-module level overrides, the
  third-party logger pinning, and the ``lastResort`` redaction guard
  (``_apply_per_module_log_levels``, :func:`set_module_level`,
  :func:`get_module_levels`, ``_apply_third_party_logger_levels``).

``setup_logging`` resolves :func:`_sweep_stale_logs` and
:class:`~voice_typer.server.log.handlers._SecureTruncatingFileHandler`
via the package object at call time so tests that
``monkeypatch.setattr(voice_typer.server.log, ...)`` keep working after
the split (C-ARCH-2 sibling-module late lookup).
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path

# Centralized log-retention constants.  Mirror the Rust-side
from voice_typer.server._log_constants import (
    LOG_AGE_RETENTION_SECONDS,
    LOG_MAX_BYTES,
    LOG_SIZE_FALLBACK_BYTES,
)
from voice_typer.server.log import state as _state
from voice_typer.server.log.formatters import (
    _ColorFormatter,
    _FileFormatter,
    _JsonFormatter,
    _TerminalFormatter,
)
from voice_typer.server.log.handlers import (
    _BubbleLevelExclusionFilter,
    _FlushingStreamHandler,
    _SessionFilter,
)

# Keep the historical logger name so ``caplog.at_level(..., logger="voice_typer.server.log")``
# keeps capturing this module's lines.
log = logging.getLogger("voice_typer.server.log")


def _sweep_stale_logs(config_dir: Path) -> None:
    """Delete stale log files at session start (Tiers 1 + 2).

    Three-tier cleanup design: this function implements Tiers 1 and 2
    (the session-start sweeps); Tier 3 (the mid-session hard ceiling)
    lives in the ``_SecureTruncatingFileHandler`` rollover path:

      * **Tier 1, age (primary):** any log file in ``logs/`` whose last
        write is older than ``LOG_AGE_RETENTION_SECONDS`` (7 days) is
        deleted. Bounds storage for low-traffic installs whose logs
        would otherwise sit forever.

      * **Tier 2, size fallback:** any log file larger than
        ``LOG_SIZE_FALLBACK_BYTES`` (25 MB) is deleted even if freshly
        written, covers a marathon session that pushed a log past the
        fallback between startups. Checked ONLY here (session start),
        never mid-session.

    Runs at the TOP of :func:`setup_logging`: BEFORE the rotating file
     handler opens ``lausu.log``, so the active file itself can be
    deleted when stale/oversized and a fresh one is created for the new
    session ("cleans everything up and starts fresh").

    Scope: every regular file in ``logs/`` EXCEPT the inter-process
    truncation lock files (``*.lock``), they must persist across setups
    so the next process can acquire the flock. This covers Python-owned
    logs (``lausu.log``, ``worker.log``, ``prewarm.log``,
    ``startup-error.log``, ``lausu-crash-buffer.log``) AND the
    host-owned logs (``lausu-rust.log`` + rotations, plus any
    legacy host log files still on disk). Files locked by another live
    process (e.g. the Rust host's logs in dev mode, where the host
    started first) fail the unlink, skipped silently; their owner
    sweeps them at its own startup (mirrored in
    ``src-tauri/src/platform/logging.rs``).

    Best-effort, any error is logged at DEBUG and swallowed so a single
    unreadable file does not abort the sweep or ``setup_logging``.
    Idempotent if called multiple times.
    """
    try:
        root = get_logs_dir(config_dir)
        if not root.is_dir():
            return
        now = time.time()
        for f in root.iterdir():
            # Skip directories and the inter-process truncation lock
            if not f.is_file() or f.name.endswith(".lock"):
                continue
            try:
                stat = f.stat()
            except OSError:
                continue
            age = now - stat.st_mtime
            oversized = stat.st_size > LOG_SIZE_FALLBACK_BYTES
            if age <= LOG_AGE_RETENTION_SECONDS and not oversized:
                continue
            reason = f"age={age / 86400:.1f}d" if age > LOG_AGE_RETENTION_SECONDS else ""
            if oversized:
                size_mb = stat.st_size / (1024 * 1024)
                reason = f"{reason}{'+' if reason else ''}size={size_mb:.1f}MB"
            try:
                f.unlink()
                log.debug(
                    "[LOG-SETUP] purged stale log %s (%s)",
                    f.name,
                    reason,
                )
            except OSError as exc:
                # Locked by another live process (host-first launch
                log.debug(
                    "[LOG-SETUP] failed to purge stale log %s: %s",
                    f.name,
                    exc,
                )
    except Exception as exc:  # noqa: BLE001, best-effort sweep
        log.debug("[LOG-SETUP] stale-log sweep failed: %s", exc)


def setup_logging(
    config_dir: Path,
    *,
    debug: bool = False,
    quiet: bool = False,
    port_mode: bool = False,
    process_name: str = "main",
) -> str:
    """Configure Lausu logging, rotating file + optional coloured console.

    Call this **once** at process startup, before any subsystem logs.
    It is safe to call multiple times (subsequent calls are idempotent).

    Parameters
    ----------
    config_dir:
        Directory where the rotating log file will be created.
    debug:
        If ``True``, the stderr handler AND the rotating file handler
        emit DEBUG-level messages .  When ``False`` both
        handlers sit at INFO so production runs do not churn through
        5 MiB x 5 of DEBUG noise.
    quiet:
        If ``True``, the file handler is set to WARNING level
        (reduces telemetry noise for enterprise deployments).
    port_mode:
        Accepted for backwards compatibility. NO LONGER forces coloured
        stderr output: ANSI colours are gated on
        ``sys.stderr.isatty()`` so ``--port`` runs whose stderr is
        redirected to a file stay plain and grep-friendly, while a
        terminal ``--port`` run still gets colours (a terminal IS a
        TTY, so the old ``or port_mode`` was redundant for the case it
        was designed for).
    process_name:
        Routes the rotating file handler to a per-process file so
        concurrent processes don't race on the same file.  ``"main"``
        (default) → ``lausu.log``; ``"prewarm"`` → ``prewarm.log``;
        ``"worker"`` → ``worker.log``.  The runtime-pack worker
        (``voice_typer/worker/__main__.py``) passes ``"worker"`` so it
        doesn't share a file descriptor with the slim-core sidecar
        (both writing to ``lausu.log`` would race on the
        ``_SecureTruncatingFileHandler``'s in-place truncation
        rotation).  An unrecognised value falls back to
        ``lausu.log``.

    Returns
    -------
    The 8-character hex session ID for this process.
    """
    # C-ARCH-2: resolve patchable collaborators via the public package
    import voice_typer.server.log as _log_pkg

    # tighten the process umask to 0o077 while creating log
    _old_umask = os.umask(0o077)
    try:
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")  # noqa: SIM115, must outlive setup_logging()
            _state._devnull_files.append(sys.stderr)
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")  # noqa: SIM115, must outlive setup_logging()
            _state._devnull_files.append(sys.stdout)
        if sys.stdin is None:
            sys.stdin = open(os.devnull, encoding="utf-8")  # noqa: SIM115, must outlive setup_logging()
            _state._devnull_files.append(sys.stdin)

        # When spawned by the Rust Tauri host, accept the host's
        _host_session_id = os.environ.get("VOICE_TYPER_SESSION_ID", "")
        if _host_session_id and re.fullmatch(r"[0-9a-f]{8}", _host_session_id):
            _session_id = _host_session_id
        else:
            _session_id = uuid.uuid4().hex[:8]
        # Canonical store is the package attribute (tests snapshot/
        _log_pkg.__dict__["_session_id"] = _session_id

        config_dir.mkdir(parents=True, exist_ok=True)
        # lock down the config dir itself so co-located users
        if os.name == "posix":
            with contextlib.suppress(OSError):
                os.chmod(config_dir, 0o700)
        # All log files (main / prewarm / worker / crash buffer /
        logs_dir = get_logs_dir(config_dir)
        logs_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            with contextlib.suppress(OSError):
                os.chmod(logs_dir, 0o700)
        _maybe_migrate_legacy_logs(config_dir)
        # MUST run BEFORE the file handler below opens
        _log_pkg._sweep_stale_logs(config_dir)
        # Single-file policy: process_name routes each long-lived
        log_file = get_log_file_path(config_dir, process_name=process_name)

        # structured JSON logging is opt-in via VOICE_TYPER_LOG_JSON.
        json_mode = _json_logging_enabled()
        _file_formatter = _JsonFormatter() if json_mode else _FileFormatter()

        # use ``errors='backslashreplace'`` so Unicode
        handler = _log_pkg._SecureTruncatingFileHandler(
            log_file,
            # Single-file policy: ZERO backups.  When the file exceeds
            maxBytes=LOG_MAX_BYTES,
            backupCount=0,
            encoding="utf-8",
            errors="backslashreplace",
        )
        # lock down the log file itself (0o600, only the
        if os.name == "posix":
            with contextlib.suppress(OSError):
                os.chmod(log_file, 0o600)
        # gate the file handler on the ``debug`` flag so
        handler.setLevel(logging.WARNING if quiet else (logging.DEBUG if debug else logging.INFO))
        # ADR-0020 §11: keep high-frequency ``bubble_level`` events out of
        handler.addFilter(_BubbleLevelExclusionFilter())
        handler.setFormatter(_file_formatter)

        # PII / API-key redaction, imported lazily to avoid circular imports
        from voice_typer.server.security import PIIRedactionFilter as _PIIRedactionFilter

        _pii_filter = _PIIRedactionFilter()
        handler.addFilter(_pii_filter)
        # Attach ``_SessionFilter`` to the file handler
        _session_filter = _SessionFilter()
        handler.addFilter(_session_filter)

        root = logging.getLogger("voice_typer")
        # Avoid duplicate handlers if setup is called multiple times.
        _new_file_level = handler.level
        _new_file_formatter = handler.formatter
        for _existing in root.handlers:
            if isinstance(_existing, _log_pkg._SecureTruncatingFileHandler):
                _existing.setLevel(_new_file_level)
                if _new_file_formatter is not None:
                    _existing.setFormatter(_new_file_formatter)
        if not any(isinstance(h, _log_pkg._SecureTruncatingFileHandler) for h in root.handlers):
            root.addHandler(handler)
        # PII + session filters are attached to each HANDLER

        root.setLevel(logging.DEBUG)

        # quiet mode for enterprise deployments
        if quiet:
            root.setLevel(logging.WARNING)

        # Per-module log level overrides (env: VOICE_TYPER_LOG_LEVEL_MODULES).
        _apply_per_module_log_levels()

        # Silence noisy third-party loggers (urllib3 / websockets /
        _apply_third_party_logger_levels()

        # Ensure the global ``lastResort`` handler also
        _ensure_last_resort_redacted(_pii_filter)

        # ``line_buffering=True`` flushes on every newline, so each log
        if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
            with contextlib.suppress(OSError):
                sys.stderr.reconfigure(errors="backslashreplace", line_buffering=True)
        if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
            with contextlib.suppress(OSError):
                sys.stdout.reconfigure(errors="backslashreplace", line_buffering=True)

        # always flush after each emit so terminal log lines appear
        do_color = bool(sys.stderr is not None and sys.stderr.isatty())
        if sys.stderr is not None:
            stream = _FlushingStreamHandler()
            stream.setLevel(logging.DEBUG if debug else logging.INFO)
            if do_color:
                # in JSON mode the console also emits structured
                stream.setFormatter(_JsonFormatter() if json_mode else _ColorFormatter())
            else:
                # Non-TTY (Tauri sidecar, piped stderr, log redirection):
                # plain time-only terminal shape (no date, no ANSI);
                # the dated shape stays file-only.
                stream.setFormatter(_JsonFormatter() if json_mode else _TerminalFormatter())
            # attach the same PII / API-key redaction filter to the
            stream.addFilter(_pii_filter)
            # Same reasoning as the file handler, attach
            stream.addFilter(_SessionFilter())
            # Avoid duplicate StreamHandlers if setup is called multiple times.
            _new_stream_level = stream.level
            _new_stream_formatter = stream.formatter
            for _existing in root.handlers:
                if isinstance(_existing, _FlushingStreamHandler):
                    _existing.setLevel(_new_stream_level)
                    if _new_stream_formatter is not None:
                        _existing.setFormatter(_new_stream_formatter)
            if not any(isinstance(h, _FlushingStreamHandler) for h in root.handlers):
                root.addHandler(stream)

        return _session_id
    finally:
        os.umask(_old_umask)

# Facade re-exports: the log-path helpers (``paths``) and the log-level policy
# (``levels``) keep resolving through this module, so the package re-export
# list in ``voice_typer/server/log/__init__.py`` and every existing import
# path stay intact.
from voice_typer.server.log.levels import (  # noqa: E402,F401  # facade re-export
    _THIRD_PARTY_LOGGER_LEVELS,
    _apply_per_module_log_levels,
    _apply_third_party_logger_levels,
    _ensure_last_resort_redacted,
    _json_logging_enabled,
    get_module_levels,
    set_module_level,
)
from voice_typer.server.log.paths import (  # noqa: E402,F401  # facade re-export
    _LEGACY_LOG_GLOBS,
    _LEGACY_LOG_NAMES,
    LOG_SUBDIR,
    _maybe_migrate_legacy_logs,
    _maybe_move_legacy_log_file,
    get_log_file_path,
    get_logs_dir,
)
