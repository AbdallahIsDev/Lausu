"""Shared hallucination detection for ASR transcription results.

Single source of truth for the low-audio hallucination gate, shared by the
whisper, parakeet and qwen engines so all three reject identical output.

SEC-009: Provides a safe logging helper for hallucination rejections
that gates detailed text logging behind the ``log_transcriptions``
config flag and applies PII redaction + truncation to 40 chars.
"""

import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Maximum chars to log from hallucination text (SEC-009)
_HALLUCINATION_LOG_MAX_CHARS = 40

# User-facing modes for ``Config.hallucination_filter_mode``.
HALLUCINATION_FILTER_OFF = "off"
HALLUCINATION_FILTER_STRICT = "strict"
HALLUCINATION_FILTER_BALANCED = "balanced"
HALLUCINATION_FILTER_MODES: tuple[str, ...] = (
    HALLUCINATION_FILTER_OFF,
    HALLUCINATION_FILTER_STRICT,
    HALLUCINATION_FILTER_BALANCED,
)
DEFAULT_HALLUCINATION_FILTER_MODE = HALLUCINATION_FILTER_BALANCED

# Stamped on the engine whenever the gate discards a result, so the dictation
# pipeline can tell a rejected hallucination apart from genuine silence
# instead of reporting "no speech detected" for both.
REJECTION_REASON_HALLUCINATION = "low-audio hallucination"

# Known phrases that Whisper emits on near-silence audio.
KNOWN_LOW_AUDIO_HALLUCINATIONS = {
    # Multi-word phrases (original OBS / Whisper-decoding artifacts)
    "thanks for watching",
    "thank you for watching",
    "see you next time",
    "bye",
    "thank you",
    "subscribe",
    "like and subscribe",
    "please subscribe",
    "thanks for listening",
    "thank you for listening",
    # common single-token hallucinations
    "you",  # Whisper's #1 most-likely starter token
    "the",  # very common Whisper decoder artifact on silence
    "so",  # common filler-token hallucination
    "thanks",  # truncation of "thanks for watching"
    "music",  # Whisper hallucinates [Music] tags on noise
    "amara",  # amara.org subtitle watermark hallucination
}

# Entries of the catalog above that are ALSO plausible real dictation. A
# quiet "so" / "you" / "bye" carries the same RMS as the fabricated version,
# so audio energy cannot separate them; ``balanced`` mode therefore demands
# the decoder's own silence probabilities before discarding these.
AMBIGUOUS_LOW_AUDIO_HALLUCINATIONS = frozenset(
    {
        "bye",
        "thank you",
        "thanks",
        "so",
        "the",
        "you",
    }
)

# Upstream Whisper silence convention (openai/whisper ``transcribe()``:
# ``no_speech_threshold=0.6``, ``logprob_threshold=-1.0``). A segment counts
# as silent only when BOTH hold -- either alone produces false rejections of
# correctly-decoded speech.
NO_SPEECH_PROB_THRESHOLD = 0.6
LOGPROB_SILENCE_THRESHOLD = -1.0


def normalize_hallucination_filter_mode(mode: str | None) -> str:
    """Coerce an arbitrary stored value to a supported filter mode.

    Fail-soft to the default rather than raising: this runs on the
    transcription hot path and a hand-edited config must never break it.
    """
    return mode if mode in HALLUCINATION_FILTER_MODES else DEFAULT_HALLUCINATION_FILTER_MODE


def _decoder_confirms_silence(
    no_speech_prob: float | None,
    avg_logprob: float | None,
) -> bool:
    """True when the decoder itself reports the segment as silent.

    Fails OPEN (returns ``False``) when the engine reports no
    probabilities -- parakeet and qwen never do, so in that case the
    ambiguous phrases are kept rather than silently dropped.
    """
    if no_speech_prob is None or avg_logprob is None:
        return False
    return no_speech_prob > NO_SPEECH_PROB_THRESHOLD and avg_logprob < LOGPROB_SILENCE_THRESHOLD


