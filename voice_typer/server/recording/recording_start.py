"""Recording start-session body extracted from ``recording_lifecycle``.

Create-first split: the facade re-exports :func:`start_recording`, so
existing call sites and ``inspect.getsource`` checks keep resolving
unchanged. Facade-owned names the facade's tests monkeypatch
(``refresh_vad_caches``) and the session-memo helpers are resolved
through :func:`_facade` at call time.
"""

from __future__ import annotations

import collections
import contextlib
import logging
import threading
from typing import TYPE_CHECKING, Any

from voice_typer.server._audio_constants import scaled_audio_blocksize
from voice_typer.server._lazy_import import lazy_module

if TYPE_CHECKING:
    from .recorder import Recorder

log = logging.getLogger("voice_typer.server.recording")

np = lazy_module("numpy")


def _facade():
    """Resolve the ``recording_lifecycle`` facade at call time.

    Tests monkeypatch ``recording_lifecycle.refresh_vad_caches``; a
    binding captured at import time here would ignore that seam, and
    the session-memo helpers must keep mutating the facade's global.
    """
    from . import recording_lifecycle

    return recording_lifecycle


def start_recording(recorder: Recorder) -> None:
    """Body of :meth:`Recorder.start` (after the ``_start_lock`` permission-gate block).

    Extracted from :mod:`.recorder` to shrink the
        3772-LOC ``recorder.py`` god class. The ``with self._start_lock:``
        block (containing the recording-event check + microphone-permission
        pre-flight) stays on ``Recorder.start`` so the source-inspection
        test (``tests/test_recording.py::TestRec5StartLock``) continues to
        pin the lock contract.

        This function runs WITHOUT holding ``_start_lock``, it is called
        after ``Recorder.start`` releases the lock. The lock contract is
        that ``start()`` and ``discard()`` cannot both pass the
        ``_recording_event.is_set()`` check at the same time, which the
        lock guarantees by serializing the gate.

    reset ALL per-session state here, not just the buffer.
        Previously some flags (_max_duration_warning_sent,
        _silence_warning_sent, etc.) persisted across recordings,
        causing stale state to suppress warnings on the next session.

    (revised): The dead ``_silence_warning_sent`` and
        ``_max_duration_warning_sent`` boolean flags have been REMOVED.
        They were declared and reset here but NEVER read in any
        conditional, the actual silence-warning state machine uses
        the integer counter ``_silence_warning_count`` (which IS read
        at recording.py:1109). The dead flags were misleading
        maintainers into thinking warning deduplication existed when
    it didn't: see FORENSIC_REVIEW_COMPLETE.md →

        SEC-audit-008: ``_secure_clear_array`` is now actually used
        here to zero cached audio arrays (``_cached_resampled`` and
        ``_cached_no_resample_arr``) before they're dropped. This
        prevents forensic recovery of audio data from process memory
        between sessions.

        CRITICAL, DO NOT RESTRUCTURE (2026-07-20)
        ========================================
        The device-enumeration block below (``last_error``,
        ``selected_device``, ``effective_sr``, the ``for candidate in
        candidates`` loop, the fallback loop, and the
        ``if recorder._stream is None:`` check) MUST stay at this
        function's body scope. OUTSIDE the ``callback`` closure built
        by ``recorder._stream_lifecycle.build_audio_callback(recorder)``
        above. A previous
        merge accidentally nested this block INSIDE the ``def
        callback()`` closure, which made ``last_error`` a local of
        ``callback`` instead of ``start()``, raising
        ``UnboundLocalError`` on every recording start.

        The device-loop bodies live on :class:`.stream_lifecycle.StreamLifecycle`
        (``open_stream_for_candidates`` / ``open_stream_fallback``, invoked
        from this function's scope via ``recorder._stream_lifecycle``, OUTSIDE
        the callback closure), so the
        structural contract above is preserved.

        DO NOT move device enumeration inside the callback closure.
        DO NOT re-add ``set_thread_registry``: it was merge damage.
    """
    # Lazy import: ``recorder.py`` is still loading when this module

    # SEC-audit-008: securely zero cached
    recorder._secure_clear_session_caches()

    # per-session state reset () ──
    recorder._session_state.reset_session_state(recorder)

    max_rec = recorder._session_state.cache_session_config(recorder)

    device = recorder._devices._resolve_device()
    candidates = recorder._devices._same_physical_microphone_candidates(device)
    candidates = _facade()._prefer_session_last_good_device(recorder, candidates)

    # build the PortAudio callback closure () ──
    callback = recorder._stream_lifecycle.build_audio_callback(recorder)

    # CRITICAL, DO NOT RESTRUCTURE (2026-07-20)
    last_error: Exception | None = None
    selected_device: Any = None
    effective_sr: int = recorder.config.sample_rate
    used_fallback = False

    selected_device, effective_sr, last_error = recorder._stream_lifecycle.open_stream_for_candidates(
        recorder, candidates, callback, effective_sr, last_error
    )

    # If all same-name candidates failed, try ALL available input devices
    if recorder._stream_lifecycle._stream is None and not used_fallback:
        selected_device, effective_sr, used_fallback, last_error = recorder._stream_lifecycle.open_stream_fallback(
            recorder, candidates, callback, effective_sr, last_error
        )

    if recorder._stream_lifecycle._stream is None:
        _facade()._remember_session_device(None)
        if last_error is not None:
            raise last_error
        raise RuntimeError("No input device could be opened")

    _facade()._remember_session_device(selected_device)

    recorder._session_state.resize_buffers_for_sample_rate(recorder, effective_sr, max_rec)

    # Scale the SPSC ring buffer to ~2s of headroom at the
    sizing_sr = effective_sr if effective_sr > 0 else recorder.config.sample_rate
    if sizing_sr > 0:
        sizing_blocksize = scaled_audio_blocksize(sizing_sr)
        new_ring_capacity = max(64, int(sizing_sr / sizing_blocksize * 2.0))
        for _payload in recorder._ring_buffer:
            _arr = _payload[0] if isinstance(_payload, tuple) else _payload
            if isinstance(_arr, np.ndarray):
                _arr.fill(0)
        recorder._ring_buffer = collections.deque(maxlen=new_ring_capacity)

    if selected_device != device and isinstance(selected_device, int):
        # Session-local fallback ONLY: the opened stream uses the
        if device is None and not used_fallback:
            log.debug(
                "[RECORDING] System Default resolved to device [%s] for this session",
                selected_device,
            )
        else:
            # Name the failure honestly: the device usually EXISTS (e.g.
            # System Default resolving to a Realtek WASAPI endpoint) but
            # its open call failed (driver/exclusive-mode/format). Saying
            # "unavailable" alone sends users hunting for an unplugged
            # mic that is sitting right there.
            _label = "System Default" if device is None else device
            _reason = str(last_error)[:160] if last_error is not None else "unknown error"
            _fallback_name = _facade()._device_display_name(recorder, selected_device)
            _tried_names = {
                _facade()._device_display_name(recorder, candidate).lower()
                for candidate in candidates
            } - {""}
            if _fallback_name and _fallback_name.lower() in _tried_names:
                # Same physical mic on another host API (WASAPI flake ->
                # MME): routine, silent. No tray toast; a popup reading
                # like breakage would train users to fear a working app.
                log.info(
                    "[RECORDING] Selected microphone [%s] failed to open (%s); using same "
                    "microphone via device [%s] for this session (saved selection unchanged)",
                    _label,
                    _reason,
                    selected_device,
                )
            else:
                log.warning(
                    "[RECORDING] Selected microphone [%s] failed to open (%s); using device [%s] "
                    "for this session (saved selection unchanged)",
                    _label,
                    _reason,
                    selected_device,
                )
                with contextlib.suppress(Exception):
                    from voice_typer.server import event_bus as _event_bus
                    from voice_typer.server.branding import APP_NAME as _APP_NAME

                    _event_bus.publish(
                        {
                            "type": "notification",
                            "data": {
                                "title": _APP_NAME,
                                "message": (
                                    f"Selected microphone '{_label}' failed to open; "
                                    f"using device [{selected_device}] for this session."
                                ),
                                "duration_ms": 10000,
                            },
                        }
                    )

    recorder._recording_event.set()

    # inside ``AudioCallbackDispatcher.audio_worker_loop`` (capture.py)

    target_sr = recorder.config.sample_rate
    # The mutable resampler state lives on the .resampling submodule;
    from voice_typer.server.recording import resampling as _recording_resampling

    if (
        effective_sr != target_sr
        and _recording_resampling._resample_poly is None
        and _recording_resampling._resample_poly_error is None
    ):
        # Skip the synchronous warm-up when the scipy preloader daemon
        _preloader = getattr(recorder, "_scipy_preloader_thread", None)
        if isinstance(_preloader, threading.Thread) and _preloader.is_alive():
            log.debug("[RECORDING] scipy preloader in flight, resampler warm-up left to the background thread")
        else:
            # Warm up synchronously when no background preloader is
            recorder.warm_up_resampler()

    # best-effort retune of the AudioProcessor's filter chain
    try:
        from .disconnect_handler import retune_audio_processor

        retune_audio_processor(
            recorder._audio_processor,
            effective_sr,
            recorder.config,
            context="on start",
        )
    except Exception:
        log.warning(
            "[RECORDING] retune_audio_processor failed on start, per-chunk resample will run on the worker thread",
            exc_info=True,
        )

    # refresh the per-chunk VAD property cache now that
    _facade().refresh_vad_caches(recorder)

    # Start the audio worker thread AFTER ``_recording_event.set()``
    try:
        recorder._start_audio_worker()
        audio_worker_started = True
    except BaseException:
        audio_worker_started = False
        recorder._stop_generation += 1
        recorder._recording_event.clear()
        with contextlib.suppress(Exception):
            recorder._teardown_stream()
        raise

    # Start the IPC event worker thread AFTER the audio worker
    try:
        with recorder._worker_lifecycle_lock:
            recorder._capture.start_event_worker_body(recorder)
    except BaseException:
        recorder._stop_generation += 1
        recorder._recording_event.clear()
        with contextlib.suppress(Exception):
            recorder._teardown_stream()
        if audio_worker_started:
            with contextlib.suppress(Exception):
                recorder._stop_audio_worker(timeout=0.5, drain=False)
        raise

    # Start the device health checker thread (off the audio
    recorder._devices._start_device_health_checker()

    # Wire the idle-recording gate. ``Recorder.start`` is the
    _mic_watcher = recorder._devices._mic_watcher
    if _mic_watcher is not None:
        _mic_watcher.set_idle(False)


