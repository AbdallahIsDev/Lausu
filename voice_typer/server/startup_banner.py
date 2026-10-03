"""App-starting banner: first visible app-identity log line (C-LOG-4).

Kept free of ``LausuApp`` / heavy construction imports so the entrypoint
can emit it immediately after logging setup, before the multi-second
``voice_typer.server.app`` import and ``LausuApp()`` construction.
"""

from __future__ import annotations

import logging

from voice_typer.server.branding import APP_NAME

log = logging.getLogger("voice_typer.server.app")

_emitted = False


def reset_app_starting_banner_for_tests() -> None:
    """Test seam: allow the banner to emit again in the next test."""
    global _emitted
    _emitted = False


def emit_app_starting_banner(config) -> None:
    """Log ``{APP_NAME} starting | model=... | hotkey=... | ...`` once.

    Idempotent: the entrypoint emits early; ``AppConstruction`` re-calls
    this after config init without duplicating the line.
    """
    global _emitted
    if _emitted:
        return
    try:
        from voice_typer.server.model_registry import NO_MODEL_SIZE
        from voice_typer.server.tray_menu import display_hotkey
        from voice_typer.server.tray_models import (
            is_active_model_downloaded,
            tooltip_model_label,
        )

        try:
            model_installed = is_active_model_downloaded(config)
        except Exception:
            model_installed = True

        model_desc = tooltip_model_label(config) or str(config.model_size)
        if model_desc == NO_MODEL_SIZE or not model_desc:
            model_desc = "none"
        elif not model_installed:
            model_desc = f"{model_desc} (not installed)"

        log.info(
            "%s starting | model=%s | hotkey=%s | mic=%s | sample_rate=%s",
            APP_NAME,
            model_desc,
            display_hotkey(config.hotkey),
            config.microphone or "default",
            config.sample_rate,
        )
        _emitted = True
    except Exception:
        # Banner must never block startup; construction re-tries via
        log.debug("[STARTUP] app-starting banner failed", exc_info=True)
