"""Background startup tasks after app construction (non-blocking)."""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import Any

from voice_typer.server import i18n
from voice_typer.server.branding import APP_NAME
from voice_typer.server.providers import AppProtocol
from voice_typer.server.server_platform.macos_bundle_id import resolve_host_bundle_id

log = logging.getLogger(__name__)


# cache the macOS ApplicationServices framework handle at
_APP_SERVICES_LIB: Any | None = None
_APP_SERVICES_LIB_LOADED: bool = False


def _a11y_regrant_message(bundle_id: str | None) -> str:
    """Build the macOS Accessibility re-grant notification body."""
    # The command string comes from the single construction
    from voice_typer.server.server_platform.macos_bundle_id import tccutil_reset_command_str

    if bundle_id:
        return (
            f"{APP_NAME} was updated. Accessibility permission may "
            f"need to be re-granted. Run: {tccutil_reset_command_str('Accessibility', bundle_id)}"
        )
    return (
        f"{APP_NAME} was updated. Accessibility permission may "
        "need to be re-granted. Open System Settings "
        "-> Privacy & Security -> Accessibility to re-grant."
    )




def sync_prewarm_task(app: AppProtocol, shutdown_event: threading.Event | None = None) -> dict:
    """No-op stub retained for caller compatibility."""
    _ = app  # unused, kept for signature backward-compat
    _ = shutdown_event  # unused, kept for signature backward-compat
    return {"registered": False, "error": None}










def _reconcile_configured_microphone(app: AppProtocol, mics: list[dict]) -> None:
    """Validate ``app.config.microphone`` against the live device list."""
    from voice_typer.server.server_platform.microphone_list import find_microphone_by_id

    try:
        mic_id = app.config.microphone
    except AttributeError:
        return
    # Only str/None are meaningful persisted values. Anything else is an
    if mic_id is not None and not isinstance(mic_id, str):
        return
    if mic_id is None:
        log.debug("[MIC] Startup microphone check: System Default (no persisted selection)")
        return
    if not mics:
        # An EMPTY enumeration is NOT evidence that the configured device
        log.debug("[MIC] Skipping microphone reconciliation: no devices enumerated")
        return

    resolved: dict | None = None
    try:
        resolved = find_microphone_by_id(mic_id)
    except Exception:
        log.debug("[MIC] Microphone resolution failed for %r", mic_id, exc_info=True)

    if resolved is not None:
        canonical = str(resolved.get("id", ""))
        if canonical and canonical != mic_id:
            # Legacy id shape (bare index / compound form) resolved to a
            lock = getattr(app, "_config_mutation_lock", None)
            with contextlib.ExitStack() as stack:
                if lock is not None:
                    stack.enter_context(lock)
                app.config.microphone = canonical
                saved = app.config.save()
            if saved:
                log.info(
                    "[MIC] Migrated legacy microphone id %r -> stable id %r (%s)",
                    mic_id,
                    canonical,
                    resolved.get("name", "?"),
                )
                _publish_mic_reconciled(app, {"microphone": canonical})
            else:
                log.warning(
                    "[MIC] Failed to persist legacy-id migration %r -> %r",
                    mic_id,
                    canonical,
                )
        else:
            log.info(
                "[MIC] Startup microphone check: configured device available: %s (%s)",
                resolved.get("name", "?"),
                mic_id,
            )
        return

    # Stale selection → SILENT user-facing recovery + diagnostic log.
    lock = getattr(app, "_config_mutation_lock", None)
    with contextlib.ExitStack() as stack:
        if lock is not None:
            stack.enter_context(lock)
        app.config.microphone = None
        saved = app.config.save()
    if saved:
        log.warning(
            "[MIC] Configured microphone %r is not available on this machine "
            "(%d input devices found), recovered to System Default and "
            "persisted null.",
            mic_id,
            len(mics),
        )
        _publish_mic_reconciled(app, {"microphone": None})
    else:
        log.error(
            "[MIC] Configured microphone %r is unavailable and persisting the "
            "System Default fallback FAILED, stale id left on disk; will "
            "retry at next startup.",
            mic_id,
        )




