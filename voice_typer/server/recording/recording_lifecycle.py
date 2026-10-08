"""Recording-session lifecycle bodies extracted from the ``Recorder`` class.

Owns :func:`start_recording` / :func:`stop_recording` /
:func:`discard_recording`; ``Recorder.start`` / ``stop`` / ``discard``
are 1-line delegators so existing call sites, subclass overrides, and
``inspect.getsource`` checks on the ``Recorder`` class keep working.
Tests patch this module's ``prepare_audio`` / ``refresh_vad_caches``
attributes, the owning-module seam (C-ARCH-2).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from voice_typer.server._audio_constants import (
    peak_amplitude,
    silence_percent,
)
from voice_typer.server._lazy_import import lazy_module

from . import (
    buffer as _buffer_mod,  # owning module of the secure-clear helpers (C-ARCH-2)
    recording_buffer,
)
from .format import prepare_audio
from .recording_start import start_recording  # noqa: F401  # re-exported seam (tests patch the facade)
from .vad_helpers import refresh_vad_caches  # noqa: F401  # call-time seam read by recording_start

if TYPE_CHECKING:
    from .recorder import Recorder

log = logging.getLogger("voice_typer.server.recording")

np = lazy_module("numpy")


# Session memo of the device index that last opened successfully.
# A fallback that worked once usually keeps working (e.g. a WASAPI
# exclusive-mode flake), so later starts try it first and skip the
# fail-then-fallback WARN pair. Process-lifetime only, never persisted:
# unplug/replug is detected by revalidating against enumeration.
_SESSION_LAST_GOOD_DEVICE: int | None = None


def _reset_session_device_memo() -> None:
    """Clear the session device memo (tests)."""
    global _SESSION_LAST_GOOD_DEVICE
    _SESSION_LAST_GOOD_DEVICE = None


def _prefer_session_last_good_device(recorder: Recorder, candidates: list[Any]) -> list[Any]:
    """Move the session-memoized device to the front of ``candidates``."""
    global _SESSION_LAST_GOOD_DEVICE
    cached = _SESSION_LAST_GOOD_DEVICE
    if cached is None or cached in candidates:
        return candidates
    try:
        current = recorder._devices._all_input_device_candidates()
    except Exception:
        return candidates
    if cached not in current:
        _SESSION_LAST_GOOD_DEVICE = None
        return candidates
    return [cached, *[c for c in candidates if c != cached]]


def _remember_session_device(device: Any) -> None:
    """Memoize a successfully opened device index (ints only)."""
    global _SESSION_LAST_GOOD_DEVICE
    _SESSION_LAST_GOOD_DEVICE = device if isinstance(device, int) else None


def _device_display_name(recorder: Recorder, device: Any) -> str:
    """Best-effort display name for a device index ("" when unknown).

    Only genuine string names count: anything else (test doubles,
    broken layers) means "unknown" so callers fail safe toward the
    loud fallback path instead of matching garbage.
    """
    try:
        info = recorder._devices._cached_device_info(device)
    except Exception:
        return ""
    if not isinstance(info, dict):
        return ""
    name = info.get("name", "")
    return name.strip() if isinstance(name, str) else ""


def discard_recording(recorder: Recorder) -> None:
    """Discard current recording without processing.

    Extracted verbatim from ``Recorder.discard`` ( split). The
        timeout constants ``_AUDIO_WORKER_DISCARD_JOIN_TIMEOUT_S`` and
        ``_EVENT_WORKER_DISCARD_JOIN_TIMEOUT_S`` are imported lazily from
        :mod:`.recorder` to avoid a circular import (recorder.py imports this
        module at the top of its class body).
    """
    # Lazy import: recorder.py is still loading when this module is first
    from voice_typer.server.recording.recorder import (
        _AUDIO_WORKER_DISCARD_JOIN_TIMEOUT_S,
        _EVENT_WORKER_DISCARD_JOIN_TIMEOUT_S,
    )

    recorder._recording_event.clear()
    # STREAM-FIX (Task 6): set _user_stop_pending before stream.stop() so
    recorder._user_stop_pending = True
    # 17-H-: increment stop_generation for symmetry with stop() so
    recorder._stop_generation += 1
    # guard _effective_sr reset with the lock so a concurrent
    with recorder._audio_pipeline._lock:
        recorder._effective_sr = recorder.config.sample_rate
        # reset ``_buffer_sr`` to ``None`` so the next session
        recorder._audio_pipeline._buffer_sr = None
    recorder._last_rms = 0.0
    recorder._silence_timer = 0.0
    recorder._silence_start_time = None
    recorder._silence_warning_count = 0
    recorder._silence_next_warning_wait = 10.0
    # securely zero cached audio arrays BEFORE reassignment
    recorder._session_state.secure_clear_caches(recorder)
    # 17-H-: drain callback + stop + close via _teardown_stream()
    recorder._teardown_stream()
    # stop the audio worker thread. drain=False because
    recorder._stop_audio_worker(timeout=_AUDIO_WORKER_DISCARD_JOIN_TIMEOUT_S, drain=False)
    # stop the IPC event worker with drain=False, the recording was
    with recorder._worker_lifecycle_lock:
        recorder._capture.stop_event_worker_body(recorder, timeout=_EVENT_WORKER_DISCARD_JOIN_TIMEOUT_S, drain=False)
    # Stop the device health checker thread (mirrors the event worker).
    recorder._stop_device_health_checker(timeout=0.0)
    with recorder._audio_pipeline._lock:
        # SEC-audit-008: defer buffer zeroing to background daemon
        recording_buffer._ensure_growable_buffer(recorder)
        _old_buffer = recorder._audio_pipeline._buffer
        # Contiguous storage: data lives in ONE ndarray, so "swap in a
        recorder._audio_pipeline._buffer = recording_buffer._fresh_recording_buffer_like(recorder, _old_buffer)
        # PERF: zero the running buffered-samples counter, the fresh
        recorder._audio_pipeline._total_buffered_samples = 0
        _buffer_mod._secure_clear_array_background(_old_buffer)


def stop_recording(recorder: Recorder) -> np.ndarray:
    """Stop recording and return the complete audio array.

        Body of :meth:`Recorder.stop`: extracted verbatim (with ``self.X``
    rewritten to ``recorder.X``) by the split to shrink the
        ~2748-LOC ``recorder.py`` god class. ``Recorder.stop`` becomes a
        1-line delegator so existing call sites, subclass overrides, and
        ``inspect.getsource`` checks that look for the method on the
        ``Recorder`` class continue to work. There is NO source-inspection
        test contract pinning ``Recorder.stop`` source (verified via
        ``rg "inspect.getsource.*Recorder\\.stop\\b" tests/``, the matches
        on ``IPCServer.stop`` are unrelated); the simple Option B delegate
        is sufficient.

        Step ordering (preserved verbatim):

          1. ``_recording_event`` early-out fast path (returns empty
             ``float32`` array when not recording).
          2. Clear ``_recording_event`` (the gate the audio callback and
             streaming thread poll).
          3. Increment ``_stop_generation`` (HOTKEY-CRASH: stale
             disconnect handlers from the audio callback bail out).
          4. Set ``_user_stop_pending = True`` (STREAM-FIX:
             ``_stream_finished_callback`` suppresses the false "Stream
             finished unexpectedly" warning during the intentional stop).
          5. ``_teardown_stream()``: 300 ms callback-drain poll, then
             ``stream.stop()`` + ``stream.close()`` (shared with
             ``discard_recording``; see the helper's docstring for the
    PERF- history).
          6. Clear ``_user_stop_pending`` (any future
             ``_stream_finished_callback`` is now a genuine disconnect).
          7. ``_stop_audio_worker(timeout=_AUDIO_WORKER_JOIN_TIMEOUT_S,
             drain=True)``: drain=True so the last few hundred ms of
             audio (chunks still in the ring buffer) end up in
             ``recorder._audio_pipeline._buffer`` and are concatenated below
    ().
          8. ``_stop_event_worker(timeout=_EVENT_WORKER_JOIN_TIMEOUT_S,
             drain=True)``: drains the IPC event queue.
          9. ``_stop_device_health_checker(timeout=0.0)``, fire-and-
             forget (the daemon exits on its next 30 s wait() return).
         10. Snapshot ``_buffer`` under ``_lock``: swap the deque for a
             fresh empty one + capture the chunk list + capture
             ``_buffer_sr`` local + ``_secure_clear_caches``; then
             release the lock and ``np.concatenate`` the captured chunks
             OUTSIDE the lock so the audio worker's append path (which
             acquires the same lock) is not blocked for the 50–300 ms
             concat duration.
         11. Compute audio stats (RMS via ``np.dot``, peak, silence
             percentage) and store them in ``_last_audio_stats`` so the
    transcription engine can reuse them ().
         12. ``_prepare_audio(audio, effective_sr)``: H15: resample from
             scratch (no cache) for the full audio.
         13. ``log.info`` the stop summary (duration, sr, samples, RMS,
             peak, silence_pct, stream/concat/resample/total ms); near-
             silence warning when ``rms < 0.001``.

        The empty-buffer fast path zeros the cached audio arrays
        (``_secure_clear_caches``), resets ``_chunk_count = 0``, and
    returns an empty ``float32`` array,  secure-clear
        contract.

        Critical: ``_buffer_sr`` (the actual rate of the audio in
        ``recorder._audio_pipeline._buffer``) is captured into a local BEFORE
        ``_secure_clear_caches`` resets it to ``None``. The local is the
        authoritative source rate for the snapshotted audio, the chunks
        in ``_captured_chunks`` were appended at this rate by
        ``_process_audio_chunk``. Using ``_effective_sr`` here (the
        device's native rate) would cause ``_prepare_audio`` to resample
        the already-16 kHz audio a second time (chipmunk voice).
    """
    # Lazy import: ``recorder.py`` is still loading when this module
    from voice_typer.server.recording.recorder import (
        _AUDIO_WORKER_JOIN_TIMEOUT_S,
        _EVENT_WORKER_JOIN_TIMEOUT_S,
    )

    # Fast-path ONLY when no worker refs exist. A
    if (
        not recorder._recording_event.is_set()
        and recorder._worker_thread is None
        and recorder._event_worker_thread is None
    ):
        return np.array([], dtype=np.float32)

    stop_started = time.perf_counter()
    recorder._recording_event.clear()

    # HOTKEY-CRASH: increment stop_generation so any stale disconnect
    recorder._stop_generation += 1

    # STREAM-FIX: mark that we're about to call stream.stop()
    recorder._user_stop_pending = True

    # 17-H-: drain callback + stop + close via _teardown_stream()
    recorder._teardown_stream()
    # STREAM-FIX: clear the user-stop-pending flag now
    recorder._user_stop_pending = False
    stream_ms = (time.perf_counter() - stop_started) * 1000

    # stop the audio worker thread. drain=True so the
    recorder._stop_audio_worker(timeout=_AUDIO_WORKER_JOIN_TIMEOUT_S, drain=True)

    # cut the worst-case stop() latency from ~5.8s to ~2.4s
    with recorder._worker_lifecycle_lock:
        recorder._capture.stop_event_worker_body(recorder, timeout=_EVENT_WORKER_JOIN_TIMEOUT_S, drain=True)

    # device health checker fire-and-forget. Pass timeout=0.0
    recorder._stop_device_health_checker(timeout=0.0)

    # snapshot the buffer under the lock, then release the lock BEFORE
    concat_started = time.perf_counter()
    with recorder._audio_pipeline._lock:
        if not recorder._audio_pipeline._buffer:
            # securely zero cached audio arrays BEFORE
            recorder._session_state.secure_clear_caches(recorder)
            recorder._audio_pipeline._chunk_count = 0
            # PERF: zero the running buffered-samples counter alongside
            recorder._audio_pipeline._total_buffered_samples = 0
            # idle-recording gate. Return to the 12 s idle
            _mic_watcher = recorder._devices._mic_watcher
            if _mic_watcher is not None:
                _mic_watcher.set_idle(True)
            return np.array([], dtype=np.float32)
        # Non-empty: normalize legacy containers (hot-swap deque / test
        recording_buffer._ensure_growable_buffer(recorder)
        _old_buffer = recorder._audio_pipeline._buffer
        recorder._audio_pipeline._buffer = recording_buffer._fresh_recording_buffer_like(recorder, _old_buffer)
        # PERF: zero the running buffered-samples counter, the fresh
        recorder._audio_pipeline._total_buffered_samples = 0
        # Critical: capture ``_buffer_sr`` into a local
        _captured_buffer_sr = recorder._audio_pipeline._buffer_sr
        # securely zero cached audio arrays BEFORE
        recorder._session_state.secure_clear_caches(recorder)
    # materialize the contiguous result OUTSIDE the lock so the
    audio = _old_buffer.export_copy()
    concat_ms = (time.perf_counter() - concat_started) * 1000

    # SEC-audit-008 (race fix): enqueue the OLD storage for background
    _buffer_mod._secure_clear_array_background(_old_buffer)

    # Log audio statistics for diagnostics
    effective_sr = _captured_buffer_sr if _captured_buffer_sr is not None else recorder._effective_sr

    # Pipeline ``prepare_audio`` with the stats computation below.
    resample_started = time.perf_counter()
    _resample_result: dict[str, Any] = {"audio": None, "exc": None}

    def _run_prepare_audio() -> None:
        try:
            _resample_result["audio"] = prepare_audio(recorder, audio, effective_sr)
        except BaseException as exc:  # noqa: BLE001, re-raised after join
            _resample_result["exc"] = exc

    _resample_thread = threading.Thread(
        target=_run_prepare_audio,
        name="stop-prepare-audio",
        daemon=True,
    )
    _resample_thread.start()

    duration = len(audio) / effective_sr if len(audio) > 0 else 0
    # initialize ``rms``/``peak``/``silence_pct`` BEFORE
    rms: float = 0.0
    peak: float = 0.0
    silence_pct: float = 0.0
    if len(audio) > 0:
        # AUDIO-NP: use np.dot for RMS in stop() too
        if audio.size:
            flat = audio.reshape(-1)
            rms = float(np.sqrt(np.dot(flat, flat) / flat.size))
            # PERF: allocation-free peak + silence stats (shared helpers).
            peak = peak_amplitude(flat)
            silence_pct = silence_percent(flat)
        else:
            peak = 0.0
            rms = 0.0
            silence_pct = 0.0
        recorder._last_rms = rms
        # store the full-recording stats so the
        recorder._last_audio_stats = (rms, peak, silence_pct)
    else:
        recorder._last_rms = 0.0
        recorder._last_audio_stats = (0.0, 0.0, 0.0)
        log.warning("[RECORDING] No audio data captured!")

    # Wait for the resample thread to complete and propagate any
    _resample_thread.join()
    if _resample_result["exc"] is not None:
        raise _resample_result["exc"]
    audio = _resample_result["audio"]
    resample_ms = (time.perf_counter() - resample_started) * 1000

    # AUDIO-PROC: post-capture spectral noise reduction (offline,

    total_ms = (time.perf_counter() - stop_started) * 1000
    if len(audio) > 0:
        log.info(
            "[RECORDING] Audio stopped: duration=%.1fs, sr=%d, samples=%d | "
            "RMS=%.6f, peak=%.6f, silence=%.1f%% | "
            "stream=%.0fms, concat=%.0fms, resample=%.0fms, total=%.0fms",
            duration,
            effective_sr,
            len(audio),
            rms,
            peak,
            silence_pct,
            stream_ms,
            concat_ms,
            resample_ms,
            total_ms,
        )
        if rms < 0.001:
            log.warning(
                "[RECORDING] Near-silence detected! (RMS=%.6f) Microphone may not be capturing audio.",
                rms,
            )
    else:
        # Warning already emitted above when len(audio) == 0
        pass

    # idle-recording gate. Return to the 12 s idle cadence
    _mic_watcher = recorder._devices._mic_watcher
    if _mic_watcher is not None:
        _mic_watcher.set_idle(True)

    return audio
