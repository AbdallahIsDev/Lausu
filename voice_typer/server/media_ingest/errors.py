"""Media-ingest error taxonomy (ADR-0023 edge catalog E1-E15)."""

from __future__ import annotations

from voice_typer.server.ipc.error_codes import ErrorCodes


class MediaIngestError(Exception):
    """User-safe ingest failure carrying a stable machine code."""

    def __init__(self, code: str, message: str = "", *, details: dict | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        # Structured extras the renderer needs to build its localized copy
        # (e.g. {"count": 3} for a multi-item link). Never free text.
        self.details = details


NO_AUDIO = "no_audio"
UNSUPPORTED_LIVE = "unsupported_live"
LOGIN_REQUIRED = "login_required"
GEO_BLOCKED = "geo_blocked"
PLAYLIST_REJECTED = "playlist_rejected"
DRM_REFUSED = "drm_refused"
DECODE_FAILED = "decode_failed"
RESOLVE_FAILED = "resolve_failed"
STREAM_STALLED = "stream_stalled"
URL_EXPIRED = "url_expired"
DOWNLOAD_FAILED = "download_failed"
NO_ENGINE = "no_engine_loaded"
JOB_BUSY = "job_busy"
NO_JOB = "no_active_job"
CANCELLED = "cancelled"

# URL classification: one link that expands to several playable items, and a
# link that expands to no playable media at all. Both are GLOBAL rules for
# every extractor, never per-site special cases.
MULTI_ITEM_URL = "multi_item_url"
NO_MEDIA_URL = "no_media_url"

# Ingest validation: the audio the decoder produced does not cover the media
# the user asked for. Never persisted, never reported as success.
MEDIA_TOO_SHORT = "media_too_short"
MEDIA_TRUNCATED = "media_truncated"

# Model-layer states surfaced through the same taxonomy (namespaced: these
# two also travel in IPC error envelopes, so the canonical constants live in
# the error-code registry rather than being restated here).
MODEL_LOADING = ErrorCodes.MODEL_LOADING
MODEL_CHANGED = ErrorCodes.MODEL_CHANGED

# Ingest hiccups worth one more attempt: the transport or the signed URL
# flaked, nothing was learned about the media itself. Every other code is a
# VERDICT about the media (missing audio, DRM, multi-item, truncated) and
# retrying it would only repeat the same decode for the same answer.
RETRYABLE_INGEST_CODES: frozenset[str] = frozenset({DOWNLOAD_FAILED, URL_EXPIRED, STREAM_STALLED})


def is_retryable_ingest_code(code: str | None) -> bool:
    """True when ``code`` describes a transient ingest failure."""
    return code in RETRYABLE_INGEST_CODES


# Every code this package can put on a job event. Used by the contract test
# that keeps the renderer copy map in step with the backend taxonomy.
MEDIA_JOB_CODES: frozenset[str] = frozenset(
    {
        NO_AUDIO,
        UNSUPPORTED_LIVE,
        LOGIN_REQUIRED,
        GEO_BLOCKED,
        PLAYLIST_REJECTED,
        DRM_REFUSED,
        DECODE_FAILED,
        RESOLVE_FAILED,
        STREAM_STALLED,
        URL_EXPIRED,
        DOWNLOAD_FAILED,
        NO_ENGINE,
        JOB_BUSY,
        NO_JOB,
        CANCELLED,
        MULTI_ITEM_URL,
        NO_MEDIA_URL,
        MEDIA_TOO_SHORT,
        MEDIA_TRUNCATED,
        MODEL_LOADING,
        MODEL_CHANGED,
    }
)
