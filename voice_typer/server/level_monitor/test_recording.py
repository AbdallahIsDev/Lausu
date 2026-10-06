"""Microphone test-recording helpers.

Split (create-first, every moved name re-exported here so the historical
import path keeps resolving): :mod:`.test_recording_files` (mic-test WAV
disk transport: recordings dir, persist, TTL expiry, slices) and
:mod:`.test_recording_lifecycle` (arm/start/cancel/auto-stop). This
module keeps the quality-band constants and the stop/finalize path.
"""

from __future__ import annotations

import io
import logging
import types
import wave
from typing import TYPE_CHECKING

import numpy as np

from voice_typer.server._audio_constants import AUDIO_LOW_VOLUME_RMS, AUDIO_SILENCE_RMS
from voice_typer.server.duration import format_duration

from ._state import _state
from .test_recording_files import (  # noqa: F401  # facade re-export
    _TEST_RECORDINGS_DIRNAME,
    MIC_TEST_RECORDING_TTL_SEC,
    _delete_expired_recordings,
    _delete_test_recording_paths,
    _purge_test_recordings,
    _remove_recordings_dir_if_empty,
    _schedule_test_recording_expiry,
    _test_recording_expiry_timers,
    _test_recordings_dir,
    _write_test_wav,
    read_test_recording_slice,
)
from .test_recording_lifecycle import (  # noqa: F401  # facade re-export
    _begin_test_locked,
    _cancel_test_locked,
    _do_auto_stop_test,
    _reset_test_chunks,
    _secure_clear_test_chunks,
    cancel_test_recording,
    is_test_active,
    start_test_recording,
    update_test_filters,
)

if TYPE_CHECKING:
    from typing import Any

log = logging.getLogger("voice_typer.server.level_monitor")


# Volume bands share the dictation path's boundaries (see
MIC_TEST_GOOD_VOLUME_RMS = AUDIO_LOW_VOLUME_RMS
MIC_TEST_VERY_LOW_VOLUME_RMS = AUDIO_SILENCE_RMS

# Background-noise bands apply to the noise FLOOR (the quietest
_MIC_TEST_NOISE_LOW_RMS = 0.005
_MIC_TEST_NOISE_HIGH_RMS = 0.05

# Voice presence: a peak above this fraction of full scale in a block
_MIC_TEST_VOICE_PEAK = 0.05
# ... but one loud transient (click/pop) in an otherwise silent test
_MIC_TEST_VOICE_MAX_SILENCE_RATIO = 0.95
_MIC_TEST_VOICE_MIN_NON_SILENT_BLOCKS = 3


