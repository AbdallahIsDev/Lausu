"""Filter-divergence guard: a lying filter must never eat a dictation.

The microphone chain can be configured into a state where it removes the
speech itself (docs/microphone-filter-failures.md §1.1, §1.6). VAD runs on
the FILTERED audio on purpose (§2.3), so on its own it cannot tell "the room
is quiet" from "the chain deleted the user". This guard compares the raw
chunk level with the filtered one and fails open the moment they disagree.

Two pieces:

* :class:`FilterDivergenceGuard` - pure per-recording math (no I/O).
* :class:`FilterFallback` - owns the raw shadow buffer and the swap to it,
  so the pipeline only has to call :meth:`FilterFallback.observe`,
  :meth:`FilterFallback.suspend_silence` and :meth:`FilterFallback.finalize`.

Rules (docs/microphone-filter-failures.md §2.3):

1. Collapse = voiced speech on raw (pitch-strength cue) while filtered sits
   more than 25 dB below it, for more than 500 ms of voiced time inside the
   last 2 s, in one unbroken run of at least 300 ms.
2. Fail open: the whole take is swapped to the raw shadow and filtering
   stops for the rest of the recording.
3. The silence timer is suspended while the guard is active, so the user is
   never auto-stopped for silence the filter invented.
4. A take that ends with speech on raw and nothing on filtered is never
   delivered blank: it is swapped to the unfiltered audio at stop time.
"""

from __future__ import annotations

import collections
import logging
import math
from typing import Any

import numpy as np

from voice_typer.server._audio_constants import AUDIO_SILENCE_RMS

log = logging.getLogger(__name__)

# "more than 25 dB below raw" (§2.3 rule 1). Below this a suppressor is
# allowed to work; above it the chain is deleting content, not noise.
COLLAPSE_DB: float = 25.0

# "more than 500 ms" of DELETED voiced speech (§2.3 rule 1).
COLLAPSE_SECONDS: float = 0.5

# A raw chunk only counts as speech evidence when it carries VOICED energy.
# Level alone cannot separate "the filter deleted the speaker" from "the
# filter correctly removed the noise": measured on the shipped stress fixture,
# pink noise at -31 dBFS gets removed by 50-70 dB, and an envelope max/min
# test lets a 500 ms pause look like a collapse because the window max still
# carries the last loud syllable (docs/microphone-filter-failures.md §3).
# Pitch strength (normalized autocorrelation peak in the 80-400 Hz range)
# separates them: over 0.35 on 41-47% of speech chunks vs 10.7% of noise.
SPEECH_FLOOR_DBFS: float = -60.0
PITCH_WINDOW_SECONDS: float = 0.04
PITCH_MIN_HZ: float = 80.0
PITCH_MAX_HZ: float = 400.0
PITCH_STRENGTH: float = 0.35
# Rolling evidence window; a trip needs most of the voiced time inside it to
# have been deleted, so a filter that removes background noise (and keeps the
# speech) never accumulates.
SPEECH_WINDOW_SECONDS: float = 2.0
COLLAPSE_SHARE: float = 0.5
# A trip also needs one unbroken stretch of deleted voiced speech. Pink noise
# produces isolated pitch spikes (longest measured run: 3 chunks, 96 ms) but
# never a continuous run, while a collapsing chain deletes whole utterances.
COLLAPSE_RUN_SECONDS: float = 0.3
# Consecutive voiced time that proves a take contains speech at all. Used by
# the stop-time blank rescue: one lucky noise window must not swap a silent
# take to raw noise.
SPEECH_EVIDENCE_SECONDS: float = 0.12

# Failure reasons reported to the caller (log line + toast payload).
REASON_COLLAPSE = "collapse"  # guard tripped mid-recording
REASON_SILENT_TAKE = "silent_take"  # stop-time fallback: speech on raw, silence filtered


