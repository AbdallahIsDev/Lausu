"""Service status/metrics mixin."""

import logging
import time
from typing import TYPE_CHECKING

from voice_typer.server._audio_constants import WHISPER_SAMPLE_RATE
from voice_typer.server._secrets import redact_secret, redact_url
from voice_typer.server.service._base import ServiceMixinBase

if TYPE_CHECKING:
    # ``StatusResponse`` is a TypedDict defined in
    from voice_typer.server.service import StatusResponse

log = logging.getLogger(__name__)


class StatusMixin(ServiceMixinBase):
    """Status / health-check service methods."""

    # notify-once guard for volume_ducker.initialize failures.
    _volume_ducker_init_warned: bool = False

    # Per-instance cache for :meth:`get_volume_backend_status`.
    _volume_backend_status_cache: dict[str, object] | None = None

    # TTL for the volume-backend status cache (fixes the
    _VOLUME_BACKEND_STATUS_TTL_S = 30.0
    _volume_backend_status_cached_at: float = 0.0

    # Offline-pack state cache for :meth:`_get_offline_pack_status`.
    _OFFLINE_PACK_STATUS_TTL_S = 15.0
    _pack_status_cache: dict[str, object] | None = None
    _pack_status_cached_at: float = 0.0

    def _read_pack_outdated_info(self) -> dict[str, object] | None:
        """Latest PK-1 stale-pack signal copy, None when clear. Never raises."""
        try:
            from voice_typer.server.service.offline_pack.outdated import get_outdated_info

            info = get_outdated_info()
        except Exception:
            log.debug("[SERVICE] offline pack outdated info unavailable", exc_info=True)
            return None
        if not isinstance(info, dict) or not info:
            return None
        return dict(info)

    @staticmethod
    def _derive_pack_state(
        installed_version: object,
        download_progress: object,
        outdated_info: object,
    ) -> str:
        """Stable PK-2 machine: outdated > downloading > verifying > ready > missing."""
        try:
            if isinstance(outdated_info, dict) and len(outdated_info) > 0:
                return "outdated"
            if type(download_progress) is int:
                if 0 <= download_progress <= 99:
                    return "downloading"
                if download_progress == 100:
                    return "verifying"
            if isinstance(installed_version, str) and installed_version:
                try:
                    from voice_typer.server.service.offline_pack.core import offline_pack_exists

                    if offline_pack_exists(installed_version):
                        return "ready"
                except Exception:
                    log.debug("[SERVICE] offline pack existence check failed", exc_info=True)
                    # The version scan already proved presence; a transient
                    # confirm failure must not claim the pack is missing.
                    return "ready"
            return "missing"
        except Exception:
            log.debug("[SERVICE] offline pack state derive failed", exc_info=True)
            return "missing"

    def invalidate_pack_status_cache(self) -> None:
        """Drop the cached version scan so the next read re-scans.

        The TTL gates the filesystem scan only; progress + derived state
        are recomputed on every read. Outdated/download paths should call
        this after mutating their stores so the next read serves the new
        signal without waiting out the TTL. Never raises.
        """
        try:
            self._pack_status_cache = None
            self._pack_status_cached_at = 0.0
        except Exception:
            log.debug("[SERVICE] offline pack cache invalidate failed", exc_info=True)

    def _get_offline_pack_status(self) -> dict[str, object]:
        """Cheap, cached offline-pack state for the degradation matrix (§8.10).

        Returns ``{"installed_version": <str|None>, "available": bool,
        "consent_granted": bool, "download_progress": <int|None>,
        "state": <str>, "outdated_info": <dict|None>}`` where
        ``download_progress`` is 0-100 while downloading, 100 once bytes
        land, None otherwise (PK-2 mount catch-up reads it); ``state`` is
        the stable PK-2 machine (outdated > downloading > verifying >
        ready > missing); ``outdated_info`` is ``{version,
        min_proto_version}`` when the PK-1 stale-pack signal is set.
        The TTL gates the version scan only: cached copies keep the scan
        fields but always carry fresh progress + freshly derived state.
        """
        from voice_typer.server.service.offline_pack.progress import get_download_progress

        progress: int | None = None
        try:
            progress = get_download_progress()
        except Exception:
            log.debug("[SERVICE] offline pack progress unavailable", exc_info=True)
            progress = None
        now = time.monotonic()
        cached = self._pack_status_cache
        if cached is not None and (now - self._pack_status_cached_at) < self._OFFLINE_PACK_STATUS_TTL_S:
            fresh = dict(cached)
            fresh["download_progress"] = progress
            outdated_info = self._read_pack_outdated_info()
            fresh["outdated_info"] = outdated_info
            fresh["state"] = self._derive_pack_state(
                fresh.get("installed_version"), progress, outdated_info
            )
            return fresh
        state: dict[str, object] = {
            "installed_version": None,
            "available": False,
            "consent_granted": False,
            "download_progress": progress,
            "state": "missing",
            "outdated_info": None,
        }
        try:
            from voice_typer.server.service import update_check

            local = update_check._local_offline_pack_version()
            state["installed_version"] = local
            state["available"] = local is not None
            # Always-on: consent is not user-disableable.
            state["consent_granted"] = True
        except Exception:  # fail-safe: degraded state, never raise
            log.debug("[SERVICE] offline pack status unavailable", exc_info=True)
        outdated_info = self._read_pack_outdated_info()
        state["outdated_info"] = outdated_info
        state["state"] = self._derive_pack_state(
            state.get("installed_version"), progress, outdated_info
        )
        self._pack_status_cache = state
        self._pack_status_cached_at = now
        return dict(state)

    def get_status(self) -> "StatusResponse":
        """Return the current app state plus audio-quality telemetry."""
        app = self._app
        status_str = app.tray.state.value
        # The tray-tooltip reason accompanying the current state (e.g.
        message = ""
        try:
            raw_message = getattr(app.tray, "_message", "")
            if isinstance(raw_message, str):
                message = raw_message
        except Exception:
            log.debug("[SERVICE] could not read tray message", exc_info=True)
        # Best-effort: xruns counter exists on the Recorder instance.
        xruns = 0
        try:
            xruns = int(getattr(app.recorder, "_xruns", 0) or 0)
        except Exception:
            log.debug("[SERVICE] could not read xrun counter", exc_info=True)
        # read the active engine's loaded_via property.
        loaded_via = ""
        try:
            active = app.models._registry.get_active() if hasattr(app, "models") and app.models else None
            if active is not None and hasattr(active, "loaded_via"):
                loaded_via = str(active.loaded_via)
        except Exception:
            log.debug("[SERVICE] could not read loaded_via", exc_info=True)
        # expose the resolved config directory so the About page's
        config_dir = ""
        try:
            config_dir = str(app.config.config_dir)
        except Exception:
            log.debug("[SERVICE] could not read config_dir", exc_info=True)
        return {
            "status": status_str,
            "message": message,
            "xruns_since_start": xruns,
            "loaded_via": loaded_via,
            "config_dir": config_dir,
            "offline_pack": self._get_offline_pack_status(),
        }

    def _read_output_level(self) -> float | None:
        """Live master-output level in ``[0.0, 1.0]``; ``None`` when unreadable.

        Deliberately NOT stored in ``_volume_backend_status_cache``: the
        renderer decides its one-time "your speakers are loud" offer from
        this value, and a 30s-old reading would offer against a level the
        user has already moved. Only the capability flags are cached.
        """
        backend = getattr(getattr(self._app, "_volume_ducker", None), "_backend", None)
        if backend is None:
            return None
        try:
            state = backend.get_state()
        except Exception:
            log.debug("[SERVICE] output level read failed", exc_info=True)
            return None
        if state is None:
            return None
        try:
            return max(0.0, min(1.0, float(state.linear)))
        except (TypeError, ValueError):
            return None

    def get_volume_backend_status(self, *, _force_refresh: bool = False) -> dict[str, object]:
        """Return the volume ducking backend status.

        ``output_level`` is read live on every call (see
        :meth:`_read_output_level`); the rest of the dict is TTL-cached.
        """
        ducker = getattr(self._app, "_volume_ducker", None)
        if ducker is None:
            return {
                "available": False,
                "name": "disabled",
                "supports_per_session": False,
                "output_level": None,
            }

        # Fast path: serve from cache when available and the caller
        cache = self._volume_backend_status_cache
        cache_fresh = (time.monotonic() - self._volume_backend_status_cached_at) < self._VOLUME_BACKEND_STATUS_TTL_S
        if cache is not None and not _force_refresh and cache_fresh:
            fresh = dict(cache)
            fresh["output_level"] = self._read_output_level()
            return fresh

        try:
            # Trigger initialize() so the backend name reflects
            init_ok = False
            try:
                ducker.initialize()
                # reset notify-once guard on success.
                StatusMixin._volume_ducker_init_warned = False
                init_ok = True
            except Exception:
                # notify-once, log first failure at WARNING,
                if not StatusMixin._volume_ducker_init_warned:
                    log.warning(
                        "[SERVICE] volume_ducker.initialize failed - subsequent failures will be logged at DEBUG",
                        exc_info=True,
                    )
                    StatusMixin._volume_ducker_init_warned = True
                else:
                    log.debug(
                        "[SERVICE] volume_ducker.initialize failed (repeat)",
                        exc_info=True,
                    )
            status = {
                "available": bool(ducker.is_available),
                "name": ducker.backend_name,
                "supports_per_session": bool(ducker.supports_per_session),
                "backend": type(ducker).__name__,
            }
            # Cache the status only when initialize() succeeded OR
            if init_ok or _force_refresh:
                self._volume_backend_status_cache = status
                self._volume_backend_status_cached_at = time.monotonic()
            fresh = dict(status)
            fresh["output_level"] = self._read_output_level()
            return fresh
        except Exception as exc:
            # redact exc string before returning to IPC layer.
            log.warning(
                "[SERVICE] get_volume_backend_status failed: %s",
                redact_secret(redact_url(str(exc))),
            )
            return {
                "available": False,
                "name": "disabled",
                "supports_per_session": False,
                "reason": redact_secret(redact_url(str(exc))),
                "output_level": None,
            }

    def get_microphone_volume(self) -> dict[str, object]:
        """Current capture-gain state for the mic guard surface.

        ``available`` is False until the guard's backend resolves, so the
        renderer can tell "no capture endpoint" from "level is 0". When
        ``supports_set`` is False (most built-in macOS mics) the renderer
        shows the guard message WITHOUT a restore button.
        """
        guard = getattr(self._app, "_mic_guard", None)
        if guard is None:
            return {"available": False, "level": None, "supports_set": False, "name": "disabled"}
        return {
            "available": bool(getattr(guard, "is_available", False)),
            "level": guard.get_level(),
            "supports_set": bool(getattr(guard, "supports_set", False)),
            "name": str(getattr(guard, "backend_name", "") or "disabled"),
        }

    def set_microphone_volume(self, level: float) -> dict[str, object]:
        """Write the REAL device capture gain. Used by ``[Back to 100%]``.

        Deliberately not a slider and not restore-previous: the previous
        value is the broken one, and a slider becomes a tug toy while a
        driver keeps pulling. The user's own write never consumes the
        anti-flap budget.
        """
        guard = getattr(self._app, "_mic_guard", None)
        if guard is None:
            return {"ok": False, "level": None}
        try:
            target = max(0.0, min(1.0, float(level)))
        except (TypeError, ValueError):
            return {"ok": False, "level": None}
        return {"ok": bool(guard.set_level(target)), "level": target}

    def set_output_volume(self, level: float) -> dict[str, object]:
        """Set the master output level. Backs the S1 ``[Lower to 75%]`` offer.

        This is the ONLY place the app writes the speaker knob outside
        dictation ducking, and it only ever runs from an explicit user
        press — Live monitoring never moves the speakers on its own.
        """
        ducker = getattr(self._app, "_volume_ducker", None)
        if ducker is None:
            return {"ok": False, "level": None}
        try:
            target = max(0.0, min(1.0, float(level)))
        except (TypeError, ValueError):
            return {"ok": False, "level": None}
        try:
            if not ducker.initialize():
                return {"ok": False, "level": None}
            ok = bool(ducker.set_level(target))
        except Exception:
            log.debug("[SERVICE] set_output_volume failed", exc_info=True)
            return {"ok": False, "level": None}
        return {"ok": ok, "level": target}

    def get_audio_status(self) -> dict:
        """Return the audio filter chain status (ADR 0007)."""
        app = self._app
        processor = getattr(app, "_audio_processor", None)
        if processor is not None:
            return {
                "filter_chain": processor.filter_names,
                "degraded": processor.is_degraded,
                "degraded_reasons": processor.degraded_reasons,
                "latency_ms": processor.total_latency_ms,
                "vad_backend": "silero" if app.config.use_silero_vad else "rms",
                "sample_rate": app.config.sample_rate,
            }
        return {
            "filter_chain": [],
            "degraded": False,
            "degraded_reasons": [],
            "latency_ms": 0.0,
            "vad_backend": "rms",
            "sample_rate": WHISPER_SAMPLE_RATE,
        }