def stop_test_recording() -> dict:
    """Stop the test recording and return the captured audio as base64 WAV.

    Returns:
    """
    # Cancel the auto-stop timer under ``_monitor_lock``: the
    with _state._monitor_lock:
        timer = _state._test_auto_stop_timer
        if timer is not None:
            timer.cancel()
            _state._test_auto_stop_timer = None

    with _state._monitor_lock:
        was_active = _state._test_mode
        sr = _state._monitor_sample_rate
        # Snapshot COPIES: the handed-off deques are zeroed in place by the
        # background secure-clear below, so downstream reads need owned data.
        raw_chunks = [np.array(c, copy=True) for c in _state._test_raw_chunks]
        filtered_chunks = [np.array(c, copy=True) for c in _state._test_filtered_chunks]
        filters = dict(_state._test_filters)
        # Dead ``list(_test_peak_history)`` expression removed
        rms_hist = list(_state._test_rms_history)
        clip_count = _state._test_clip_count
        silence_blocks = _state._test_silence_blocks

        # Clear test state
        _secure_clear_test_chunks(
            _state._test_raw_chunks,
            _state._test_filtered_chunks,
            _state._test_chunks,
        )
        _state._test_mode = False
        _state._test_chunks.clear()
        _state._test_raw_chunks.clear()
        _state._test_filtered_chunks.clear()
        _state._test_start_time = 0.0
        _state._test_filters.clear()
        _state._test_peak_history.clear()
        _state._test_rms_history.clear()
        _state._test_clip_count = 0
        _state._test_silence_blocks = 0

    # ``_test_chunks`` is a backward-compat shim (kept for tests outside
    if not was_active and not raw_chunks and not filtered_chunks:
        return {
            "success": False,
            "audio_file": None,
            "raw_audio_file": None,
            "duration_ms": 0,
            "sample_rate": 16000,
            "message": "No test running",
            "quality": {},
        }

    if not raw_chunks and not filtered_chunks:
        return {
            "success": True,
            "audio_file": None,
            "raw_audio_file": None,
            "duration_ms": 0,
            "sample_rate": sr,
            "message": "No audio captured",
            "quality": {},
        }

    # Build ``raw_audio`` (the "before" WAV) from ``_test_raw_chunks``.
    try:
        if raw_chunks:
            raw_audio = np.concatenate(raw_chunks, axis=0).reshape(-1)
        else:
            raw_audio = np.concatenate(filtered_chunks, axis=0).reshape(-1)
    except Exception as exc:
        log.warning("[LEVEL-MON] Chunk concatenation failed: %s", exc)
        return {
            "success": False,
            "audio_file": None,
            "raw_audio_file": None,
            "duration_ms": 0,
            "sample_rate": sr,
            "message": f"Audio processing failed: {exc}",
            "quality": {},
        }

    # Build ``audio`` (the "after" WAV) from
    if filtered_chunks:
        try:
            audio = np.concatenate(filtered_chunks, axis=0).reshape(-1)
        except Exception as exc:
            log.warning("[LEVEL-MON] Filtered chunk concatenation failed: %s", exc)
            audio = raw_audio.copy()
    else:
        audio = raw_audio.copy()

    duration_ms = int(len(audio) / sr * 1000)

    raw_abs = np.abs(raw_audio)
    raw_rms = float(np.sqrt(np.mean(np.square(raw_audio.astype(np.float32)))))
    raw_peak = float(raw_abs.max())
    total_blocks = len(rms_hist) if rms_hist else 0
    silence_ratio_value = round(silence_blocks / max(1, total_blocks), 4)
    non_silent_blocks = total_blocks - silence_blocks
    if total_blocks > 0:
        # Voice requires a loud peak AND a non-trivial non-silent share:
        has_voice = (
            raw_peak > _MIC_TEST_VOICE_PEAK
            and silence_ratio_value < _MIC_TEST_VOICE_MAX_SILENCE_RATIO
            and non_silent_blocks >= _MIC_TEST_VOICE_MIN_NON_SILENT_BLOCKS
        )
    else:
        # No per-block history to assess the share from (e.g. chunks
        has_voice = raw_peak > _MIC_TEST_VOICE_PEAK

    # Background noise is graded on the noise FLOOR (quietest ~32 ms
    noise_floor = float(min(rms_hist)) if rms_hist else raw_rms
    if noise_floor < _MIC_TEST_NOISE_LOW_RMS:
        noise_level = "low"
    elif noise_floor < _MIC_TEST_NOISE_HIGH_RMS:
        noise_level = "moderate"
    else:
        noise_level = "high"
    if has_voice and noise_level == "high":
        # A sustained voice signal dominates the total energy: the
        noise_level = "moderate"

    # annotate ``quality`` as ``dict[str, Any]`` so that
    quality: dict[str, Any] = {
        "volume_level": (
            "good"
            if raw_rms >= MIC_TEST_GOOD_VOLUME_RMS
            else ("very_low" if raw_rms < MIC_TEST_VERY_LOW_VOLUME_RMS else "low")
        ),
        "volume_rms": round(raw_rms, 6),
        "peak_level": round(raw_peak, 4),
        "noise_level": noise_level,
        "has_voice": has_voice,
        "has_clipping": clip_count > 0,
        "clipping_blocks": clip_count,
        "total_blocks": total_blocks,
        "silence_ratio": silence_ratio_value,
        "avg_rms": round(float(np.mean(rms_hist) if rms_hist else 0), 6),
        "peak_rms": round(float(np.max(rms_hist) if rms_hist else 0), 6),
    }

    # Detected issues list
    detected_issues = []
    if quality["noise_level"] == "high":
        detected_issues.append("High background noise")
    elif quality["noise_level"] == "moderate":
        detected_issues.append("Moderate background noise")
    if quality["has_clipping"]:
        detected_issues.append("Audio clipping detected")
    if quality["volume_level"] == "very_low":
        detected_issues.append("Volume too low, speak closer to the microphone")
    elif quality["volume_level"] == "low":
        detected_issues.append("Volume is low, consider raising input gain")
    if not quality["has_voice"]:
        detected_issues.append("No voice detected, try speaking during the test")
    quality["detected_issues"] = detected_issues

    # Estimate transcription quality (0-100)
    est_score = 100
    if quality["noise_level"] == "high":
        est_score -= 30
    elif quality["noise_level"] == "moderate":
        est_score -= 10
    if quality["has_clipping"]:
        est_score -= 20
    if quality["volume_level"] == "very_low":
        est_score -= 40
    elif quality["volume_level"] == "low":
        est_score -= 15
    if not quality["has_voice"]:
        est_score = 0
    # Inaudible input is already charged once via the very_low -40
    if raw_rms > 0.1:
        est_score = max(0, est_score - 10)
    quality["estimated_transcription_quality"] = max(0, min(100, est_score))

    # skip the post-hoc filter when ``filtered_chunks`` was
    if not filtered_chunks and filters and filters.get("noise_filter_enabled", True):
        try:
            # ADR 0007: AudioProcessor takes a config-like object directly.
            from voice_typer.server.audio_processor import AudioProcessor

            ap_config = types.SimpleNamespace(**filters)
            processor = AudioProcessor(ap_config, sample_rate=sr, quiet=True)

            block_size = 1024
            processed_parts = []
            for i in range(0, len(audio), block_size):
                block = audio[i : i + block_size]
                processed_parts.append(processor.process_chunk(block))
            non_null = [p for p in processed_parts if p is not None]
            processed = np.concatenate(non_null) if non_null else audio

            if len(processed) > 0:
                log.info(
                    "[LEVEL-MON] Applied filter chain: highpass=%s, gate=%s, method=%s",
                    filters.get("noise_filter_highpass", True),
                    filters.get("noise_filter_gate", True),
                    filters.get("noise_suppression_method", "rnnoise"),
                )
                audio = processed
        except Exception as exc:
            log.warning("[LEVEL-MON] Filter application failed (using raw audio): %s", exc)

    # See the module-top transport block: base64-in-one-frame exceeded
    audio_int16 = (audio * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())

    # Raw ("before") WAV for before/after comparison.
    raw_int16 = (raw_audio * 32767).astype(np.int16)
    raw_buf = io.BytesIO()
    with wave.open(raw_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw_int16.tobytes())

    # The test-chunk state was already cleared above, so a persist
    try:
        audio_file = _write_test_wav(buf, "filtered")
        raw_audio_file = _write_test_wav(raw_buf, "raw")
    except Exception as exc:
        log.warning(
            "[LEVEL-MON] Test persist failed:%s not recorded: %s",
            format_duration(duration_ms / 1000),
            exc,
        )
        return {
            "success": False,
            "audio_file": None,
            "raw_audio_file": None,
            "duration_ms": duration_ms,
            "sample_rate": sr,
            "message": f"Failed to persist test recording: {type(exc).__name__}",
            "quality": quality,
        }

    # Disk TTL: auto-delete exactly these uuid paths TTL seconds after
    _schedule_test_recording_expiry(
        [ref["path"] for ref in (audio_file, raw_audio_file) if isinstance(ref, dict) and ref.get("path")]
    )

    log.info(
        "[LEVEL-MON] Test stopped:%s recorded, wrote raw(before)=%d bytes + filtered(after)=%d bytes WAV to %s/",
        format_duration(duration_ms / 1000),
        len(raw_buf.getvalue()),
        len(buf.getvalue()),
        _TEST_RECORDINGS_DIRNAME,
    )

    return {
        "success": True,
        "audio_file": audio_file,
        "raw_audio_file": raw_audio_file,
        "duration_ms": duration_ms,
        "sample_rate": sr,
        "message": f"Recorded{format_duration(duration_ms / 1000)} of audio",
        "quality": quality,
    }