def rms_dbfs(rms: float) -> float:
    """dBFS for a linear RMS value, clamped so silence compares instead of raising."""
    try:
        value = float(rms)
    except (TypeError, ValueError):
        return -200.0
    if not math.isfinite(value) or value <= 0.0:
        return -200.0
    return 20.0 * math.log10(value)


def rms_of(chunk: Any) -> float:
    """Linear RMS of one audio chunk (0.0 for empty/garbage input)."""
    try:
        flat = np.asarray(chunk, dtype=np.float32).reshape(-1)
    except (TypeError, ValueError):
        return 0.0
    if flat.size == 0:
        return 0.0
    return float(np.sqrt(np.dot(flat, flat) / flat.size))


def pitch_strength(window: np.ndarray, sample_rate: int) -> float:
    """Normalized autocorrelation peak of ``window`` in the pitch range.

    Voiced speech repeats at 80-400 Hz, so its autocorrelation peaks near 1.0
    at one full period. Broadband noise has no period and stays low. The
    window must hold several periods (``PITCH_WINDOW_SECONDS``) or the peak is
    meaningless. FFT autocorrelation keeps the cost at tens of microseconds
    per chunk; the guard runs it only while a suppressor/gate is in the chain.
    """
    flat = np.asarray(window, dtype=np.float32).reshape(-1)
    if flat.size < 64 or sample_rate <= 0:
        return 0.0
    centred = flat - float(flat.mean())
    energy = float(np.dot(centred, centred))
    if energy <= 1e-12:
        return 0.0
    size = 1 << max(1, (2 * centred.size - 1).bit_length())
    spectrum = np.fft.rfft(centred, size)
    autocorr = np.fft.irfft(spectrum * np.conj(spectrum), size)[: centred.size]
    low = max(2, int(sample_rate / PITCH_MAX_HZ))
    high = min(centred.size - 1, int(sample_rate / PITCH_MIN_HZ))
    if high <= low:
        return 0.0
    return float(np.max(autocorr[low : high + 1]) / energy)


def publish_filter_collapse(
    reason: str,
    fields: dict[str, float | str | bool],
    preset: str,
    method: str,
) -> None:
    """Publish ``filter_collapse`` for the renderer's toast (one consumer)."""
    try:
        from voice_typer.server import event_bus

        event_bus.publish(
            {
                "type": "filter_collapse",
                "data": {
                    "reason": reason,
                    "raw_db": fields.get("raw_db"),
                    "filtered_db": fields.get("filtered_db"),
                    "delta_db": fields.get("delta_db"),
                    "preset": preset,
                    "method": method,
                },
            }
        )
    except Exception:
        log.debug("[RECORDING] could not publish filter_collapse", exc_info=True)


# One WARNING / one toast per process per reason: the chain is a config
# property, so repeating it every recording is noise, and the per-recording
# summary line (C-LOG-2) already carries the state.
_reported_reasons: set[str] = set()


def report_fallback(recorder: Any, fallback: FilterFallback, reason: str) -> None:
    """Log + toast a filter fallback once per process. Never raises."""
    fields = fallback.summary_fields()
    config = getattr(recorder, "config", None)
    preset = str(getattr(config, "audio_preset", "unknown"))
    method = str(getattr(config, "noise_suppression_method", "unknown"))
    if reason in _reported_reasons:
        log.debug(
            "[RECORDING] filter fallback repeat (%s): raw=%s filtered=%s delta=%s",
            reason,
            fields.get("raw_db"),
            fields.get("filtered_db"),
            fields.get("delta_db"),
        )
        return
    _reported_reasons.add(reason)
    if reason == REASON_SILENT_TAKE:
        log.warning(
            "[RECORDING] Filter divergence: take was silent after filtering "
            "(raw=%.1f dBFS, filtered=%.1f dBFS, delta=%.1f dB, preset=%s, "
            "method=%s); delivering the unfiltered take",
            fields.get("raw_db", -200.0),
            fields.get("filtered_db", -200.0),
            fields.get("delta_db", 0.0),
            preset,
            method,
        )
    else:
        log.warning(
            "[RECORDING] Filter divergence: chain is removing speech "
            "(raw=%.1f dBFS, filtered=%.1f dBFS, delta=%.1f dB, preset=%s, "
            "method=%s); filtering disabled for this take",
            fields.get("raw_db", -200.0),
            fields.get("filtered_db", -200.0),
            fields.get("delta_db", 0.0),
            preset,
            method,
        )
    publish_filter_collapse(reason, fields, preset, method)


