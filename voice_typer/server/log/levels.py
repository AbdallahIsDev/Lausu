"""Log-level policy for the log package: module overrides and silencing.

One concern only: decide which loggers speak and at what level. Per-module
overrides (``VOICE_TYPER_LOG_LEVEL_MODULES`` plus the runtime
:func:`set_module_level` API), the third-party logger pinning, and the
``lastResort`` PII-redaction guard live here. The one-time
``setup_logging`` configuration that applies them lives in
:mod:`voice_typer.server.log.setup`, which re-exports all of this.
"""

from __future__ import annotations

import logging
import os

from voice_typer.server.log import state as _state

# Keep the historical logger name so ``caplog`` and the per-module level
# overrides keep routing every ``[LOG-SETUP]`` line the same way.
log = logging.getLogger("voice_typer.server.log")



def _json_logging_enabled() -> bool:
    """structured JSON logging is opt-in via ``VOICE_TYPER_LOG_JSON``."""
    return os.environ.get("VOICE_TYPER_LOG_JSON", "").lower() in ("1", "true", "yes")


def _apply_per_module_log_levels() -> None:
    """Apply per-module log level overrides from ``VOICE_TYPER_LOG_LEVEL_MODULES``.

    Format::

        VOICE_TYPER_LOG_LEVEL_MODULES="module.path=LEVEL,another.module=LEVEL"

    where ``LEVEL`` is a ``logging`` level name (``DEBUG``, ``INFO``,
    ``WARNING``, ``ERROR``, ``CRITICAL``).  Invalid entries are
    skipped (best-effort) so a typo in one entry does not break
    logging setup, but each skipped entry now logs a WARNING
    so the operator can see *which* entry was ignored and why, a
    silent skip was an operator trap (typo in the module path => no
    DEBUG output => operator assumes the subsystem isn't logging when
    in fact the override never applied).  Lets operators crank up
    DEBUG on a single subsystem (e.g.
    ``voice_typer.server.dictation_pipeline``) without enabling DEBUG
    globally and flooding the rotating file with high-frequency events
    from unrelated subsystems.

    Successfully applied overrides are recorded in
    :data:`_module_level_overrides` so :func:`get_module_levels` can
    report the active per-module config .
    """
    raw = os.environ.get("VOICE_TYPER_LOG_LEVEL_MODULES", "")
    if not raw:
        return
    # log to the voice_typer.server.log logger so the warning
    setup_log = logging.getLogger("voice_typer.server.log")
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            setup_log.warning(
                "[LOG-SETUP] skipping invalid VOICE_TYPER_LOG_LEVEL_MODULES entry %r (reason: missing '=')",
                entry,
            )
            continue
        name, _, level_str = entry.partition("=")
        name = name.strip()
        level_str = level_str.strip().upper()
        if not name or not level_str:
            setup_log.warning(
                "[LOG-SETUP] skipping invalid VOICE_TYPER_LOG_LEVEL_MODULES "
                "entry %r (reason: empty module name or level)",
                entry,
            )
            continue
        level = getattr(logging, level_str, None)
        if not isinstance(level, int):
            setup_log.warning(
                "[LOG-SETUP] skipping invalid VOICE_TYPER_LOG_LEVEL_MODULES "
                "entry %r (reason: unknown level %r, expected DEBUG/INFO/WARNING/ERROR/CRITICAL)",
                entry,
                level_str,
            )
            continue
        logging.getLogger(name).setLevel(level)
        # record the override so get_module_levels can report it.
        _state._module_level_overrides[name] = level_str
        setup_log.info(
            "[LOG-SETUP] set %s to %s",
            name,
            level_str,
        )



def set_module_level(name: str, level: str) -> None:
    """Set a single logger's level at runtime .

    Parameters
    ----------
    name:
        Dotted logger name (e.g. ``"voice_typer.server.dictation_pipeline"``).
    level:
        Level name (``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``,
        ``"CRITICAL"``), case-insensitive.  Invalid names raise
        :class:`ValueError`.

    Notes
    -----
    Mirrors what :func:`_apply_per_module_log_levels` does for the
    ``VOICE_TYPER_LOG_LEVEL_MODULES`` env var, but exposes a public
    API so the renderer / a future CLI / a debug overlay can change
    a subsystem's level without restarting the sidecar.  Emits an
    INFO log line so the change is visible in the rotating file (audit
    trail).  The override is recorded in :data:`_module_level_overrides`
    and is queryable via :func:`get_module_levels`.
    """
    if not name or not isinstance(name, str):
        raise ValueError(f"set_module_level: name must be a non-empty string, got {name!r}")
    level_str = (level or "").strip().upper()
    resolved = getattr(logging, level_str, None) if level_str else None
    if not isinstance(resolved, int):
        raise ValueError(
            f"set_module_level: unknown level {level!r} for module {name!r} "
            "(expected DEBUG/INFO/WARNING/ERROR/CRITICAL)"
        )
    logging.getLogger(name).setLevel(resolved)
    _state._module_level_overrides[name] = level_str
    logging.getLogger("voice_typer.server.log").info(
        "[LOG-SETUP] set %s to %s (runtime override)",
        name,
        level_str,
    )



def get_module_levels() -> dict[str, str]:
    """Return a snapshot of explicitly-set per-module level overrides .

    Returns a fresh dict (mutating the return value does not affect
    internal state).  Includes overrides applied by the
    ``VOICE_TYPER_LOG_LEVEL_MODULES`` env var at startup AND by
    subsequent :func:`set_module_level` calls.  Values are level
    *names* (``"DEBUG"`` ...) so the dict is JSON-serialisable for IPC.
    """
    return dict(_state._module_level_overrides)



def _ensure_last_resort_redacted(pii_filter: logging.Filter) -> None:
    """Ensure the global ``lastResort`` handler carries ``PIIRedactionFilter``."""
    last_resort = getattr(logging, "lastResort", None)
    if last_resort is None:
        return
    # Idempotent: skip if a PIIRedactionFilter of the same class is
    if any(isinstance(f, type(pii_filter)) for f in last_resort.filters):
        return
    last_resort.addFilter(pii_filter)


# Third-party loggers the app depends on (directly or transitively)
_THIRD_PARTY_LOGGER_LEVELS: dict[str, int] = {
    "urllib3": logging.WARNING,
    "urllib3.connectionpool": logging.WARNING,
    "requests": logging.WARNING,
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
    "websockets": logging.WARNING,
    "keyring": logging.WARNING,
    "sounddevice": logging.WARNING,
    "PIL": logging.WARNING,
    "numpy": logging.WARNING,
    "torch": logging.WARNING,
    "onnxruntime": logging.WARNING,
    "faster_whisper": logging.WARNING,
    "ctranslate2": logging.WARNING,
    "huggingface_hub": logging.WARNING,
    "transformers": logging.WARNING,
    "pystray": logging.WARNING,
    "asyncio": logging.WARNING,
}


def _apply_third_party_logger_levels() -> None:
    """Pin every logger in :data:`_THIRD_PARTY_LOGGER_LEVELS` to WARNING."""
    for name, level in _THIRD_PARTY_LOGGER_LEVELS.items():
        lib_logger = logging.getLogger(name)
        lib_logger.setLevel(level)
        lib_logger.handlers.clear()
        lib_logger.propagate = True
