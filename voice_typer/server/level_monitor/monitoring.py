"""Level-monitor open/stop and RMS sampling."""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import TYPE_CHECKING

import numpy as np

from voice_typer.server._audio_constants import (
    WHISPER_SAMPLE_RATE,
    scaled_audio_blocksize,
)

from ._state import _state
from .mic_level_push import (  # noqa: F401  # facade re-export
    _ensure_mic_level_worker_running,
    _mic_level_worker_loop,
    _push_mic_level,
    _stop_mic_level_worker,
)
from .monitoring_queries import (  # noqa: F401  # facade re-export
    get_level,
    get_level_diagnostics,
    is_monitoring,
    update_level_processor,
)

if TYPE_CHECKING:
    pass

log = logging.getLogger("voice_typer.server.level_monitor")


def _emit_device_lost(source: str) -> None:
    """Publish a ``device_lost`` IPC event (idempotent via ``_device_lost_emitted``)."""
    if _state._device_lost_emitted:
        return
    _state._device_lost_emitted = True
    try:
        from voice_typer.server import event_bus

        event_bus.publish({"type": "device_lost", "data": {"source": source}})
        log.info("[LEVEL-MON] device_lost event emitted (source=%s)", source)
    except Exception:
        log.debug("[LEVEL-MON] Failed to publish device_lost event", exc_info=True)


def _make_stream_finished_guard(stream_cell: dict[str, object]):
    """Build a PortAudio ``finished_callback`` bound to the stream in *stream_cell*."""

    def _on_stream_finished() -> None:
        with _state._monitor_lock:
            current = _state._monitor_stream
            active = _state._monitor_active
        if stream_cell.get("stream") is not current or not active:
            # Intentional stop / replaced by a newer stream, not a loss.
            log.debug("[LEVEL-MON] finished callback ignored (stream replaced or intentionally stopped)")
            return
        _handle_dead_stream("stream_finished")

    return _on_stream_finished


# An OS-side mic reconfigure (format/effects change, transient driver
# restart) kills the PortAudio stream while the device is still there:
# a reopen a second later succeeds. Linux suspend often shows up the
# other way (starved stream of exact zeros instead of a finished
# callback). Both signatures funnel through one bounded retry; only a
# provably-gone device, exhausted retries, or a reopen loop that keeps
# yielding silence becomes a device_lost banner (C-MIC-16: banners fire
# on real unavailability, never on transient blips).
_STREAM_REOPEN_ATTEMPTS = 3
_STREAM_REOPEN_DELAY_SEC = 1.0
_STREAM_RECOVERY_MAX_EPISODES = 3


def _handle_dead_stream(source: str) -> None:
    """Park a dead monitor stream and retry the open (idempotent).

    No-op when already inactive. Otherwise marks inactive, mints a
    recovery token, and spawns the bounded retry on a daemon thread
    (the PortAudio callback thread must return fast). Episodes cap
    reopen loops whose fresh streams keep yielding only silence.
    """
    with _state._monitor_lock:
        if not _state._monitor_active:
            return
        _state._monitor_active = False
        _state._stream_recovery_episodes += 1
        if _state._stream_recovery_episodes > _STREAM_RECOVERY_MAX_EPISODES:
            _state._stream_recovery_token = None
            looped = True
            mic_id = _state._monitor_mic_id
        else:
            # Recovery token: a later stop_monitoring / successful start
            # clears it, which aborts the retry below. Our own failed
            # reopen attempts never touch it, so only real user action
            # (or a concurrent recovery) can cancel the retry.
            token = object()
            _state._stream_recovery_token = token
            looped = False
            mic_id = _state._monitor_mic_id
    if looped:
        log.warning("[LEVEL-MON] InputStream finished - device disconnected")
        _emit_device_lost(source)
        return
    log.info("[LEVEL-MON] InputStream finished unexpectedly, retrying open")
    retry = threading.Thread(
        target=_recover_stream_reopen,
        args=(mic_id, token, source),
        daemon=True,  # RACE-008: fire-and-forget retry must never block exit
        name="level-monitor-stream-retry",
    )
    retry.start()


