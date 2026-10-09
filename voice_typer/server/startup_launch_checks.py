"""Launch-time startup checks (offline pack, media extractor, shortcut, probes).

Split out of ``voice_typer.server.startup_tasks`` (one concern per file);
the facade re-exports every name so existing ``startup_tasks.X`` call
sites and monkeypatch seams keep resolving.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from voice_typer.server.platform_utils import is_windows
from voice_typer.server.providers import AppProtocol
from voice_typer.server.server_platform import create_launcher_shortcut

# Logger name stays the facade module's so log routing is unchanged.
log = logging.getLogger("voice_typer.server.startup_tasks")


def check_offline_pack_on_launch(app: AppProtocol, shutdown_event: threading.Event | None = None) -> dict:
    """Launch-time pack check: integrity + always-on remote update check.

    Runs on a fire-and-forget daemon thread at startup (see
    ``StartupSequence._startup_parallel_work``). Never blocks the window:

    1. Cheap local existence scan (no SHA-256).
    2. Pack present → background checksum AND remote update check
       (``check_offline_pack_update`` with ``trigger_download=True``).
    3. Pack missing → ``offline_pack_missing`` event + remote update
       check (silent re-download). Always-on: no consent gate.
    4. ``installer-state.json`` can suppress the download: full-offline
       installs set ``pack_bundled`` (pack already on disk) and the
       Components-page checkbox can set ``include_offline_engine_pack``
       false (user opted out of the silent download).

    Remote fetch uses ``LAUNCH_MANIFEST_TIMEOUT_S`` so a stalled logon
    network cannot pin the thread. Best-effort: never raises.
    """
    try:
        from voice_typer.server import event_bus as _event_bus_module
        from voice_typer.server.service import offline_pack, update_check

        config = getattr(app, "config", None)
        event_bus = _event_bus_module

        local_version: str | None = None
        try:
            local_version = update_check._local_offline_pack_version()
        except Exception:  # noqa: BLE001
            log.debug("[PACK] launch-time local pack scan failed", exc_info=True)

        if shutdown_event is not None and shutdown_event.is_set():
            return {"checked": False, "reason": "shutdown"}

        checksum: str | None = None
        missing_event = False
        if local_version is not None:
            try:
                background = offline_pack.BackgroundChecksum(local_version, event_bus=event_bus)
                background.start()
                checksum = "background"
            except Exception:  # noqa: BLE001
                log.exception("[PACK] background checksum spawn failed for %s", local_version)
            log.info(
                "[PACK] offline pack %s present at launch, background checksum started",
                local_version,
            )
        else:
            missing_event = True
            try:
                offline_pack._publish_event(
                    event_bus,
                    "offline_pack_missing",
                    {
                        "version": None,
                        "path": str(offline_pack._default_offline_pack_root()),
                    },
                )
            except Exception:  # noqa: BLE001
                log.debug("[PACK] offline_pack_missing publish failed", exc_info=True)
            log.info("[PACK] offline pack missing at launch, always-on re-download check")

        if shutdown_event is not None and shutdown_event.is_set():
            return {
                "checked": False,
                "reason": "shutdown",
                "installed_version": local_version,
            }

        from voice_typer.server.installer_state import load_installer_state, pack_download_allowed

        installer = load_installer_state()
        allow_download = pack_download_allowed(installer, pack_present=local_version is not None)
        if not allow_download:
            if installer.pack_bundled and local_version is not None:
                reason = "pack_bundled"
            elif not installer.include_offline_engine_pack:
                reason = "user_opted_out"
            else:
                reason = "download_not_needed"
            log.info(
                "[PACK] skipping remote pack download (%s); include=%s bundled=%s present=%s",
                reason,
                installer.include_offline_engine_pack,
                installer.pack_bundled,
                local_version is not None,
            )
            return {
                "checked": True,
                "reason": reason,
                "installed_version": local_version,
                "missing_event": missing_event,
            }

        # Always-on: remote check on every launch (present or missing).
        update_result: dict | None = None
        try:
            result = update_check.check_offline_pack_update(
                config,
                event_bus,
                trigger_download=True,
                manifest_timeout=update_check.LAUNCH_MANIFEST_TIMEOUT_S,
            )
            update_result = dict(result)
        except Exception:  # noqa: BLE001
            log.exception("[PACK] launch-time pack update check failed (best-effort)")

        return {
            "checked": True,
            "installed_version": local_version,
            "checksum": checksum,
            "missing_event": missing_event,
            "update_check": update_result,
        }
    except Exception:  # noqa: BLE001
        log.exception("[PACK] launch-time pack check failed (best-effort)")
        return {"checked": False, "reason": "error"}

def check_media_extractor_refresh(app: AppProtocol, shutdown_event: threading.Event | None = None) -> dict:
    """Launch-time CHECK-ONLY freshness probe for the media extractor (ADR-0023).

    Compares the installed yt-dlp / solver versions against the published
    ``media-extractor.json`` manifest and persists the result. It NEVER
    downloads or installs anything: the offline pack stays the heavy
    software boundary and the user-initiated update path owns installs.
    Runs fire-and-forget on a daemon thread; best-effort, never raises.
    """
    _ = app  # state is advisory metadata, nothing on the app is mutated
    try:
        if shutdown_event is not None and shutdown_event.is_set():
            return {"checked": False, "reason": "shutdown"}
        from voice_typer.server.media_ingest import mini_update as _mini_update

        state = _mini_update.check_refresh()
        if state.update_available:
            log.info(
                "[MEDIA] extractor refresh available: yt-dlp %s -> %s, solver %s -> %s (check-only; user-installed)",
                state.backend_version,
                state.remote_backend_version,
                state.solver_version,
                state.remote_solver_version,
            )
        else:
            log.info(
                "[MEDIA] extractor freshness check complete (yt-dlp=%s solver=%s, no update)",
                state.backend_version,
                state.solver_version,
            )
        return {
            "checked": True,
            "update_available": state.update_available,
            "checked_at": state.checked_at,
        }
    except Exception:  # noqa: BLE001
        log.debug("[MEDIA] launch-time extractor refresh check failed (best-effort)", exc_info=True)
        return {"checked": False, "reason": "error"}

def ensure_desktop_shortcut(app: AppProtocol) -> None:
    """Create the Desktop + Start Menu shortcuts on first run."""
    if not is_windows():
        return
    desktop = Path.home() / "Desktop"
    legacy_bat = desktop / "Lausu.bat"

    # 1. Migrate: remove the legacy backend-only .bat so the broken
    try:
        if legacy_bat.exists() and "-m voice_typer" in legacy_bat.read_text(encoding="utf-8", errors="replace"):
            legacy_bat.unlink()
            log.info("[STARTUP] Removed legacy backend-only shortcut: %s", legacy_bat)
    except OSError:
        pass

    # 2. Ensure the universal-launcher shortcut exists.
    try:
        create_launcher_shortcut()
    except Exception as e:
        log.debug("[STARTUP] Desktop shortcut creation skipped: %s", e)

def prewarm_connect_probes() -> None:
    """Warm the get_config probe caches before the renderer connects.

    Connect-time ``get_config`` runs the keyring + GPU probes inline;
    their first-call cost (keyring backend init, DLL scan, ctranslate2
    import) can stall a readonly-pool worker mid-startup-storm. Both
    probes cache per process, so one fire-and-forget pass here makes
    every later handshake answer from cache. Never raises.
    """
    try:
        from voice_typer.server import device_caps

        device_caps.gpu_available()
    except Exception:
        log.debug("[STARTUP] GPU probe pre-warm failed", exc_info=True)
    try:
        from voice_typer.server.credential_store import get_keyring_status

        get_keyring_status()
    except Exception:
        log.debug("[STARTUP] keyring probe pre-warm failed", exc_info=True)
