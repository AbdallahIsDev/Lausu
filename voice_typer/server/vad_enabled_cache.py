"""VAD-enabled cache mixin: the ``vad_enabled`` property (5s TTL,
PERF-02), the ``on_config_changed`` refresh hook, and
``compute_vad_enabled``.

Split from ``voice_typer/server/vad_processor.py`` (create-first);
:class:`voice_typer.server.vad_processor.VadProcessor` composes it so
the historical import path keeps resolving.
"""

from __future__ import annotations

import logging
import time
from typing import Any

# Same logger object as the pre-split facade (see vad_calibration).
log = logging.getLogger("voice_typer.server.vad_processor")


class _VadEnabledCacheMixin:
    """Config-derived VAD gate with a TTL safety net."""

    # Host state owned by VadProcessor.__init__ (composed class).
    _config: Any
    _vad_enabled_cached: bool | None
    _vad_enabled_cache_ts: float
    # Class-level TTL constant defined on the composing VadProcessor.
    VAD_ENABLED_CACHE_TTL_S: float

    # ── VAD-enabled cache (VAD-GATE Task 4 + PERF-02) ────────────────

    @property
    def vad_enabled(self) -> bool:
        """Whether VAD should run based on current audio enhancement state.

        VAD-GATE (Task 4): ensures that if the user changes the audio
        preset to "Off" while the Recorder exists (or mid-session), the
        VAD gate reflects the current config state.

        PERF-02 (c-review): previously a dynamic @property that
        re-evaluated 6 ``getattr()`` calls on every access (read 3× per
        chunk at the ~31 Hz chunk cadence of rate-scaled ~32 ms blocks ≈
        560 getattr/sec for a value that only changes
        when the user toggles a Settings UI switch). Now returns a
        cached value refreshed by ``on_config_changed()`` (the explicit
        hook) with a 5-second TTL safety net so a missed config-change
        notification cannot permanently wedge the cache.
        """
        cached = self._vad_enabled_cached
        if cached is not None:
            # Safety-net refresh: if the explicit on_config_changed()
            now = time.perf_counter()
            if now - self._vad_enabled_cache_ts >= self.VAD_ENABLED_CACHE_TTL_S:
                # (item 2): reassign the narrowed local ``cached``
                cached = self.compute_vad_enabled(self._config)
                self._vad_enabled_cached = cached
                self._vad_enabled_cache_ts = now
            return cached
        # First access (cache cold): compute + cache.
        self._vad_enabled_cached = self.compute_vad_enabled(self._config)
        self._vad_enabled_cache_ts = time.perf_counter()
        return self._vad_enabled_cached

    def on_config_changed(self) -> None:
        """Refresh cached config-derived state after a config change.

                PERF-02 (c-review): called by ``app._rebuild_audio_processor``
                (wiring owned by Sub-Agent H in app.py) whenever any
                ``noise_filter_*``, ``audio_preset``, or
                ``noise_suppression_method`` config field changes. Refreshes
                the cached ``vad_enabled`` value so the next audio chunk's VAD
                gate decision uses the new config without re-running 6
                ``getattr()`` calls per access.

        when VAD transitions enabled → disabled mid-session
                (user selected the "Off" audio preset, or manually turned off
                every noise filter), the Silero model is unloaded so the ~2MB
                JIT graph isn't pinned in RAM for the rest of the process
                lifetime. Reload happens lazily via ``vad._load_model`` on the
                next VAD-enabled chunk.

                Safe to call from any thread (only reads ``self._config`` and
                writes two atomic Python attributes under the GIL). No-op if
                the processor has not been initialized yet.
        """
        was_enabled = self._vad_enabled_cached
        new_enabled = self.compute_vad_enabled(self._config)
        self._vad_enabled_cached = new_enabled
        self._vad_enabled_cache_ts = time.perf_counter()

        # release the Silero model when VAD transitions to
        if was_enabled and not new_enabled:
            try:
                from voice_typer.server.vad import unload as _vad_unload

                _vad_unload()
                log.info("[VAD] Silero model unloaded (VAD disabled mid-session)")
            except Exception:
                log.debug("[VAD] unload on config-change failed", exc_info=True)

    def compute_vad_enabled(self, config: Any) -> bool:
        """Whether voice-activity detection runs.

        Always True. VAD and the audio-enhancement filters are independent
        concerns: knowing when the user stopped talking (auto-stop after
        ``stop_on_silence_seconds``, silence warnings) is not an audio-quality
        feature, so switching off EQ/denoise must not silently disable it. The
        old VAD-GATE tied the two together, which meant picking the "Off"
        preset quietly removed auto-stop with no way to get it back.

        Cost is negligible: Silero is ~1-2 ms per audio chunk on CPU, against
        multi-second Whisper inference, so the original CPU rationale no longer
        holds. Users who never want auto-stop set ``stop_on_silence_seconds``
        to 0, which disables the trigger without disabling detection.

        ``use_silero_vad`` is intentionally NOT consulted here: it selects the
        Silero ML model vs RMS thresholds, not whether VAD runs.
        """
        return True
