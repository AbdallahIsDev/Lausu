"""Retry policy, cached device info, and fallback-candidate resolution.

Extracted from ``device_manager`` by a create-first split: the cache
storage lives on :class:`device_manager.DeviceManager`; the mixin owns the
retry / fallback logic. ``_resolve_device`` stays on the facade, where its
canonical-resolver delegation is pinned by a source tripwire. ``sd`` is
resolved from the facade at call time because tests replace
``device_manager.sd`` wholesale.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from voice_typer.server._audio_constants import SILERO_VAD_SAMPLE_RATES

log = logging.getLogger("voice_typer.server.recording")


class _DeviceResolutionMixin:
    """Resolution concerns of :class:`device_manager.DeviceManager`.

    The annotation-only declarations are the host-state contract: every
    value is initialised by ``DeviceManager.__init__``.
    """

    recorder: Any
    _device_list_cache: list[dict] | None
    _host_api_cache: dict[int, str]
    _last_default_input_info: dict | None
    _bt_retry_sleep_seconds: float

    if TYPE_CHECKING:
        # Methods provided by the facade class itself.
        def _refresh_device_list(self) -> list[dict]: ...

        def _resolve_device(self) -> int | None: ...


    def _build_device_info_for_retry_policy(
        self,
        *,
        allow_live_default_fallback: bool = True,
    ) -> dict | None:
        """Return the current device info for BT retry classification."""
        try:
            current = self._resolve_device()
            if current is None:
                stashed = self._last_default_input_info
                if stashed is not None:
                    return stashed
                if not allow_live_default_fallback:
                    # Health-checker path: skip the live query. The
                    return None
                return self._cached_device_info(None)
            return self._cached_device_info(current)
        except Exception:
            return None

    def _get_max_retries_for_device(self, device_info: dict | None) -> int:
        """return the max retry count for the given device."""
        if device_info is None:
            return 3
        name = str(device_info.get("name", "")).lower()
        if any(kw in name for kw in ("bluetooth", "hfp", "hands-free", "hands free")):
            return 6
        try:
            sr = int(device_info.get("default_samplerate", 0))
        except (ValueError, TypeError):
            sr = 0
        if sr in SILERO_VAD_SAMPLE_RATES:
            return 6
        return 3

    def _get_retry_sleep_for_device(self, device_info: dict | None) -> float:
        """return the per-retry sleep for the given device."""
        if device_info is None:
            return 0.0
        if self._get_max_retries_for_device(device_info) >= 6:
            return self._bt_retry_sleep_seconds
        return 0.0

    def _host_api_name(self, host_api_index: int) -> str:
        """Return the host-API name for the given index, with a one-shot cache."""
        # Call-time facade read: tests replace ``device_manager.sd``.
        from .device_manager import sd

        cached = self._host_api_cache.get(host_api_index)
        if cached is not None:
            return cached
        try:
            name = str(sd.query_hostapis(host_api_index)["name"])
        except Exception:
            return ""
        self._host_api_cache[host_api_index] = name
        return name

    def _canonical_default_index(self) -> int | None:
        """Return the canonical default input index, or ``None``."""
        try:
            from voice_typer.server.server_platform.microphone_list import (
                get_canonical_default_index as _canonical_default,
            )

            result = _canonical_default()
            return int(result) if result is not None else None
        except (TypeError, ValueError):
            return None
        except Exception:
            log.debug("[RECORDING] canonical default index lookup failed", exc_info=True)
            return None

    def _cached_device_info(self, device: int | None) -> dict | None:
        """Look up the cached device info dict for ``device``.

        Returns the cached entry from ``_device_list_cache`` when the
        index is present (fast path, no PortAudio RPC). Falls back to
        a live ``sd.query_devices(device)`` query on cache miss (e.g.
        the cache is stale, the device was just hot-plugged, or the
        TTL expired between the ``_refresh_device_list`` call and this
        lookup). Returns ``None`` if both the cache lookup and the
        live query fail, callers must handle ``None`` gracefully
        (same as the pre-fix ``sd.query_devices`` exception path).

        For ``device=None`` (system default input), resolve through the
        canonical host-API view first so the sample-rate probe and the
        stream open agree with the UI list (WASAPI on Windows). Only
        when the canonical view has no usable default does this fall
        through to the live ``sd.query_devices(kind="input")`` query
        (preserves the pre-fix behavior for the OS-default path).

        Returns ``None`` when the resolved value is not a ``dict``
        (defensive: some test stubs / broken host-API layers return a
        list or other shape; callers contract is dict-or-None).
        """
        # Call-time facade read: tests replace ``device_manager.sd``.
        from .device_manager import sd

        if device is None:
            canonical = self._canonical_default_index()
            if canonical is not None:
                resolved = self._cached_device_info(canonical)
                if resolved is not None:
                    return resolved
            try:
                info = sd.query_devices(kind="input")
            except Exception:
                return None
            return info if isinstance(info, dict) else None
        cache = self._device_list_cache
        if cache is not None:
            for entry in cache:
                try:
                    if int(entry.get("index", -1)) == device:
                        return entry
                except (TypeError, ValueError):
                    continue
        # Cache miss, fall back to a live query. This preserves
        try:
            info = sd.query_devices(device)
        except Exception:
            return None
        return info if isinstance(info, dict) else None

    def _device_index(self, fallback_index: int, device_info: dict) -> int:
        try:
            return int(device_info.get("index", fallback_index))
        except Exception:
            return fallback_index

    def _same_physical_microphone_candidates(self, device: Any) -> list[Any]:
        """Return equivalent input device IDs to try if the selected one fails."""
        candidates = [device]
        if device is None:
            # Null means System Default (fresh-install default): resolve it
            try:
                canonical = self._canonical_default_index()
                if canonical is not None:
                    return [canonical]
            except Exception:
                log.debug(
                    "[RECORDING] canonical default lookup failed, using OS default",
                    exc_info=True,
                )
            return candidates
        if not isinstance(device, int):
            return candidates

        # Use the cached device info + cached device list instead of
        selected = self._cached_device_info(device)
        if selected is None:
            return candidates
        selected_name = selected.get("name", "").strip().lower()
        all_devices = self._refresh_device_list()
        if not selected_name:
            return candidates

        alternates = []
        for fallback_index, info in enumerate(all_devices):
            index = self._device_index(fallback_index, info)
            if index == device:
                continue
            if info.get("max_input_channels", 0) <= 0:
                continue
            if info.get("name", "").strip().lower() != selected_name:
                continue
            host_name = self._host_api_name(info.get("hostapi", 0))
            alternates.append((self._fallback_host_rank(host_name), index))

        alternates.sort()
        seen = set()
        ordered = []
        for candidate in candidates + [index for _, index in alternates]:
            marker = str(candidate)
            if marker in seen:
                continue
            ordered.append(candidate)
            seen.add(marker)
        return ordered

    def _fallback_host_rank(self, host_name: str) -> int:
        """REC-6: rank host APIs for fallback device selection."""
        lower = host_name.lower()
        # Windows hosts
        if "wasapi" in lower:
            return 0
        if lower == "mme":
            return 1
        if "wdm-ks" in lower:
            return 2
        if "directsound" in lower:
            return 3
        # macOS hosts
        if "coreaudio" in lower or "core audio" in lower:
            return 0
        # Linux hosts
        if lower == "alsa":
            return 0
        if "pulseaudio" in lower:
            return 1
        if lower == "jack":
            return 2
        # Unknown host, lowest priority but not last (leaves room for
        return 5

    def _resolve_effective_sample_rate(self, device: int | None) -> tuple[int, dict | None]:
        """Determine the effective sample rate and device info for the given device.

        Returns (effective_sr, dev_info_dict) where dev_info_dict has
        """
        target_sr = self.recorder.config.sample_rate  # 16000 for Whisper
        dev_info_extra = None
        try:
            # Use the cached device info (fast path, no PortAudio RPC)
            dev_info = self._cached_device_info(device)
            if dev_info is None:
                # Both cache and live query failed. Raise to trigger
                raise RuntimeError(f"Could not query device info for device {device} (cache miss + live query failed)")
            raw_native_rate = int(dev_info.get("default_samplerate", 0))
            # Drivers can report 0 (or another implausible value) for an
            # endpoint that is not open yet; feeding it to the stream makes
            # PortAudio reject the open with paInvalidSampleRate even though
            # the target rate + resample path would work. Treat anything
            # outside the plausible audio range as unknown (same outcome as
            # the query-failure branch below).
            if 8000 <= raw_native_rate <= 384000:
                native_rate = raw_native_rate
            else:
                native_rate = target_sr
                log.warning(
                    "[RECORDING] Device %r reported an unusable default_samplerate=%r; "
                    "falling back to the target rate %d Hz",
                    dev_info.get("name", ""),
                    raw_native_rate,
                    target_sr,
                )
            host_api_idx = dev_info.get("hostapi", 0)
            host_api_name = self._host_api_name(host_api_idx)
            dev_info_extra = {
                "name": dev_info.get("name", ""),
                "host_api_name": host_api_name,
                "native_rate": native_rate,
            }
            log.debug(
                "[RECORDING] Device query: name=%s, host_api=%s | native_rate=%d, target_rate=%d",
                dev_info.get("name", ""),
                host_api_name,
                native_rate,
                target_sr,
            )

            # If the device's native rate matches the target, use it directly.
            if native_rate == target_sr:
                log.debug(
                    "[RECORDING] Native rate matches target, using %d Hz directly",
                    target_sr,
                )
                return target_sr, dev_info_extra
            else:
                log.debug(
                    "[RECORDING] Native rate %d differs from target %d, will record at native rate and resample",
                    native_rate,
                    target_sr,
                )
                return native_rate, dev_info_extra
        except Exception:
            # log at WARNING (not DEBUG) so the user knows
            log.warning(
                "[RECORDING] Device %s info unavailable, falling back to %d Hz (PortAudio resamples)",
                device,
                target_sr,
            )
            return target_sr, dev_info_extra

    def _all_input_device_candidates(self) -> list[int]:
        """Return all available input device IDs as a last-resort fallback."""
        # Call-time facade read: tests replace ``device_manager.sd``.
        from .device_manager import sd

        candidates = []
        try:
            all_devices = list(sd.query_devices())
            for fallback_index, info in enumerate(all_devices):
                index = self._device_index(fallback_index, info)
                if info.get("max_input_channels", 0) <= 0:
                    continue
                if index not in candidates:
                    candidates.append(index)
        except Exception as e:
            log.debug("[RECORDING] Could not build all-device fallback list: %s", e)
        return candidates
