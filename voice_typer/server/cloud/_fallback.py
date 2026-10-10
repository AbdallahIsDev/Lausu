"""Cloud to local fallback policy for the cloud engine.

One concern only: classify a cloud failure for the user and, when a local
engine is available, hand the audio to it instead of failing the dictation
cycle. Consent errors and user aborts never fall back.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

from voice_typer.server.asr_errors import (
    CloudAuthError,
    CloudConfigError,
    CloudEmptyResponseError,
    CloudRateLimitError,
    CloudServerError,
    ConsentRequiredError,
)

log = logging.getLogger(__name__)


class _FallbackHost(Protocol):
    """Engine surface the fallback policy drives (owned by ``CloudEngine``)."""

    provider: str
    _abort_event: threading.Event
    _local_engine_factory: Callable[..., Any] | None

    def transcribe(self, audio: np.ndarray) -> str: ...


def _fallback_kind(exc: BaseException) -> str:
    """Classify a cloud failure for fallback UX: "key" | "provider" | "network".

    "key": the API key/config is at fault (401/403, missing key or URL),
    the user must fix credentials. "provider": the provider failed
    (5xx, rate limit, empty transcript), retry later. "network": the
    request never reached the provider (timeout, DNS, reset).
    """
    if isinstance(exc, (CloudAuthError, CloudConfigError)):
        return "key"
    if isinstance(exc, (CloudServerError, CloudRateLimitError, CloudEmptyResponseError)):
        return "provider"
    return "network"


def fall_back_to_local(
    engine: _FallbackHost,
    audio: np.ndarray,
    local_engine=None,
    audio_stats: tuple[float, float, float] | None = None,
) -> str:
    """Try cloud transcription; fall back to local engine on failure.

    PERF: if the cloud request fails after all retries,
    and a local_engine is provided, attempt transcription on it
    instead of raising.  This gives a best-effort result even
    when the cloud is temporarily unreachable.

            When ``local_engine`` is NOT explicitly passed but the
            engine was constructed with a ``local_engine_factory`` callable,
            the factory is invoked lazily to construct the local whisper
            engine on demand.  This decouples the cloud engine from the
            model registry / app object: callers that don't know about
            the local whisper backend (e.g. the streaming session) still
            get the cloud→local fallback as long as the factory was wired
            at construction time.  If the factory returns ``None`` (e.g.
            cold start with whisper not yet registered), the fallback is
            skipped and the original cloud error is re-raised.

    Signature note: ``audio_stats`` is accepted
            for signature parity with the three local engines
            (Whisper/Parakeet/Qwen) so ``DictationPipeline._transcribe``
            can pass it unconditionally without a broad ``except TypeError``
            fallback. The cloud engines don't use it, RMS/peak/silence
            detection is irrelevant when audio is shipped to a remote API
           , so the value is simply ignored here on the cloud path.
            When a ``local_engine`` is provided, ``audio_stats`` is forwarded
            so the local fallback benefits from the same pre-computation
            (all three local engines accept the kwarg).
    """
    try:
        return engine.transcribe(audio)
    except ConsentRequiredError:
        # consent errors must propagate, do NOT fall back to
        raise
    except (RuntimeError, OSError) as cloud_err:
        if engine._abort_event.is_set():
            # User-cancelled (ESC) or watchdog-recovered mid-request:
            # the cycle is marked cancelled, so a local fallback decode
            # would be wasted work pasted nowhere (CancellationGuard
            # blocks it). Return empty and let the empty-transcription
            # branch skip silently.
            log.info(
                "[CLOUD] %s request aborted, skipping local fallback",
                engine.provider,
            )
            return ""
        # Prefer the explicitly-passed local_engine; fall
        resolved_local_engine = local_engine
        if resolved_local_engine is None and engine._local_engine_factory is not None:
            try:
                resolved_local_engine = engine._local_engine_factory()
            except Exception as factory_err:
                log.warning(
                    "[CLOUD] %s local_engine_factory raised; skipping fallback: %s",
                    engine.provider,
                    factory_err,
                )
                resolved_local_engine = None
        if resolved_local_engine is not None:
            # Include exc_info so the cloud failure
            log.warning(
                "[CLOUD] %s failed, falling back to local engine: %s",
                engine.provider,
                cloud_err,
                exc_info=True,
            )
            # surface the fallback to the renderer so the
            try:
                from voice_typer.server import event_bus

                event_bus.publish(
                    {
                        "type": "cloud_fallback_used",
                        "data": {
                            "provider": engine.provider,
                            "kind": _fallback_kind(cloud_err),
                            "reason": str(cloud_err)[:200],
                        },
                    }
                )
            except Exception as notify_exc:
                log.debug(
                    "[CLOUD] could not publish cloud_fallback_used event: %s",
                    notify_exc,
                )
            try:
                return resolved_local_engine.transcribe(audio, audio_stats=audio_stats)
            except Exception as local_err:
                # Include exc_info so the local fallback
                log.error("[CLOUD] Local fallback also failed: %s", local_err, exc_info=True)
                # re-raise the ORIGINAL cloud error (not a
                raise cloud_err from local_err
        raise