def _monitor_device_present(mic_id: str | None) -> bool:
    """Fail-open presence check: only a provably-absent device skips the retry."""
    if mic_id is None:
        return True
    try:
        from voice_typer.server.server_platform import find_microphone_by_id

        return find_microphone_by_id(str(mic_id)) is not None
    except Exception:
        return True


def _recover_stream_reopen(mic_id: str | None, token: object, source: str) -> None:
    """Reopen a dead monitor stream; emit device_lost only when truly gone."""
    import time as _time

    for attempt in range(1, _STREAM_REOPEN_ATTEMPTS + 1):
        _time.sleep(_STREAM_REOPEN_DELAY_SEC)
        with _state._monitor_lock:
            if _state._stream_recovery_token is not token or _state._monitor_active:
                return
        if not _monitor_device_present(mic_id):
            break
        if start_monitoring(mic_id=mic_id).get("success"):
            log.info("[LEVEL-MON] Stream recovered after OS-side restart (attempt %d)", attempt)
            return
    with _state._monitor_lock:
        if _state._stream_recovery_token is not token or _state._monitor_active:
            return
        _state._stream_recovery_token = None
    log.warning("[LEVEL-MON] InputStream finished - device disconnected")
    _emit_device_lost(source)


def _level_stream_finished() -> None:
    """Legacy unguarded finished callback, device disconnected mid-stream."""
    with _state._monitor_lock:
        _state._monitor_active = False
    log.warning("[LEVEL-MON] InputStream finished - device disconnected")
    _emit_device_lost("stream_finished")