class FilterDivergenceGuard:
    """Per-recording detector for "the filter is eating the speech"."""

    def __init__(
        self,
        *,
        collapse_db: float = COLLAPSE_DB,
        collapse_seconds: float = COLLAPSE_SECONDS,
        speech_floor_dbfs: float = SPEECH_FLOOR_DBFS,
        pitch_strength: float = PITCH_STRENGTH,
        speech_window_seconds: float = SPEECH_WINDOW_SECONDS,
        collapse_share: float = COLLAPSE_SHARE,
        collapse_run_seconds: float = COLLAPSE_RUN_SECONDS,
    ) -> None:
        self._collapse_db = float(collapse_db)
        self._collapse_seconds = float(collapse_seconds)
        self._speech_floor_dbfs = float(speech_floor_dbfs)
        self._pitch_strength = float(pitch_strength)
        self._window_seconds = float(speech_window_seconds)
        self._collapse_share = float(collapse_share)
        self._collapse_run_seconds = float(collapse_run_seconds)
        # (duration, speech, collapsed) per chunk, bounded by the window.
        self._window: collections.deque[tuple[float, bool, bool]] = collections.deque()
        self._pitch_buf = np.zeros(0, dtype=np.float32)
        # Consecutive voiced time; proves the take carries speech at all.
        self._voiced_run = 0.0
        # Consecutive deleted-voiced time; one utterance has to disappear.
        self._deleted_run = 0.0
        self.raw_db = -200.0
        self.filtered_db = -200.0
        self.delta_db = 0.0
        self.tripped = False
        # True once voiced speech ran long enough (stop-time blank rescue).
        self.saw_speech = False

    def reset(self) -> None:
        """Start a new recording (the latch is per recording)."""
        self._window.clear()
        self._pitch_buf = np.zeros(0, dtype=np.float32)
        self._voiced_run = 0.0
        self._deleted_run = 0.0
        self.raw_db = -200.0
        self.filtered_db = -200.0
        self.delta_db = 0.0
        self.tripped = False
        self.saw_speech = False

    def _pitch_window(self, raw: np.ndarray, sample_rate: int) -> np.ndarray:
        """Keep the trailing ``PITCH_WINDOW_SECONDS`` of raw audio for pitch."""
        span = max(1, int(int(sample_rate) * PITCH_WINDOW_SECONDS))
        if self._pitch_buf.size and self._pitch_buf.size + raw.size > span * 4:
            self._pitch_buf = np.zeros(0, dtype=np.float32)
        self._pitch_buf = np.concatenate((self._pitch_buf.reshape(-1), raw.reshape(-1)))[-span:]
        return self._pitch_buf

    def speech_active(self, raw: np.ndarray, sample_rate: int, raw_db: float) -> bool:
        """True when the raw chunk carries voiced speech above the floor."""
        if raw_db < self._speech_floor_dbfs:
            return False
        window = self._pitch_window(raw, sample_rate)
        return pitch_strength(window, sample_rate) >= self._pitch_strength

    def _window_totals(self) -> tuple[float, float]:
        """Drop evidence older than the window; return (voiced, deleted) seconds."""
        total = sum(duration for duration, _speech, _collapsed in self._window)
        while self._window and total > self._window_seconds:
            head, _speech, _collapsed = self._window.popleft()
            total -= head
        voiced = sum(duration for duration, speech, _collapsed in self._window if speech)
        deleted = sum(duration for duration, speech, collapsed in self._window if speech and collapsed)
        return voiced, deleted

    def observe(
        self,
        raw: np.ndarray,
        filtered_rms: float,
        duration: float,
        sample_rate: int,
    ) -> bool:
        """Record one chunk; return ``True`` exactly once, on the trip."""
        raw_rms = rms_of(raw)
        self.raw_db = rms_dbfs(raw_rms)
        self.filtered_db = rms_dbfs(filtered_rms)
        self.delta_db = self.raw_db - self.filtered_db
        speech = self.speech_active(raw, sample_rate, self.raw_db)
        collapsed = speech and self.delta_db > self._collapse_db
        if duration > 0.0:
            self._window.append((float(duration), speech, collapsed))
            self._voiced_run = self._voiced_run + duration if speech else 0.0
            self._deleted_run = self._deleted_run + duration if collapsed else 0.0
            if self._voiced_run >= SPEECH_EVIDENCE_SECONDS:
                self.saw_speech = True
        voiced, deleted = self._window_totals()
        if self.tripped:
            return False
        # The chain is lying when most of the voiced time it saw is gone, for
        # longer than the collapse bar, in one unbroken stretch. Noise never
        # builds voiced time, and never in a run, so a suppressor doing its job
        # cannot trip this.
        if (
            deleted >= self._collapse_seconds
            and self._deleted_run >= self._collapse_run_seconds
            and voiced > 0.0
            and deleted >= self._collapse_share * voiced
        ):
            self.tripped = True
            return True
        return False


