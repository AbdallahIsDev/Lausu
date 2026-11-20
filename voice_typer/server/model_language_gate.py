"""Refuse a dictation whose spoken language the active model cannot decode.

A pinned spoken language outside the model's own published language list
is a mismatch the decode cannot recover from: Parakeet Ultra has no Arabic,
so hinting it Arabic yields junk and Whisper's English-only junk guard
deletes the whole take. The user must be told before any audio is captured,
in the app and in the OS notification area, with the recovery action
(C-UXERR-4) pointing at the Models page.

Only the LOCAL model is gated: a selected internal plugin or the cloud
backend owns its own language support, so the local capability list is not
the authority there.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from voice_typer.server import event_bus, i18n as _i18n
from voice_typer.server.branding import APP_NAME
from voice_typer.server.model_language_support import supports_language
from voice_typer.server.model_registry import get_model_metadata

log = logging.getLogger("voice_typer.server.model_language_gate")

MODELS_PATH = "/models"

#: Revert the tray ERROR state after the refusal message has been read.
_TRAY_ERROR_REVERT_S = 3.0


@dataclass(frozen=True)
class UnsupportedLanguage:
    """One model/language pair the active model cannot transcribe."""

    model_name: str
    language: str


def unsupported_language(config: Any | None) -> UnsupportedLanguage | None:
    """Return the model/language mismatch for ``config``, or None.

    None means "no pinned mismatch": Auto (``language=""``), a cloud
    backend (its own model list), an unknown model id, or a language the
    model's published list contains.
    """
    if str(getattr(config, "asr_backend", "") or "") == "cloud":
        return None
    model_size = str(getattr(config, "model_size", "") or "")
    if not model_size:
        return None
    meta = get_model_metadata(model_size)
    if meta is None:
        return None
    language = str(getattr(config, "language", "") or "")
    if supports_language(meta.supported_languages, language):
        return None
    return UnsupportedLanguage(model_name=meta.display_name or meta.name, language=language)


def language_display_name(language: str) -> str:
    """Localized language name, or the upper-cased code when unnamed.

    The names are the renderer's existing ``settings.language*`` strings,
    pushed under ``model_language.<code>`` on every locale change, so no
    second translation table exists here.
    """
    key = f"model_language.{language}"
    name = _i18n.t(key)
    return name if name != key else language.upper()


def gate_dictation_language(app: Any | None) -> bool:
    """True when the start may proceed, False when it was refused + surfaced."""
    from voice_typer.server.internal_plugin_hook import plugin_display_name

    if plugin_display_name(app):
        return True
    finding = unsupported_language(getattr(app, "config", None))
    if finding is None:
        return True
    refuse(app, finding)
    return False


def refuse(app: Any | None, finding: UnsupportedLanguage) -> None:
    """Surface the mismatch: in-app toast event + OS notification + tray + log."""
    message = _i18n.t(
        "notify.model_language.unsupported",
        model=finding.model_name,
        language=language_display_name(finding.language),
    )
    log.warning(
        "[DICTATION] Refusing start: %s does not support language=%s (auto would detect it)",
        finding.model_name,
        finding.language,
    )
    _publish_unsupported_event(finding)
    _notify_os(app, message)
    _set_tray_error(app, message)


def _publish_unsupported_event(finding: UnsupportedLanguage) -> None:
    """Push the in-app toast event (renderer localizes from the raw code)."""
    try:
        event_bus.publish(
            {
                "type": "model_language_unsupported",
                "data": {"model": finding.model_name, "language": finding.language},
            }
        )
    except Exception:
        log.debug("[DICTATION] language-mismatch event publish failed", exc_info=True)


def _notify_os(app: Any | None, message: str) -> None:
    """OS notification, clickable to the Models page; tray balloon fallback."""
    from voice_typer.server.permissions import refusal_notify

    if not refusal_notify.should_notify_refusal(APP_NAME, message):
        log.info("[DICTATION] repeat language mismatch: OS notification suppressed (dedup)")
        return
    try:
        if event_bus.has_live_transport() and event_bus.publish(
            {
                "type": "notification",
                "data": {
                    "title": APP_NAME,
                    "message": message,
                    "duration_ms": 0,
                    "critical": False,
                    "click_path": MODELS_PATH,
                },
            }
        ):
            return
    except Exception:
        log.debug("[DICTATION] language-mismatch OS notification failed", exc_info=True)
    try:
        tray = getattr(app, "tray", None)
        if tray is not None:
            tray.notify(APP_NAME, message)
    except Exception:
        log.debug("[DICTATION] language-mismatch tray balloon failed", exc_info=True)


def _set_tray_error(app: Any | None, message: str) -> None:
    """Tooltip mirror, auto-reverted so the tray does not stay stuck red."""
    from voice_typer.server.tray_types import AppState

    if app is None:
        return
    try:
        app.tray.set_state(AppState.ERROR, message)
    except Exception:
        log.debug("[DICTATION] language-mismatch tray state failed", exc_info=True)
        return
    try:
        app._schedule_timer(_TRAY_ERROR_REVERT_S, lambda: app.tray.set_state(AppState.IDLE))
    except Exception:
        log.debug("[DICTATION] language-mismatch tray revert failed", exc_info=True)


__all__ = [
    "MODELS_PATH",
    "UnsupportedLanguage",
    "gate_dictation_language",
    "language_display_name",
    "refuse",
    "unsupported_language",
]