def normalize_hallucination_key(text: str) -> str:
    """Normalize text for hallucination key lookup."""
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def reject_and_stamp_reason(
    engine: Any,
    text: str,
    rms: float,
    **kwargs: Any,
) -> bool:
    """Run the gate for one engine and stamp ``last_rejection_reason``.

    Single chokepoint so parakeet and qwen report a rejection the same way
    whisper's delegator does (``transcription_result.reject_low_audio_hallucination``):
    the flag is set to the rejection reason on a hit and cleared to ``None``
    on every run, so a stale value can never leak into the next dictation.
    """
    mode = getattr(getattr(engine, "config", None), "hallucination_filter_mode", None)
    rejected = should_reject_low_audio_hallucination(text, rms, mode=mode, **kwargs)
    try:
        engine.last_rejection_reason = REJECTION_REASON_HALLUCINATION if rejected else None
    except AttributeError:
        # A slotted/frozen engine stand-in in tests: the gate result still
        # stands, only the reason flag is unavailable.
        log.debug("engine has no last_rejection_reason slot", exc_info=True)
    return rejected


def should_reject_low_audio_hallucination(
    text: str,
    rms: float,
    *,
    peak: float | None = None,
    silence_pct: float | None = None,
    duration: float | None = None,
    first_segment_start: float | None = None,
    last_segment_end: float | None = None,
    no_speech_prob: float | None = None,
    avg_logprob: float | None = None,
    mode: str | None = None,
) -> bool:
    """Return True if the transcription is likely a hallucination from near-silence."""
    resolved_mode = normalize_hallucination_filter_mode(mode)
    if resolved_mode == HALLUCINATION_FILTER_OFF:
        return False
    if not text:
        return False

    key = normalize_hallucination_key(text)
    if key not in KNOWN_LOW_AUDIO_HALLUCINATIONS:
        return False

    # Balanced mode: for phrases that double as real dictation, audio
    # energy is not evidence enough -- require decoder confirmation.
    if (
        resolved_mode == HALLUCINATION_FILTER_BALANCED
        and key in AMBIGUOUS_LOW_AUDIO_HALLUCINATIONS
        and not _decoder_confirms_silence(no_speech_prob, avg_logprob)
    ):
        return False

    # Tier 1: simple check (always available)
    if rms < 0.01 and (silence_pct is None or silence_pct >= 95.0) and (duration is None or duration < 10.0):
        return True

    # Tier 2: extended check (requires segment timing info)
    if (
        duration is not None
        and duration >= 30.0
        and rms < 0.005
        and silence_pct is not None
        and silence_pct >= 50.0
        and first_segment_start is not None
        and first_segment_start <= 3.0
        and last_segment_end is not None
    ):
        segment_span = max(0.0, last_segment_end - first_segment_start)
        if segment_span <= 5.0:
            return True

    return False


def log_hallucination_rejection(
    engine_tag: str,
    text: str,
    reason: str = "hallucination",
    *,
    log_transcriptions: bool = False,
) -> None:
    """SEC-009: Log a hallucination rejection with PII-safe output.

    When ``log_transcriptions`` is False (the default), only logs the
    character count and rejection reason -- never the text content.
    When True, logs the text but applies PII redaction using the
    existing PIIRedactionFilter patterns and truncates to 40 chars
    (down from the previous 80).
    """
    char_count = len(text)
    if not log_transcriptions:
        # SEC-009: When logging is disabled, only log metadata -- no text content
        log.warning(
            "%s Rejected likely %s (%d chars)",
            engine_tag,
            reason,
            char_count,
        )
        return

    # SEC-009: When logging is enabled, apply PII redaction and truncation.
    try:
        from voice_typer.server.security import redact_pii

        safe_text = redact_pii(text)[:_HALLUCINATION_LOG_MAX_CHARS]
    except Exception:
        # No longer a silent ``except Exception: pass`` --
        log.debug(
            "PII redaction failed in log_hallucination_rejection; logging redacted marker only",
            exc_info=True,
        )
        safe_text = "<redaction-failed>"

    log.warning(
        "%s Rejected likely %s (%d chars): %s",
        engine_tag,
        reason,
        char_count,
        safe_text,
    )
