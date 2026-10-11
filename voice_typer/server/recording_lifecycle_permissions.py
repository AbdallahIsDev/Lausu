"""Permission, consent, and failure-notification surface for recording.

Split out of ``voice_typer.server.recording_lifecycle`` (one concern per
file). The facade keeps the composed class, the constants and every
monkeypatch seam; this module owns the moved bodies and the notification
helpers. Facade-owned names (``i18n``, the consent constant, the bubble
timeout, the no-device marker) are read through the lazy ``_facade()``
proxy at call time so facade-level patches are honored.
"""

from __future__ import annotations

import contextlib
import logging

from voice_typer.server import event_bus
from voice_typer.server.branding import APP_NAME
from voice_typer.server.tray_types import AppState

log = logging.getLogger("voice_typer.server.recording_lifecycle")


def _facade():
    """The facade module, read at call time so patches on it are honored."""
    from voice_typer.server import recording_lifecycle as module

    return module


def _i18n_text(key: str) -> str:
    """Resolve the facade i18n seam as ``str`` for the ``-> str`` helpers."""
    text: str = _facade().i18n.t(key)
    return text


def _recording_start_failure_message(exc: BaseException) -> str:
    """Map a ``recorder.start()`` failure to a safe, user-friendly message."""
    from voice_typer.server.asr_errors import MicrophonePermissionDeniedError

    if isinstance(exc, MicrophonePermissionDeniedError):
        return _i18n_text("state.recording_controller.recording_failed_permission")
    if isinstance(exc, RuntimeError) and _facade()._NO_INPUT_DEVICE_MARKER in str(exc):
        return _i18n_text("state.recording_controller.recording_failed_no_device")
    return _i18n_text("state.recording_controller.recording_failed")


def _notify_consent_gate(title: str, message: str) -> bool:
    """Prefer a CLICKABLE host notification over the pystray balloon."""
    try:
        if not event_bus.has_live_transport():
            return False
        ok = event_bus.publish(
            {
                "type": "notification",
                "data": {
                    "title": title,
                    "message": message,
                    "duration_ms": 0,
                    "critical": False,
                    "click_consent_field": _facade().VOICE_BIOMETRIC_CONSENT_FIELD,
                },
            }
        )
        if ok:
            log.info("[DICTATION] published clickable consent notification (click -> Settings > Voice Biometric)")
            return True
    except Exception:
        log.debug("[DICTATION] clickable consent notification push failed", exc_info=True)
    return False


def _publish_consent_required_event() -> None:
    """Best-effort publish of a ``consent_required`` push event."""
    try:
        event_bus.publish(
            {
                "type": "consent_required",
                "data": {"consent_field": _facade().VOICE_BIOMETRIC_CONSENT_FIELD},
            }
        )
    except Exception:
        log.debug("[DICTATION] consent_required event push failed", exc_info=True)


def _open_os_microphone_settings() -> bool:
    """Open the OS microphone privacy page via the shared helper."""
    try:
        from voice_typer.server.handlers.status_handlers import open_os_microphone_settings as _open

        return bool(_open())
    except Exception:
        log.debug("[DICTATION] open OS mic settings failed", exc_info=True)
    return False


def _notify_permission_denied_with_settings(title: str, message: str) -> bool:
    """Clickable host notification; falls back to tray balloon.

    A duplicate of the same refusal within the dedup window returns
    True WITHOUT publishing, so callers skip their fallback too - the
    user already saw this notification once (refusal_notify).
    """
    from voice_typer.server.permissions import refusal_notify

    if not refusal_notify.should_notify_refusal(title, message):
        log.info("[DICTATION] repeat mic-refusal: OS notification suppressed (dedup)")
        return True
    try:
        if event_bus.has_live_transport():
            ok = event_bus.publish(
                {
                    "type": "notification",
                    "data": {
                        "title": title,
                        "message": message,
                        "duration_ms": 0,
                        "critical": True,
                        "click_path": "/microphone",
                    },
                }
            )
            if ok:
                return True
    except Exception:
        log.debug("[DICTATION] clickable permission notification push failed", exc_info=True)
    return False