class FilterFallback:
    """Raw shadow + swap-to-unfiltered bookkeeping for :class:`AudioPipeline`."""

    def __init__(self) -> None:
        self._guard = FilterDivergenceGuard()
        self._shadow: Any | None = None
        self._shadow_sr: int = 0
        self._shadow_active: bool = False
        # True once the take was swapped to raw (mid-recording or at stop).
        self.swapped: bool = False
        self.reason: str = ""

    # ----- lifecycle ---------------------------------------------------
    def reset(self, recorder: Any) -> None:
        """Start a new recording: drop the shadow and clear the latch."""
        self._guard.reset()
        self._shadow = None
        self._shadow_sr = 0
        self._shadow_active = False
        self.swapped = False
        self.reason = ""

    @property
    def tripped(self) -> bool:
        return self._guard.tripped

    @property
    def saw_speech(self) -> bool:
        return self._guard.saw_speech

    def active(self) -> bool:
        """True when this recording keeps a raw shadow."""
        return self._shadow_active

    def suspend_silence(self) -> bool:
        """True while the guard is active, so invented silence cannot auto-stop."""
        return self._guard.tripped

    def summary_fields(self) -> dict[str, float | str | bool]:
        """Per-recording log/summary values (C-LOG-2/§2.3 rule 5)."""
        return {
            "raw_db": round(self._guard.raw_db, 1),
            "filtered_db": round(self._guard.filtered_db, 1),
            "delta_db": round(self._guard.delta_db, 1),
            "guard": "tripped" if self._guard.tripped else ("swapped" if self.swapped else "ok"),
        }

    # ----- per-chunk ---------------------------------------------------
    @staticmethod
    def chain_can_eat_speech(processor: Any) -> bool:
        """True when the chain holds a suppressor or a gate.

        Those are the two stages measured eating healthy speech; shaping
        filters (high-pass/EQ/compressor/limiter) cannot collapse a take, so
        they do not cost the shadow's memory.
        """
        chain = getattr(processor, "_chain", None)
        names = getattr(chain, "filter_names", None)
        if not names:
            return False
        return any(str(name).startswith("NoiseSuppressor(") or str(name) == "NoiseGate" for name in names)

    def ensure_shadow(self, recorder: Any, processor: Any, sample_rate: int) -> None:
        """Create the raw shadow for this recording when the chain justifies it."""
        if self._shadow_active or self.swapped:
            return
        if not self.chain_can_eat_speech(processor):
            return
        from voice_typer.server.recording.recorder import DEFAULT_MAX_BUFFER_CHUNKS
        from voice_typer.server.recording.recording_buffer import GrowableRecordingBuffer

        self._shadow = GrowableRecordingBuffer(
            maxlen=DEFAULT_MAX_BUFFER_CHUNKS,
            nominal_sample_rate=sample_rate,
        )
        self._shadow_sr = int(sample_rate or 0)
        self._shadow_active = True

    def append_raw(self, raw_mono: Any) -> None:
        """Copy the raw chunk into the shadow (own the memory, never a view)."""
        if not self._shadow_active or self._shadow is None:
            return
        try:
            self._shadow.append(raw_mono.copy())
        except Exception:
            log.debug("[RECORDING] raw shadow append failed; guard disabled for this take", exc_info=True)
            self._shadow_active = False

    def observe(
        self,
        raw_chunk: Any,
        filtered_rms: float,
        duration: float,
        sample_rate: int,
    ) -> bool:
        """Feed one raw/filtered pair; ``True`` on the trip transition."""
        if not self._shadow_active or self.swapped:
            return False
        return self._guard.observe(raw_chunk, filtered_rms, duration, sample_rate)

    # ----- swaps -------------------------------------------------------
    def swap_to_raw(self, recorder: Any, reason: str, buffer_sr: int) -> bool:
        """Install the raw shadow as the take's buffer. Caller holds no pipeline lock."""
        if self.swapped or self._shadow is None:
            return False
        pipeline = recorder._audio_pipeline
        shadow = self._shadow
        target_sr = int(buffer_sr or self._shadow_sr or recorder._effective_sr)
        try:
            raw = shadow.export_copy()
        except Exception:
            log.warning("[RECORDING] filter fallback could not read the raw shadow", exc_info=True)
            return False
        if raw.size == 0:
            return False
        if target_sr != self._shadow_sr:
            try:
                from voice_typer.server.recording.format import resample_chunk

                raw = resample_chunk(recorder, raw, self._shadow_sr, target_sr)
            except Exception:
                log.warning(
                    "[RECORDING] filter fallback could not resample the raw shadow (%d -> %d Hz)",
                    self._shadow_sr,
                    target_sr,
                    exc_info=True,
                )
                return False
        # The secure-clear helpers live in ``recording.buffer``; the buffer
        # factory lives in ``recording.recording_buffer`` (C-ARCH-2: patch the
        # OWNING module, never a facade).
        from voice_typer.server.recording import buffer as _buffer_mod, recording_buffer

        with pipeline._lock:
            old_buffer = pipeline._buffer
            new_buffer = recording_buffer._fresh_recording_buffer_like(recorder, old_buffer)
            new_buffer.append(raw)
            pipeline._buffer = new_buffer
            pipeline._buffer_sr = target_sr
            pipeline._total_buffered_samples = int(raw.shape[0])
        _buffer_mod._secure_clear_array_background(old_buffer)
        self.swapped = True
        self.reason = reason
        self._shadow = None
        self._shadow_active = False
        return True

    def finalize(self, recorder: Any) -> str | None:
        """Stop-time fallback: never deliver a blank take we know had speech."""
        if self.swapped or self._shadow is None:
            return None
        if not self._guard.saw_speech:
            return None
        pipeline = recorder._audio_pipeline
        try:
            filtered = pipeline._buffer.export_copy() if pipeline._buffer else None
        except Exception:
            filtered = None
        if filtered is not None and filtered.size:
            flat = filtered.reshape(-1)
            rms = float((flat.astype("float64") ** 2).mean() ** 0.5) if flat.size else 0.0
            if rms >= AUDIO_SILENCE_RMS:
                return None
        buffer_sr = int(pipeline._buffer_sr or recorder._effective_sr)
        if self.swap_to_raw(recorder, REASON_SILENT_TAKE, buffer_sr):
            return REASON_SILENT_TAKE
        return None
