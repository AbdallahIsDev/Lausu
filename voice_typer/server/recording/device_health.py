"""Device health-checker thread, permission probe, and sample-rate drift.

Extracted from ``device_manager`` by a create-first split: the storage
lives on :class:`device_manager.DeviceManager`, the mixin owns the
behaviour. ``sd`` is resolved from the facade at call time because
tests replace ``device_manager.sd`` wholesale.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import TYPE_CHECKING, Any

log = logging.getLogger("voice_typer.server.recording")


class _DeviceHealthMixin:
    """Health-checker concerns of :class:`device_manager.DeviceManager`.

    The annotation-only declarations are the host-state contract: every
    value is initialised by ``DeviceManager.__init__``.
    """

    recorder: Any
    _device_disconnected: bool
    _device_health_checker_thread: threading.Thread | None
    _device_health_stop_event: threading.Event
    _device_check_interval_s: float
    _device_check_interval_s_bt: float
    _permission_check_counter: int
    _permission_check_interval: int
    _last_default_input_info: dict | None
    _stream_open_default_input_index: Any | None

    if TYPE_CHECKING:
        # Facade-provided method plus the sibling mixin's retry-policy helper.
        def _resolve_device(self) -> int | None: ...

        def _build_device_info_for_retry_policy(
            self,
            *,
            allow_live_default_fallback: bool = True,
        ) -> dict | None: ...

        def _get_max_retries_for_device(self, device_info: dict | None) -> int: ...

        def _cached_device_info(self, device: int | None) -> dict | None: ...


    def _start_device_health_checker(self) -> None:
        """Start the device health checker daemon thread."""
        if self._device_health_checker_thread is not None and self._device_health_checker_thread.is_alive():
            return
        self._device_health_stop_event.clear()
        self._device_health_checker_thread = threading.Thread(
            target=self._device_health_checker_loop,
            name="device-health-checker",
            daemon=True,
        )
        self._device_health_checker_thread.start()

    def _stop_device_health_checker(self) -> None:
        """Signal the device health checker thread to stop and join it."""
        self._device_health_stop_event.set()
        thread = self._device_health_checker_thread
        if thread is not None:
            thread.join(timeout=1.0)
            health_exited = not thread.is_alive()
            if not health_exited:
                log.debug(
                    "[RECORDING] Device health checker thread did not exit within 1s "
                    "(stop event left SET; thread NOT nulled to prevent duplicate spawn)"
                )
            # only null the thread reference + clear stop event if the
            if health_exited:
                self._device_health_checker_thread = None
                self._device_health_stop_event.clear()

    def stop_device_health_checker(self, timeout: float | None = None) -> None:
        """Signal the device health checker thread to stop and join it."""
        if timeout == 0.0:
            # Fire-and-forget: signal the stop event, do NOT join. The
            self._device_health_stop_event.set()
            return
        self._stop_device_health_checker()

    def _device_health_checker_loop(self) -> None:
        """Device health checker daemon thread main loop."""
        # Call-time facade read: tests replace ``device_manager.sd``.
        from .device_manager import sd

        while True:
            # Compute the effective poll interval per iteration. BT
            effective_interval = self._effective_device_check_interval_s()
            if self._device_health_stop_event.wait(timeout=effective_interval):
                return
            # skip the check if we've already detected a disconnect
            if self._device_disconnected:
                continue
            # periodic OS-level microphone-permission re-probe.
            self._permission_check_counter += 1
            if self._permission_check_counter >= self._permission_check_interval:
                self._permission_check_counter = 0
                if self._check_microphone_permission_revoked():
                    # Permission was revoked mid-recording. The
                    continue
            try:
                current_device = self._resolve_device()
                if current_device is not None:
                    try:
                        dev_info = sd.query_devices(current_device)
                    except Exception:
                        # HOTKEY-CRASH: double-check recording is still active.
                        if not self.recorder._recording_event.is_set():
                            return
                        log.warning(
                            "[RECORDING] Current device no longer available in query_devices -- disconnect detected"
                        )
                        self._device_disconnected = True
                        _captured_gen = self.recorder._stop_generation
                        # Route through ``_spawn_device_thread`` so
                        with contextlib.suppress(Exception):
                            self.recorder._spawn_device_thread(
                                name="device-disconnect-check",
                                target=self.recorder._handle_device_disconnect,
                                kwargs={"_captured_generation": _captured_gen},
                                single_flight=True,
                            )
                    else:
                        # Sample-rate drift detection. After
                        if self._detect_sample_rate_drift(dev_info):
                            if not self.recorder._recording_event.is_set():
                                return
                            log.warning(
                                "[RECORDING] Sample-rate drift detected on current "
                                "device -- disconnect recovery will pick up the new rate"
                            )
                            self._device_disconnected = True
                            _captured_gen = self.recorder._stop_generation
                            with contextlib.suppress(Exception):
                                self.recorder._spawn_device_thread(
                                    name="device-samplerate-drift",
                                    target=self.recorder._handle_device_disconnect,
                                    kwargs={"_captured_generation": _captured_gen},
                                    single_flight=True,
                                )
                else:
                    # ``current_device is None`` → ``config.microphone
                    self._check_default_input_device_changed()
            except Exception:
                log.debug("[RECORDING] Device health checker error", exc_info=True)

    def _effective_device_check_interval_s(self) -> float:
        """Return the effective health-checker interval for the current device."""
        try:
            # ``allow_live_default_fallback=False``: on the System
            dev_info = self._build_device_info_for_retry_policy(
                allow_live_default_fallback=False,
            )
            if dev_info is not None and self._get_max_retries_for_device(dev_info) >= 6:
                return self._device_check_interval_s_bt
        except Exception:
            log.debug(
                "[RECORDING] BT-classification query failed; using default health-checker interval",
                exc_info=True,
            )
        return self._device_check_interval_s

    def record_stream_open_default_input_index(self, index: Any | None = None) -> None:
        """Record the OS default input device index at stream-open time."""
        self._stream_open_default_input_index = index

    def _check_default_input_device_changed(self, current_info: dict | None = None) -> None:
        """Detect OS default input device change when ``config.microphone is None``."""
        if current_info is None:
            current_info = self._cached_device_info(None)
            if current_info is None:
                log.debug(
                    "[RECORDING] canonical + raw default query failed; "
                    "skipping default-input-device change check this cycle",
                    exc_info=True,
                )
                return
        if not isinstance(current_info, dict):
            return
        try:
            current_index = current_info.get("index")
        except Exception:
            return
        if current_index is None:
            return
        # Stash for the next cycle's BT classification so the health
        self._last_default_input_info = current_info
        stream_open_index = self._stream_open_default_input_index
        # Lazily capture the baseline on the first successful query
        if stream_open_index is None:
            self._stream_open_default_input_index = current_index
            return
        if current_index == stream_open_index:
            return
        log.warning(
            "[RECORDING] OS default input device changed (index %r -> %r) "
            "— routing through disconnect handler to re-open against the new OS default",
            stream_open_index,
            current_index,
        )
        # HOTKEY-CRASH: double-check recording is still active before
        try:
            if not self.recorder._recording_event.is_set():
                return
        except AttributeError:
            pass
        self._device_disconnected = True
        # Update the baseline so a subsequent iteration doesn't
        self._stream_open_default_input_index = current_index
        _captured_gen = getattr(self.recorder, "_stop_generation", 0)
        with contextlib.suppress(Exception):
            self.recorder._spawn_device_thread(
                name="device-default-input-changed",
                target=self.recorder._handle_device_disconnect,
                kwargs={"_captured_generation": _captured_gen},
                single_flight=True,
            )

    def _verify_post_restart_sample_rate(
        self,
        restart_device: Any,
        candidate_sr: Any,
    ) -> None:
        """Re-query the device's ``default_samplerate`` after a restart and"""
        # Call-time facade read: tests replace ``device_manager.sd``.
        from .device_manager import sd

        if restart_device is None or candidate_sr is None:
            return
        try:
            post_info = sd.query_devices(restart_device)
        except Exception:
            log.debug(
                "[RECORDING] post-restart sd.query_devices(%r) failed; skipping immediate drift re-check",
                restart_device,
                exc_info=True,
            )
            return
        if not isinstance(post_info, dict):
            return
        try:
            post_sr = post_info.get("default_samplerate")
            if post_sr is None:
                return
            post_sr = float(post_sr)
            cand_sr = float(candidate_sr)
        except (TypeError, ValueError):
            return
        if abs(post_sr - cand_sr) <= 1.0:
            return
        log.warning(
            "[RECORDING] Post-restart sample-rate drift detected on device %r "
            "(candidate_sr=%r, device default_samplerate=%r), scheduling immediate drift re-check",
            restart_device,
            candidate_sr,
            post_sr,
        )
        # Immediate drift re-check: if the recorder's ``_effective_sr``
        if self._detect_sample_rate_drift(post_info):
            try:
                if not self.recorder._recording_event.is_set():
                    return
            except AttributeError:
                pass
            self._device_disconnected = True
            _captured_gen = getattr(self.recorder, "_stop_generation", 0)
            with contextlib.suppress(Exception):
                self.recorder._spawn_device_thread(
                    name="device-post-restart-drift",
                    target=self.recorder._handle_device_disconnect,
                    kwargs={"_captured_generation": _captured_gen},
                    single_flight=True,
                )

    def _detect_sample_rate_drift(self, dev_info: Any) -> bool:
        """Return True if the device's ``default_samplerate`` differs from"""
        if not isinstance(dev_info, dict):
            return False
        try:
            current_native = dev_info.get("default_samplerate")
            if current_native is None:
                return False
            current_native = float(current_native)
        except (TypeError, ValueError):
            return False
        effective_sr = getattr(self.recorder, "_effective_sr", None)
        if effective_sr is None:
            return False
        try:
            effective_sr = float(effective_sr)
        except (TypeError, ValueError):
            return False
        # Tolerance: 1 Hz. ``default_samplerate`` is a float from
        return abs(current_native - effective_sr) > 1.0

    def _check_microphone_permission_revoked(self) -> bool:
        """probe the OS-level microphone permission state.

        Returns True if the permission was detected as DENIED, in which
        """
        # Lazy import to avoid paying the import cost on every loop wake
        try:
            from voice_typer.server import permissions as _permissions_mod

            state = _permissions_mod.check_microphone_permission()
        except Exception:
            log.debug(
                "[RECORDING] Microphone permission probe raised, ignoring",
                exc_info=True,
            )
            return False

        # ``MicrophonePermissionState.DENIED`` is the only state we act
        try:
            denied = state == _permissions_mod.MicrophonePermissionState.DENIED
        except Exception:
            denied = str(state).lower() == "denied"

        if not denied:
            return False

        # HOTKEY-CRASH: double-check recording is still active before
        try:
            if not self.recorder._recording_event.is_set():
                return False
        except AttributeError:
            # ``_recording_event`` may not be set yet during early init —
            pass

        log.warning(
            "[RECORDING] Microphone permission revoked mid-recording -- "
            "stopping stream and surfacing on_microphone_permission_revoked"
        )
        self._device_disconnected = True
        _captured_gen = getattr(self.recorder, "_stop_generation", 0)

        def _permission_revoked_handler(_captured_generation: int = _captured_gen) -> None:
            """Spawned on a fresh daemon thread so we don't block the"""
            try:
                cb = getattr(self.recorder, "on_microphone_permission_revoked", None)
                if callable(cb):
                    cb()
                else:
                    # Fallback: if the callback isn't wired (older
                    device_lost_cb = getattr(self.recorder, "on_device_lost", None)
                    if callable(device_lost_cb):
                        with contextlib.suppress(Exception):
                            device_lost_cb()
                    elif self.recorder.on_silence_auto_stop is not None:
                        with contextlib.suppress(Exception):
                            self.recorder.on_silence_auto_stop()
            except Exception:
                log.debug(
                    "[RECORDING] on_microphone_permission_revoked handler raised",
                    exc_info=True,
                )

        with contextlib.suppress(Exception):
            self.recorder._spawn_device_thread(
                name="mic-permission-revoked",
                target=_permission_revoked_handler,
                kwargs={"_captured_generation": _captured_gen},
                single_flight=True,
            )
        return True