def reconcile_configured_device(app: AppProtocol) -> bool:
    """Force ``config.device`` to CPU when no CUDA GPU is present.

    Self-healing guard: a persisted GPU value on a CPU-only machine
    (fresh-install default, stale config, hand-edited ``config.json``)
    would fail every transcription at runtime. The probe is cached
    and sub-second; the overwrite is persisted so the next launch
    starts clean, and a ``config_changed`` push moves the sidebar
    toggle without a reconnect. Returns True when a change persisted.
    """
    try:
        from voice_typer.server import device_caps
    except ImportError:
        log.debug("[DEVICE] device_caps unavailable, skipping reconcile", exc_info=True)
        return False
    if device_caps.gpu_available():
        return False
    try:
        current = app.config.device
    except AttributeError:
        return False
    if not isinstance(current, str):
        return False
    if current.lower() == "cpu":
        return False
    lock = getattr(app, "_config_mutation_lock", None)
    with contextlib.ExitStack() as stack:
        if lock is not None:
            stack.enter_context(lock)
        app.config.device = "cpu"
        try:
            saved = app.config.save()
        except Exception:
            saved = False
    if not saved:
        log.error("[DEVICE] No GPU detected but persisting the CPU fallback FAILED")
        return False
    log.warning("[DEVICE] No GPU detected, device %r overwritten to CPU and persisted", current)
    _publish_mic_reconciled(app, {"device": "cpu"})
    return True


def _publish_mic_reconciled(app: AppProtocol, updates: dict) -> None:
    """Push a ``config_changed`` event after startup reconciliation."""
    try:
        from voice_typer.server import event_bus

        event_bus.publish({"type": "config_changed", "data": updates})
    except Exception:
        log.debug("[MIC] config_changed publish failed", exc_info=True)


def load_microphones(app: AppProtocol, shutdown_event: threading.Event | None = None) -> None:
    """Enumerate microphones and update the tray menu.

    RACE-020: accepts an optional shutdown_event so the task can
    abort early if the app is quitting during startup.

    AUDIO-MIC: detects device changes by comparing the new list against
    the cached one. When the set of device IDs changes (USB mic
    plugged/unplugged), pushes a ``microphones_changed`` IPC event so
    the predecessor renderer can refresh its microphone dropdown without
    a manual "Refresh" click. The comparison is done via ``old_ids``
    and ``new_ids`` sets.
    """
    # Import list_microphones at call time so tests that monkeypatch
    from voice_typer.server.server_platform.microphone_list import list_microphones

    # Accessors for the app's off-protocol ``_microphones`` attribute
    from voice_typer.server.service._app_internals import app_microphones, set_app_microphones

    # RACE-020: abort early if shutting down
    if shutdown_event is not None and shutdown_event.is_set():
        return
    try:
        mics = list_microphones()
        # Startup reconciliation: validate the PERSISTED selection against
        try:
            _reconcile_configured_microphone(app, mics)
        except Exception:
            # Belt-and-braces: a reconciler bug must never downgrade the
            log.warning("[MIC] Microphone reconciliation failed", exc_info=True)
        # AUDIO-MIC: detect device changes by comparing the new
        app_mics = app_microphones(app)
        old_ids = {m["id"] for m in app_mics} if app_mics else set()
        new_ids = {m["id"] for m in mics}
        set_app_microphones(app, mics)
        app.tray.set_microphones(mics)
        # Log INFO on first load or when device count changes.
        if not old_ids:
            log.info("[RECORDING] Found %d microphones", len(mics))
        elif len(mics) != len(old_ids):
            log.info("[RECORDING] Microphone count changed: %d -> %d", len(old_ids), len(mics))
        # AUDIO-MIC: push a device-change IPC event if the device
        if (old_ids and old_ids != new_ids) or (not old_ids and new_ids):
            added = new_ids - old_ids
            removed = old_ids - new_ids
            log.info(
                "[AUDIO-MIC] Device set changed: +%d added, -%d removed",
                len(added),
                len(removed),
            )
            try:
                from voice_typer.server import event_bus

                event_bus.publish(
                    {
                        "type": "microphones_changed",
                        "data": {"count": len(mics)},
                    }
                )
            except Exception:
                # Best-effort: a failed notification publish must never break
                log.debug("[AUDIO-MIC] microphones_changed publish failed", exc_info=True)
    except Exception as e:
        log.warning("[RECORDING] Could not enumerate microphones: %s", e)


