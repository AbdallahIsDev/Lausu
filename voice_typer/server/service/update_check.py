"""Auto-update check against GitHub Releases (user-initiated/silent check)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, TypedDict
from urllib.parse import urlparse

from voice_typer.server.service import offline_pack
from voice_typer.server.service.offline_pack import (
    OfflinePackManifest,
    require_offline_pack_consent,
)
from voice_typer.server.service.update_check_http import (  # noqa: F401  # facade re-export
    LAUNCH_MANIFEST_TIMEOUT_S,
    _http_get_manifest,
    _is_missing_manifest_404,
    _SSRFAwareRedirectHandler,
    fetch_remote_manifest,
    fetch_remote_manifest_first_success,
)
from voice_typer.server.service.update_check_urls import (  # noqa: F401  # facade re-export
    DEFAULT_OFFLINE_PACK_MANIFEST_URL,
    MAX_MANIFEST_BYTES,
    ROLLING_OFFLINE_PACK_MANIFEST_URL,
    _resolve_manifest_url,
    pack_manifest_url_candidates,
)
from voice_typer.server.service.update_check_versions import (  # noqa: F401  # facade re-export
    _parse_version,
    is_newer_version,
)

if TYPE_CHECKING:
    from voice_typer.server.config import Config

log = logging.getLogger(__name__)


class UpdateCheckResult(TypedDict, total=False):
    """Outcome of a pack-version check."""

    success: bool
    checked_at: int
    local_version: str | None
    remote_version: str | None
    update_available: bool
    download_triggered: bool
    consent_required: bool
    error: str
    reason: str



def _local_offline_pack_version(root: Path | None = None) -> str | None:
    """Return the locally-installed pack version, or ``None`` if none."""
    base = offline_pack._default_offline_pack_root() if root is None else root
    if not base.exists():
        return None
    best: str | None = None
    try:
        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            if entry.name.endswith(".new") or entry.name.endswith(".trash"):
                # Staging dirs left by a crashed install and trash dirs
                continue
            version = entry.name
            try:
                if offline_pack.offline_pack_exists(version, root=root) and (
                    best is None or is_newer_version(version, best)
                ):
                    best = version
            except Exception:  # defensive: a single corrupt dir must not abort the scan
                log.debug("[UPDATE] offline_pack_exists check failed for %s", version, exc_info=True)
    except OSError:
        log.debug("[UPDATE] pack root scan failed", exc_info=True)
        return None
    return best


# Per-version in-flight download guard (§8.13 / §8.16).
_ACTIVE_PACK_DOWNLOADS: set[str] = set()
_ACTIVE_PACK_DOWNLOADS_LOCK = threading.Lock()


def _trigger_background_download(
    *,
    manifest: OfflinePackManifest,
    manifest_url: str,
    config: Config | None,
    event_bus: ModuleType | None,
    root: Path | None,
    http_get: Callable[..., Any] | None,
) -> bool:
    """Trigger a background download of the pack via :mod:`pack`."""
    version = manifest["version"]

    # Always-on product decision: gate is a no-op; kept for call-site uniformity.
    require_offline_pack_consent(config, version=version)

    # Dedupe: if a download for this version is already in flight (started
    with _ACTIVE_PACK_DOWNLOADS_LOCK:
        if version in _ACTIVE_PACK_DOWNLOADS:
            log.info(
                "[UPDATE] pack %s download already in flight, skipping duplicate trigger",
                version,
            )
            return False
        _ACTIVE_PACK_DOWNLOADS.add(version)

    # Everything that can still fail AFTER registration (mkdir on a full
    try:
        # Construct the pack-download URL. The manifest lives at
        parsed = urlparse(manifest_url)
        # Strip ``pack-manifest.json`` from the path; append the pack asset name.
        path = parsed.path
        # ``path`` looks like ``/owner/repo/releases/latest/download/pack-manifest.json``
        dir_path = path.rsplit("/", 1)[0] if "/" in path else ""
        pack_asset_name = f"pack-{manifest['version']}.zip"
        pack_url = f"{parsed.scheme}://{parsed.netloc}{dir_path}/{pack_asset_name}"

        dest = offline_pack.offline_pack_partial_path(manifest["version"], root=root)
        # Ensure the version directory exists (``download_offline_pack_with_resume``
        dest.parent.mkdir(parents=True, exist_ok=True)

        def _bg() -> None:
            try:
                # §8.8 disk gate: refuse to even START a ~200 MB download
                offline_pack.check_offline_pack_disk_space(dest.parent)
                # §8.13 cross-process lock: serialize the partial-file
                with offline_pack.OfflinePackLock(version, root=root):
                    # Post-lock installed re-check: the version
                    if offline_pack.offline_pack_exists(version, root=root):
                        log.info(
                            "[UPDATE] pack %s already installed (post-lock re-check), skipping the redundant download",
                            version,
                        )
                        return
                    downloaded = offline_pack.download_offline_pack_with_resume(
                        pack_url,
                        dest,
                        expected_sha256=manifest["sha256"],
                        version=version,
                        event_bus=event_bus,
                        http_get=http_get,
                    )
                    if downloaded:
                        # Install stage: extract the verified archive
                        offline_pack.install_offline_pack(
                            dest,
                            version,
                            manifest,
                            root=root,
                            event_bus=event_bus,
                        )
            except Exception:  # background thread must not propagate
                log.exception(
                    "[UPDATE] background pack download failed for %s",
                    version,
                )
            finally:
                # Release the in-flight guard so a LATER trigger (or the next
                with _ACTIVE_PACK_DOWNLOADS_LOCK:
                    _ACTIVE_PACK_DOWNLOADS.discard(version)

        thread = threading.Thread(
            target=_bg,
            name=f"pack-update-download-{manifest['version']}",
            daemon=True,
        )
        thread.start()
    except BaseException:
        # Late failure AFTER registration (mkdir, thread spawn) —
        with _ACTIVE_PACK_DOWNLOADS_LOCK:
            _ACTIVE_PACK_DOWNLOADS.discard(version)
        raise
    log.info(
        "[UPDATE] background download started for pack %s from %s",
        manifest["version"],
        pack_url,
    )
    return True


def check_offline_pack_update(
    config: Config | None,
    event_bus: ModuleType | None,
    *,
    http_get: Callable[..., Any] | None = None,
    manifest_url: str | None = None,
    local_version: str | None = None,
    root: Path | None = None,
    trigger_download: bool = True,
    manifest_timeout: float = 30.0,
) -> UpdateCheckResult:
    """Check whether a newer pack version is available; optionally trigger download.

    Pack auto-update is always-on: consent never blocks the manifest
    fetch or the background download (user product decision).

    Steps:
      1. Resolve candidate manifest URLs (param > ``VT_PACK_MANIFEST_URL`` env >
         :func:`pack_manifest_url_candidates`).
      2. Resolve the local pack version (param > scan the pack root).
      3. Fetch + validate via :func:`fetch_remote_manifest_first_success`
         (SSRF-gated, max-bytes-capped, ``manifest_timeout``-bounded).
      4. Compare versions via :func:`is_newer_version`.
      5. If a newer version is available AND ``trigger_download=True``,
         call :func:`_trigger_background_download`.

    Returns an :data:`UpdateCheckResult`. Never raises, all errors are
    caught and returned as ``{"success": False, "error": ..., "reason": ...}``.
    """
    import time

    candidates = pack_manifest_url_candidates(manifest_url)
    url = candidates[0]

    # Default local_version to a scan of the pack root.
    if local_version is None:
        try:
            local_version = _local_offline_pack_version(root=root)
        except Exception:  # defensive: pack-root scan must not abort the check
            log.exception("[UPDATE] local pack scan failed")
            local_version = None

    try:
        remote_manifest, fetched_url = fetch_remote_manifest_first_success(
            candidates, http_get=http_get, timeout=manifest_timeout
        )
    except Exception:  # fetch is supposed to return None on failure, but catch defensively
        log.exception("[UPDATE] unexpected error fetching remote manifest")
        remote_manifest, fetched_url = None, None

    if remote_manifest is None or not fetched_url:
        return {
            "success": False,
            "checked_at": int(time.time() * 1000),
            "local_version": local_version,
            "remote_version": None,
            "update_available": False,
            "download_triggered": False,
            "error": "failed to fetch remote manifest",
            "reason": "fetch_failed",
        }
    url = fetched_url

    remote_version = remote_manifest["version"]
    update_available = local_version is None or is_newer_version(remote_version, local_version)

    result: UpdateCheckResult = {
        "success": True,
        "checked_at": int(time.time() * 1000),
        "local_version": local_version,
        "remote_version": remote_version,
        "update_available": update_available,
        "download_triggered": False,
    }

    if not update_available:
        log.info(
            "[UPDATE] pack is up-to-date (local=%s, remote=%s)",
            local_version,
            remote_version,
        )
        return result

    log.info(
        "[UPDATE] pack update available (local=%s, remote=%s)",
        local_version,
        remote_version,
    )

    if not trigger_download:
        return result

    try:
        download_started = _trigger_background_download(
            manifest=remote_manifest,
            manifest_url=url,
            config=config,
            event_bus=event_bus,
            root=root,
            http_get=http_get,
        )
        result["download_triggered"] = download_started
    except Exception as exc:  # defensive: the download trigger must not abort the check
        log.exception("[UPDATE] failed to trigger background download")
        result["success"] = False
        result["error"] = f"failed to trigger download: {exc}"
        result["reason"] = "download_trigger_failed"

    return result


def handle_check_offline_pack_update_ipc(
    app: Any,
    data: dict | None,
    *,
    http_get: Callable[..., Any] | None = None,
    manifest_url: str | None = None,
    local_version: str | None = None,
    root: Path | None = None,
    trigger_download: bool = True,
) -> dict[str, Any]:
    """Thin IPC handler wrapper around :func:`check_offline_pack_update`.

    Returns a plain ``dict`` (not a TypedDict) for IPC serialization —
    """
    config = getattr(app, "config", None) if app is not None else None
    # Typed resolution: the app may expose ``event_bus`` as an
    event_bus: ModuleType | None = getattr(app, "event_bus", None) if app is not None else None
    if event_bus is None and app is not None:
        # Fall back to the module-level event_bus (some service objects
        try:
            from voice_typer.server import event_bus as _event_bus_module

            event_bus = _event_bus_module
        except ImportError:
            pass
    result = check_offline_pack_update(
        config,
        event_bus,
        http_get=http_get,
        manifest_url=manifest_url,
        local_version=local_version,
        root=root,
        trigger_download=trigger_download,
    )
    return dict(result)


__all__ = [
    "DEFAULT_OFFLINE_PACK_MANIFEST_URL",
    "ROLLING_OFFLINE_PACK_MANIFEST_URL",
    "pack_manifest_url_candidates",
    "fetch_remote_manifest_first_success",
    "MAX_MANIFEST_BYTES",
    "UpdateCheckResult",
    "check_offline_pack_update",
    "fetch_remote_manifest",
    "handle_check_offline_pack_update_ipc",
    "is_newer_version",
]