def start_monitoring(mic_id: str | None = None) -> dict:
    """Start continuous real-time audio level monitoring.

    Returns:
    """
    import sounddevice as sd

    with _state._monitor_lock:
        # Already running on the same device, no-op
        if _state._monitor_active and _state._monitor_mic_id == mic_id:
            return {
                "success": True,
                "message": "Already monitoring",
                "sample_rate": _state._monitor_sample_rate,
            }

        # Already running on a DIFFERENT device, restart
        if _state._monitor_active:
            old_stream = _state._monitor_stream
            _state._monitor_stream = None
            _state._monitor_active = False
            _state._monitor_level = 0.0
            _state._monitor_peak = 0.0
            _state._monitor_mic_id = None
            # Reset the OLD processor's filter state before closing the
            old_processor = _state._level_processor
            if old_processor is not None:
                with contextlib.suppress(Exception):
                    old_processor.reset()
            # Close old stream outside the lock to avoid blocking
        else:
            old_stream = None
        # Mark this open attempt so a racing switch or stop is detected at commit.
        _state._monitor_epoch += 1
        opening_epoch = _state._monitor_epoch

    # Close old stream (if any) without holding the lock.
    if old_stream is not None:
        try:
            old_stream.stop()
            old_stream.close()
        except Exception as exc:
            log.debug("[LEVEL-MON] Close old stream: %s", exc)

    # Resolve + query + open WITHOUT the lock so get_level() polls stay
    # responsive while a device switch runs through its slow path.
    device = None
    if mic_id is not None:
        try:
            from voice_typer.server.server_platform import (
                resolve_mic_id_to_device_index,
            )

            device = resolve_mic_id_to_device_index(mic_id)
        except Exception:
            log.debug(
                "[LEVEL-MON] mic id %r resolution failed; using system default",
                mic_id,
                exc_info=True,
            )
            device = None

    try:
        dev_info_raw = sd.query_devices(kind="input") if device is None else sd.query_devices(device)
        native_rate = int(dev_info_raw["default_samplerate"]) if isinstance(dev_info_raw, dict) else WHISPER_SAMPLE_RATE
    except Exception:
        native_rate = WHISPER_SAMPLE_RATE

    # Scale the block size with the device native sample rate so
    blocksize = scaled_audio_blocksize(native_rate)

    # Cell for the not-yet-created InputStream: the finished-callback
    stream_cell: dict[str, object] = {}

    def callback(indata, frames, time_info, status):
        #  (c-review PERF-03): the PortAudio callback runs
        try:
            _state._level_ring_buffer.append((indata.copy(), status))
        except Exception:
            # defensive. Don't let a callback error kill the stream.
            log.debug("[LEVEL-MON] ring buffer append failed", exc_info=True)
            return
        if len(_state._level_ring_buffer) >= _state._LEVEL_RING_BUFFER_CAPACITY:
            # Ring buffer full, worker can't keep up. Drop the
            _state._dropped_level_chunks += 1
            # Emit a one-shot WARNING on the first drop of a
            if not _state._first_drop_warning_emitted:
                _state._first_drop_warning_emitted = True
                log.warning(
                    "[LEVEL-MON] ring buffer full, dropped audio chunk "
                    "(worker thread can't keep up with the PortAudio "
                    "callback rate; consider disabling RNNoise or "
                    "reducing the filter chain cost)",
                )
        _state._level_worker_wake_event.set()

    stream = None
    try:
        stream = sd.InputStream(
            samplerate=native_rate,
            channels=1,
            dtype=np.float32,
            device=device,
            callback=callback,
            finished_callback=_make_stream_finished_guard(stream_cell),
            blocksize=blocksize,
        )
        stream.start()
        stream_cell["stream"] = stream
    except Exception as exc:
        # Close a partially started stream without the lock.
        with contextlib.suppress(Exception):
            if stream is not None:
                stream.stop()
                stream.close()
        with _state._monitor_lock:
            if _state._monitor_epoch != opening_epoch:
                return {
                    "success": _state._monitor_active,
                    "message": "Monitoring active" if _state._monitor_active else str(exc),
                    "sample_rate": _state._monitor_sample_rate,
                }
        log.warning("[LEVEL-MON] Failed to start monitoring: %s", exc)
        return {"success": False, "message": str(exc), "sample_rate": native_rate}

    # Commit the opened stream under the lock; a racing switch or stop
    # bumps the epoch and wins, our stream is closed instead of reviving.
    with _state._monitor_lock:
        if _state._monitor_epoch != opening_epoch or _state._monitor_active:
            raced = True
            config_snapshot = None
        else:
            raced = False
            _state._monitor_sample_rate = native_rate
            _state._monitor_level = 0.0
            _state._monitor_peak = 0.0
            _state._monitor_stream = stream
            _state._monitor_active = True
            _state._monitor_mic_id = mic_id
            _state._device_lost_emitted = False
            _state._stream_recovery_token = None
            # Fresh stream, fresh silence assessment. Episodes are NOT
            # reset here: a reopen loop that keeps yielding silence must
            # keep counting toward the cap (reset comes from live audio
            # in the worker, or from an explicit user stop below).
            _state._consecutive_zero_chunks = 0
            # seed the idle-timeout poll timestamp so the worker
            _state._last_get_level_poll_ts = time.monotonic()
            config_snapshot = _state._level_processor_config

    if raced:
        with contextlib.suppress(Exception):
            stream.stop()
            stream.close()
        with _state._monitor_lock:
            active = _state._monitor_active
            committed_rate = _state._monitor_sample_rate
        if active:
            return {"success": True, "message": "Already monitoring", "sample_rate": committed_rate}
        return {"success": False, "message": "Monitoring stopped during open", "sample_rate": committed_rate}

    # A worker-spawn failure after the stream was committed would leave an
    # active stream with nobody pushing levels: close it and report the failure.
    try:
        _ensure_mic_level_worker_running()

        #  (c-review PERF-03): start the dedicated worker
        from .worker import _ensure_level_worker_running

        _ensure_level_worker_running()
    except Exception as exc:
        log.exception("[LEVEL-MON] Level worker start failed after stream open: %s", exc)
        with contextlib.suppress(Exception):
            stream.stop()
            stream.close()
        with _state._monitor_lock:
            if _state._monitor_stream is stream:
                _state._monitor_stream = None
                _state._monitor_active = False
        return {
            "success": False,
            "message": f"level worker start failed: {exc}",
            "sample_rate": native_rate,
        }

    log.info(
        "[LEVEL-MON] Monitoring started: mic=%s | sr=%d",
        mic_id or "default",
        native_rate,
    )

    # Rebuild the level processor at the new native rate. Must happen
    if config_snapshot is not None:
        try:
            update_level_processor(config_snapshot)
        except Exception:
            log.debug(
                "[LEVEL-MON] post-restart update_level_processor failed",
                exc_info=True,
            )

    return {"success": True, "message": "Monitoring active", "sample_rate": native_rate}