def start_accessibility_pulse(app: AppProtocol, initial_state: bool) -> None:
    """Periodically re-check macOS Accessibility permission."""

    def _check_accessibility() -> bool:
        """Return True if Accessibility permission is granted."""
        global _APP_SERVICES_LIB, _APP_SERVICES_LIB_LOADED
        if not _APP_SERVICES_LIB_LOADED:
            try:
                import ctypes

                _APP_SERVICES_LIB = ctypes.cdll.LoadLibrary(
                    "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
                )
            except Exception:
                _APP_SERVICES_LIB = None
            finally:
                _APP_SERVICES_LIB_LOADED = True
        if _APP_SERVICES_LIB is None:
            return False  # fail safe (assume not granted)
        try:
            return bool(_APP_SERVICES_LIB.AXIsProcessTrusted())
        except Exception:
            return False  # fail safe (assume not granted)

    def _pulse_loop(stop_event: threading.Event) -> None:
        # PERF-25: the loop now also watches ``stop_event``
        # 60-iteration 1s loop (PERF-25) was added so shutdown signals
        # the  finding). The defensive ``app._shutting_down`` check
        last_state = initial_state
        while not app._shutting_down:
            # single 60s wait, ``stop_event.set()`` from
            if stop_event.wait(timeout=60.0):
                return
            if app._shutting_down or stop_event.is_set():
                return
            current = _check_accessibility()
            if current != last_state:
                if current:
                    log.info("[A11Y] macOS Accessibility permission granted")
                    # persist the app version at which a11y was
                    try:
                        import voice_typer as _vt

                        _current_vt_version = getattr(_vt, "__version__", None)
                        if _current_vt_version is not None:
                            app.config.last_known_a11y_version = _current_vt_version
                    except Exception:
                        log.debug("[A11Y] could not persist last_known_a11y_version", exc_info=True)
                    with contextlib.suppress(Exception):
                        app.tray.notify(APP_NAME, i18n.t("notify.permissions.accessibility_granted"))
                else:
                    log.warning("[A11Y] macOS Accessibility permission revoked")
                    # detect version-change-induced TCC reset
                    _version_changed = False
                    try:
                        import voice_typer as _vt

                        _current_vt_version = getattr(_vt, "__version__", None)
                        _last_known_version = getattr(app.config, "last_known_a11y_version", None)
                        _version_changed = (
                            _current_vt_version is not None
                            and _last_known_version is not None
                            and _current_vt_version != _last_known_version
                        )
                        if _version_changed:
                            log.warning(
                                "[A11Y] a11y denied after app version change (%s -> %s), likely TCC reset on update",
                                _last_known_version,
                                _current_vt_version,
                            )
                    except Exception:
                        log.debug("[A11Y] could not compare a11y version", exc_info=True)
                    with contextlib.suppress(Exception):
                        if _version_changed:
                            # Resolve the HOST app's bundle ID at runtime:
                            app.tray.notify_safety(
                                f"{APP_NAME}, Accessibility Re-grant",
                                _a11y_regrant_message(resolve_host_bundle_id()),
                            )
                        else:
                            app.tray.notify_safety(
                                f"{APP_NAME}, Accessibility Revoked",
                                i18n.t("notify.permissions.global_hotkeys_disabled"),
                            )
                last_state = current

    # PERF-25: dedicated stop_event so ``app._thread_registry`` can
    stop_event = threading.Event()
    t = threading.Thread(target=_pulse_loop, args=(stop_event,), daemon=True, name="A11yPulse")
    # RACE-008: daemon=True is acceptable, the pulse only reads
    t.start()
    # PERF-25: register with the central ThreadRegistry so
    registry = getattr(app, "_thread_registry", None)
    if registry is not None:
        try:
            registry.register(
                name="A11yPulse",
                thread=t,
                stop_event=stop_event,
                join_timeout=2.0,
            )
        except Exception:
            log.debug("[STARTUP] could not register A11yPulse with ThreadRegistry", exc_info=True)


# Re-exports for the create-first split (bodies live in the sibling
# modules; every historical ``startup_tasks.X`` call site and
# monkeypatch seam keeps resolving through this facade).
from voice_typer.server.startup_config_sync import (  # noqa: E402,F401  # facade re-export
    reconcile_configured_model,
    reset_onboarding_complete,
    sync_autostart,
)
from voice_typer.server.startup_launch_checks import (  # noqa: E402,F401  # facade re-export
    check_media_extractor_refresh,
    check_offline_pack_on_launch,
    ensure_desktop_shortcut,
    prewarm_connect_probes,
)


