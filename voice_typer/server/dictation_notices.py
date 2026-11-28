"""Localized notices for refused dictation starts, with one publish path.

A user press that cannot start dictation must always say why and where to
look. Automatic retries share the model manager's episode dedupe; user
presses use a one-per-second floor so a held hotkey cannot flood the UI.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from voice_typer.server import event_bus
from voice_typer.server.branding import APP_NAME
from voice_typer.server.i18n import t

log = logging.getLogger(__name__)

NOTICE_INTERVAL_S = 1.0
USER_PRESS_WINDOW_S = 5.0
_LOCK = threading.Lock()

_LOCAL_NOTICE_KEYS = {
    "offline_pack_missing": "notify.model_manager.offline_pack_missing",
    "model_not_downloaded": "notify.model_manager.model_not_downloaded",
    "no_model_selected": "notify.model_manager.no_model_selected",
    "local_runtime_missing": "notify.dictation_provider.local_runtime_missing",
}
_LOCAL_STATE_KEYS = {
    "offline_pack_missing": "state.model_manager.offline_pack_missing",
    "model_not_downloaded": "state.model_manager.model_not_downloaded",
    "no_model_selected": "state.model_manager.no_model_selected",
    "local_runtime_missing": "state.model_manager.offline_pack_missing",
}


def mark_user_press(app: Any) -> None:
    """Remember the last accepted user start so async loaders can see it."""
    app._dictation_user_press_at = time.monotonic()


def user_press_recent(app: Any, *, window_s: float = USER_PRESS_WINDOW_S) -> bool:
    """True while a real user press is close enough to own a load refusal."""
    stamp = getattr(app, "_dictation_user_press_at", None)
    if not isinstance(stamp, (int, float)):
        return False
    return time.monotonic() - stamp < window_s


def user_notice_allowed(app: Any, key: str) -> bool:
    """One notice per key per second, even under a burst of user presses."""
    now = time.monotonic()
    stamps = getattr(app, "_dictation_notice_at", None)
    if stamps is None:
        stamps = {}
        app._dictation_notice_at = stamps
    with _LOCK:
        last = stamps.get(key)
        if last is not None and now - last < NOTICE_INTERVAL_S:
            return False
        stamps[key] = now
    return True


def publish_notice(
    app: Any,
    message: str,
    *,
    click_path: str | None = None,
) -> None:
    """Publish one in-app notice and the matching tray balloon."""
    data: dict[str, Any] = {
        "title": APP_NAME,
        "message": message,
        "duration_ms": 0,
        "critical": False,
    }
    if click_path:
        data["click_path"] = click_path
    try:
        event_bus.publish({"type": "notification", "data": data})
    except Exception:
        log.debug("[NOTICE] in-app notification failed", exc_info=True)
    try:
        app.tray.notify(APP_NAME, message)
    except Exception:
        log.debug("[NOTICE] tray notification failed", exc_info=True)


def publish_no_engine_notice(app: Any, *, caller: str = "HOTKEY") -> None:
    """ONE notice path for a user press with nothing able to transcribe."""
    message = t("notify.model_manager.no_model_selected")
    log.info("[%s] no active engine; dictation not started", caller)
    publish_notice(app, message)


def notify_plugin_unavailable(app: Any, label: str) -> None:
    """The selected plugin owns dictation but has no usable browser session."""
    if not user_notice_allowed(app, "plugin-unavailable"):
        return
    publish_notice(
        app,
        t("notify.dictation_provider.plugin_unavailable", name=label),
        click_path="/plugins",
    )


def notify_local_start_refused(app: Any, reason: str, *, backend: str = "") -> None:
    """Refuse a user start with the actionable local-model notice."""
    from voice_typer.server.tray_types import AppState

    if not user_notice_allowed(app, "start-refused:" + reason):
        return
    key = _LOCAL_NOTICE_KEYS.get(reason, _LOCAL_NOTICE_KEYS["model_not_downloaded"])
    state_key = _LOCAL_STATE_KEYS.get(reason, _LOCAL_STATE_KEYS["model_not_downloaded"])
    message = t(key, backend=backend or "")
    try:
        app.tray.set_state(AppState.ERROR, t(state_key, backend=backend or ""))
    except Exception:
        log.debug("[NOTICE] tray state for local refusal failed", exc_info=True)
    publish_notice(app, message, click_path="/models" if reason != "offline_pack_missing" else "/settings")


__all__ = [
    "mark_user_press",
    "notify_local_start_refused",
    "notify_plugin_unavailable",
    "publish_no_engine_notice",
    "publish_notice",
    "user_notice_allowed",
    "user_press_recent",
]