class RecordingLifecyclePermissionsMixin:
    """Consent gate, permission refusals and start-failure surfacing."""

    def _gate_voice_biometric_consent(self, app) -> bool:
        """Enforce voice_biometric_consent before capturing any audio.

        Returns True when start may proceed, False when the caller must
        """
        try:
            if getattr(app.config, "voice_biometric_consent", False):
                return True
            log.warning(
                "[DICTATION] Refusing to start recording - voice_biometric_consent "
                "is False. User must enable it in Settings > Privacy."
            )
            try:
                app.tray.set_state(AppState.ERROR, _facade().i18n.t("state.recording_controller.consent_required"))
                # Prefer the CLICKABLE host toast (click → Settings
                if not _notify_consent_gate(
                    APP_NAME,
                    _facade().i18n.t("notify.recording_controller.consent_required"),
                ):
                    app.tray.notify_safety(
                        APP_NAME,
                        _facade().i18n.t("notify.recording_controller.consent_required"),
                    )
            except Exception:
                log.debug("[DICTATION] failed to notify about missing consent", exc_info=True)
            # Publish the ``consent_required`` push event so the
            _publish_consent_required_event()
            return False
        except Exception:
            # GDPR Art. 9: if we cannot verify voice_biometric_consent
            log.exception(
                "[DICTATION] Failed to check voice_biometric_consent - "
                "failing CLOSED (refusing to record) per GDPR Art. 9"
            )
            try:
                app.tray.set_state(
                    AppState.ERROR,
                    _facade().i18n.t("state.recording_controller.consent_required"),
                )
                if not _notify_consent_gate(
                    APP_NAME,
                    "Could not verify voice biometric consent.\nRecording refused. Check Settings > Privacy.",
                ):
                    app.tray.notify_safety(
                        APP_NAME,
                        _facade().i18n.t("notify.recording_controller.consent_not_verified"),
                    )
            except Exception:
                log.debug(
                    "[DICTATION] failed to notify about consent check exception",
                    exc_info=True,
                )
            # Same ``consent_required`` push as the plain-refusal branch
            _publish_consent_required_event()
            return False

    def _publish_permission_denied_refusal(self, app, state: str = "denied") -> None:
        """Terminal hotkey-press refusal: bubble + tray + notify + event."""
        try:
            if getattr(app.config, "bubble_behavior", "show_on_record") != "hidden":
                app._waveform_bubble.show()
                app._waveform_bubble.set_state("permission_revoked")
                self._schedule_permission_revoked_bubble_reset(app)
        except Exception:
            log.debug("[DICTATION] permission bubble surface failed", exc_info=True)
        try:
            app.tray.set_state(
                AppState.ERROR,
                _facade().i18n.t("state.recording_controller.recording_failed_permission"),
            )
        except Exception:
            log.debug("[DICTATION] permission tray surface failed", exc_info=True)
        _perm_msg = _facade().i18n.t("notify.recording_controller.mic_permission_revoked")
        if not _notify_permission_denied_with_settings(APP_NAME, _perm_msg):
            try:
                app.tray.notify_safety(APP_NAME, _perm_msg)
            except Exception:
                log.debug("[DICTATION] permission notify failed", exc_info=True)
        try:
            event_bus.publish({"type": "microphone_permission_revoked"})
        except Exception:
            log.debug("[DICTATION] permission event publish failed", exc_info=True)
        try:
            app._schedule_timer(3.0, lambda: app.tray.set_state(AppState.IDLE))
        except Exception:
            log.debug("[DICTATION] permission idle timer failed", exc_info=True)

    def _schedule_permission_revoked_bubble_reset(self, app) -> None:
        """Auto-revert the permission_revoked bubble variant after a beat.

        always_visible returns to the idle variant; show_on_record hides.
        Guarded by the bubble's current state so a recording that started
        inside the window is never clobbered by the stale reset.
        """

        def _reset() -> None:
            try:
                if getattr(app._waveform_bubble, "state", None) != "permission_revoked":
                    return
                if getattr(app.config, "bubble_behavior", "show_on_record") == "always_visible":
                    app._waveform_bubble.set_state("idle")
                else:
                    app._waveform_bubble.hide()
            except Exception:
                log.debug("[DICTATION] permission bubble auto-reset failed", exc_info=True)

        try:
            app._schedule_timer(_facade()._PERMISSION_REVOKED_BUBBLE_SECONDS, _reset)
        except Exception:
            log.debug("[DICTATION] permission bubble reset timer failed", exc_info=True)

    def _publish_start_failure_notification(self, app, exc: BaseException) -> None:
        """Surface a start failure in tray / toast / push / idle-timer."""
        from voice_typer.server.asr_errors import MicrophonePermissionDeniedError

        if isinstance(exc, MicrophonePermissionDeniedError):
            self._publish_permission_denied_refusal(app, getattr(exc, "state", None) or "denied")
            return
        _start_fail_msg = _recording_start_failure_message(exc)
        app.tray.set_state(AppState.ERROR, _start_fail_msg)
        # Notification mirrors the tooltip: for typed failures the
        if _start_fail_msg != _facade().i18n.t("state.recording_controller.recording_failed"):
            app.tray.notify(
                APP_NAME,
                _facade().i18n.t("notify.recording_controller.start_failed_with_reason", reason=_start_fail_msg),
            )
        else:
            app.tray.notify(
                APP_NAME,
                _facade().i18n.t("notify.recording_controller.start_failed"),
            )
        with contextlib.suppress(Exception):
            event_bus.publish(
                {"type": "error", "data": {"message": "Could not start recording", "kind": "recording_start"}}
            )
        app._schedule_timer(3.0, lambda: app.tray.set_state(AppState.IDLE))
