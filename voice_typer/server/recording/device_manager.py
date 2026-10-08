"""Device enumeration, hot-swap, and health-checker for :class:`Recorder`."""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from voice_typer.server._lazy_import import lazy_module

from .device_health import _DeviceHealthMixin
from .device_resolution import _DeviceResolutionMixin

# PERF-COLDSTART-001: lazy import, sounddevice loads the PortAudio C
sd = lazy_module("sounddevice")

# All submodules use the package-level logger so log records propagate
log = logging.getLogger("voice_typer.server.recording")

# when the mic device watcher fails to start (e.g. on macOS
_DEVICE_LIST_FAST_TTL: float = 5.0


class DeviceManager(_DeviceHealthMixin, _DeviceResolutionMixin):
    """Device enumeration, hot-swap, and health-checker for ``Recorder``."""

    def __init__(self, recorder: Any) -> None:
        # Collaborator back-reference. Typed ``Any`` to avoid a circular
        self.recorder = recorder

        # AUDIO-HOT: hot-plug device disconnect handling
        self._device_disconnected: bool = False
        self._device_disconnect_retries: int = 0
        self._max_disconnect_retries: int = 3
        # AUDIO-HOT: periodic device availability check, every N chunks,
        self._device_check_interval: int = 500  # check every ~500 chunks (~32s at 16Hz)
        self._device_check_counter: int = 0
        # Dedicated device-health-checker thread state. The checker
        self._device_health_checker_thread: threading.Thread | None = None
        self._device_health_stop_event: threading.Event = threading.Event()
        self._device_check_interval_s: float = 30.0  # seconds between probes
        # BT-narrowband devices get a shorter health-check interval (5 s)
        self._device_check_interval_s_bt: float = 5.0
        # counter for periodic OS-level microphone-permission
        self._permission_check_counter: int = 0
        # With the default 30 s interval, every 2nd iteration = ~60 s.
        self._permission_check_interval: int = 2

        # AUDIO-MIC: device list cache with timestamp
        self._device_list_cache: list[dict] | None = None
        self._device_list_cache_time: float = 0.0
        self._device_list_cache_ttl: float = 30.0  # seconds

        # PERF-MIC-001: OS-event-driven cache invalidation. The watcher
        self._mic_watcher: Any | None = None
        # optional service-layer cache invalidator callback.
        self._service_cache_invalidator: Any | None = None
        # configurable sleep between BT-device disconnect retries.
        self._bt_retry_sleep_seconds: float = 0.75
        # Last successful ``sd.query_devices(kind="input")`` result from
        self._last_default_input_info: dict | None = None
        # OS default-input index captured at stream-open (or lazily on
        self._stream_open_default_input_index: Any | None = None
        # Lazy host-API index → name cache. Populated on first
        self._host_api_cache: dict[int, str] = {}
        try:
            from voice_typer.server.microphone_watcher import (
                MicrophoneDeviceWatcher,
            )

            # (pyrefly): bind to a local so pyrefly can see the
            watcher: Any = MicrophoneDeviceWatcher(on_change=self._invalidate_device_cache)
            watcher.start()
            self._mic_watcher = watcher
        except Exception:
            # Watcher is best-effort, the 30s TTL cache covers the
            log.warning(
                "[RECORDING] mic device watcher failed to start, falling back to 5s TTL polling for the session",
                exc_info=True,
            )
            self._mic_watcher = None

    def _refresh_device_list(self) -> list[dict]:
        """Return the device list, refreshing the cache if stale."""
        now = time.monotonic()
        # compute the effective TTL based on whether an OS-event
        if self._mic_watcher is None:
            effective_ttl: float = _DEVICE_LIST_FAST_TTL
        else:
            effective_ttl = self._device_list_cache_ttl
        if self._device_list_cache is not None and now - self._device_list_cache_time < effective_ttl:
            return self._device_list_cache

        try:
            # Shared PortAudio walk + filters with the canonical UI list
            _shared_walk: Callable[[Any], list[tuple[int, dict[str, Any], str]]] | None = None
            try:
                from voice_typer.server.server_platform.microphone_list import (
                    iter_filtered_input_devices as _shared_walk,
                )
            except Exception:
                log.debug("[RECORDING] shared device walk unavailable, skipping name filters", exc_info=True)

            if _shared_walk is not None:
                filtered_inputs = _shared_walk(sd.query_devices())
            else:
                # Import-failure fallback: channel filter only (the
                filtered_inputs = []
                for i, dev in enumerate(sd.query_devices()):
                    if isinstance(dev, dict) and dev.get("max_input_channels", 0) > 0:
                        raw_name = dev.get("name", "")
                        name = raw_name.strip() if isinstance(raw_name, str) else ""
                        filtered_inputs.append((i, dev, name))

            devices = []
            for i, dev, _name in filtered_inputs:
                devices.append(
                    {
                        "index": i,
                        "name": dev.get("name", ""),
                        "max_input_channels": dev.get("max_input_channels", 0),
                        # Cache the native sample rate and host-API index
                        "default_samplerate": dev.get("default_samplerate", 0),
                        "hostapi": dev.get("hostapi", 0),
                    }
                )
            self._device_list_cache = devices
            self._device_list_cache_time = now
            return devices
        except Exception as e:
            log.debug("[RECORDING] Could not enumerate devices: %s", e)
            return self._device_list_cache or []

    def _resolve_device(self):
        """Resolve config.microphone to a sounddevice device specifier."""
        mic = self.recorder.config.microphone
        if mic is None:
            return None
        try:
            from voice_typer.server.server_platform.microphone_list import resolve_mic_id_to_device_index
        except Exception:
            log.debug("[RECORDING] canonical mic resolver unavailable; using system default", exc_info=True)
            return None
        try:
            resolved = resolve_mic_id_to_device_index(mic)
        except Exception:
            log.debug("[RECORDING] mic id %r resolution failed; using system default", mic, exc_info=True)
            return None
        return resolved

    def set_service_cache_invalidator(self, callback: Any | None) -> None:
        """Register a service-layer cache invalidator ()."""
        self._service_cache_invalidator = callback

    def _invalidate_device_cache(self) -> None:
        """Reset the device-list cache so the next ``_refresh_device_list``"""
        self._device_list_cache = None
        self._device_list_cache_time = 0.0
        # Device churn is routine; keep the log free of per-event noise.

        # fire the service-layer cache invalidator (best-effort).
        service_cb = self._service_cache_invalidator
        if service_cb is not None:
            try:
                service_cb()
            except Exception:
                log.debug(
                    "[RECORDING] service cache invalidator callback raised",
                    exc_info=True,
                )

        # (High): proactive recovery on hot-plug while a disconnect
        if not self._device_disconnected:
            return
        try:
            if not self.recorder._recording_event.is_set():
                return
        except AttributeError:
            # ``_recording_event`` may not be set yet during early init —
            pass
        _captured_gen = getattr(self.recorder, "_stop_generation", 0)
        with contextlib.suppress(Exception):
            self.recorder._spawn_device_thread(
                name="device-hotplug-recovery",
                target=self.recorder._handle_device_disconnect,
                kwargs={"_captured_generation": _captured_gen},
                single_flight=True,
            )
        log.info(
            "[RECORDING] hot-plug event triggered disconnect recovery (device was disconnected, re-attempting restart)"
        )

    def shutdown_mic_watcher(self) -> None:
        """Stop the microphone device-change watcher.

        Called explicitly from ``LausuApp.quit_app()`` during
        shutdown and defensively from ``Recorder.__del__``. Safe to call
        even if the watcher never started (``_mic_watcher`` is None).
        """
        watcher = getattr(self, "_mic_watcher", None)
        if watcher is None:
            return
        try:
            watcher.stop()
        except Exception:
            log.debug("[RECORDING] mic watcher stop failed", exc_info=True)
        self._mic_watcher = None