def stop_monitoring() -> dict:
    """Stop the continuous level monitor stream.

    A running mic test HOLDS the stream: navigating away stops the
    meter, never the recording. The test owns the mic until it
    auto-stops/finalizes; the idle timeout releases it after.

    Returns:
    """
    with _state._monitor_lock:
        if _state._test_mode:
            return {"success": True, "message": "Test running, stream held"}
        # A user stop aborts any in-flight stream recovery and wipes
        # the episode count (next start is a fresh slate).
        _state._stream_recovery_token = None
        _state._stream_recovery_episodes = 0
    # Cancel any active test first.
    from .test_recording import _cancel_test_locked
    from .worker import _stop_level_worker

    _cancel_test_locked()
    _stop_mic_level_worker()

    already_stopped = False
    stream = None
    with _state._monitor_lock:
        # Bump on every stop, even a no-op: a stop landing inside a slow
        # open's window must make that open yield instead of reviving.
        _state._monitor_epoch += 1
        if not _state._monitor_active:
            #  (c-review PERF-03): monitoring was already
            already_stopped = True
        else:
            _state._monitor_active = False
            stream = _state._monitor_stream
            _state._monitor_stream = None
            _state._monitor_level = 0.0
            _state._monitor_peak = 0.0
            _state._monitor_mic_id = None

    if already_stopped:
        #  (c-review PERF-03): stop the (possibly leaked) worker
        _stop_level_worker()
        return {"success": True, "message": "Not monitoring"}

    if stream is not None:
        try:
            stream.stop()
            stream.close()
        except Exception as exc:
            log.debug("[LEVEL-MON] Stream close: %s", exc)

    # Reset the per-session audio processor filter state so the IIR
    if _state._level_processor is not None:
        with contextlib.suppress(Exception):
            _state._level_processor.reset()

    #  (c-review PERF-03): now that the stream is closed (no
    _stop_level_worker()

    log.info("[LEVEL-MON] Monitoring stopped")
    return {"success": True, "message": "Monitoring stopped"}


def _idle_timeout_auto_stop() -> bool:
    """auto-stop the monitor stream if the IPC idle-timeout has fired."""
    if not _state._monitor_active:
        return False
    if _state._test_mode:
        # A recording test holds the mic regardless of poll idle.
        return False
    # Polls ONLY. Push timestamps self-perpetuate (every push refreshes
    # the clock, so counting them kept the mic open 24/7 and defeated
    # the timeout outright). Consumers that need the stream keep it
    # alive by polling (the mic page heartbeats while visible).
    last_activity_ts = _state._last_get_level_poll_ts
    if last_activity_ts <= 0.0:
        # No poll has ever been recorded, don't auto-stop yet
        return False
    now = time.monotonic()
    if (now - last_activity_ts) < _state._LEVEL_IDLE_TIMEOUT_SEC:
        return False

    # Idle timeout has fired. Close the stream.
    log.info(
        "[LEVEL-MON] idle-timeout: auto-stopping monitor stream (no get_level poll in %.1fs)",
        _state._LEVEL_IDLE_TIMEOUT_SEC,
    )
    stream = None
    with _state._monitor_lock:
        if not _state._monitor_active:
            return False
        _state._monitor_active = False
        stream = _state._monitor_stream
        _state._monitor_stream = None
        _state._monitor_level = 0.0
        _state._monitor_peak = 0.0
        _state._monitor_mic_id = None
        _state._monitor_epoch += 1
        # Reset BOTH idle-timestamp clocks so the next
        _state._last_get_level_poll_ts = 0.0
        _state._mic_level_last_push_ts = 0.0

    if stream is not None:
        try:
            stream.stop()
            stream.close()
        except Exception as exc:
            log.debug("[LEVEL-MON] idle-timeout stream close: %s", exc)

    # Stop the mic_level push-event worker too (no more levels to push).
    _stop_mic_level_worker()
    return True
