"""CloudEngine: the cloud ASR engine implementing TranscriberProtocol.

Engine-dispatch half of the ``cloud_engines.py`` monolith split: the full
``CloudEngine`` class (lifecycle, consent gate, shared retry skeleton,
connection probe) lives HERE. The provider send paths and their retry loop
live in :mod:`._sendpaths`; the cloud-to-local fallback policy lives in
:mod:`._fallback`; the stateless plumbing (transport, retry policy, provider
defaults, request shaping) lives in the sibling leaf modules
(:mod:`._transport`, :mod:`._retry`, :mod:`._defaults`,
:mod:`._providers.*`). Both split leaves are re-exported here, so every
existing import path keeps resolving.

FACADE-NAMESPACE PATCH CONTRACT: tests and production patch
engine-adjacent singletons through the facade module's namespace
(``setattr(cloud_engines, "_opener", mock)``,
``patch("voice_typer.server.cloud_engines.assert_url_allowed")``).
This module therefore resolves ``_opener`` and ``assert_url_allowed``
from the facade namespace at call time (see :func:`_facade`) instead
of importing them statically. Every other dependency is imported
statically from its owning leaf module.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import numpy as np

from voice_typer.server._secrets import redact_secret, redact_url
from voice_typer.server.asr_errors import (
    CloudConfigError,
    CloudConsentRequiredError,
    CloudEmptyResponseError,
    CloudEngineError,
    CloudNetworkError,
)
from voice_typer.server.cloud._defaults import _PROVIDER_DEFAULTS
from voice_typer.server.cloud._providers.gemini import build_gemini_body, build_gemini_url
from voice_typer.server.cloud._retry import _cloud_http_error_class, _parse_retry_after
from voice_typer.server.cloud._transport import _audio_to_wav_bytes, _read_capped
from voice_typer.server.i18n import DEFAULT_LOCALE
from voice_typer.server.retry import delay_for_attempt, sleep_interruptible

log = logging.getLogger(__name__)


class CloudEngine:
    """Cloud ASR engine implementing TranscriberProtocol.

        Supports OpenAI, Groq, Deepgram, and Gemini APIs (all OpenAI-compatible
        except Deepgram which uses its own format and Gemini which uses
        generateContent with inline base64 audio).

    each CloudEngine instance has a ``consent_given``
        flag that must be True before any audio is sent to the provider.
        The flag is set from the per-provider consent field on the Config
        dataclass (``cloud_openai_consent``, ``cloud_groq_consent``,
        ``cloud_deepgram_consent``, ``cloud_gemini_consent``).  When consent is False, ``is_loaded``
        returns False and ``transcribe`` raises a ConsentRequiredError so
        the IPC layer can surface a consent dialog to the renderer.
    """

    # Per-request timeout for cloud HTTP calls. Reduced from 30s to 10s
    _REQUEST_TIMEOUT_SECONDS: float = 10.0
    # Gemini transcriptions average ~17s per 8s clip, so the shared 10s
    # timeout aborts every call. Gemini path uses its own 120s budget.
    _GEMINI_REQUEST_TIMEOUT_SECONDS: float = 120.0

    def __init__(
        self,
        provider: str,
        api_key: str,
        api_url: str | None = None,
        model: str | None = None,
        language: str = DEFAULT_LOCALE,
        consent_given: bool = False,
        local_engine_factory: Callable[..., Any] | None = None,
    ):
        self.provider = provider
        self.api_key = api_key
        self.language = language
        # per-instance consent flag.  Must be True before
        self.consent_given = bool(consent_given)
        self._lock = threading.RLock()

        defaults = _PROVIDER_DEFAULTS.get(provider, {})
        self.api_url = api_url or defaults.get("url", "")
        self.model_name = model or defaults.get("model", "")

        self._loaded = True  # Cloud engines don't need local model loading

        # Optional factory that constructs the local whisper
        self._local_engine_factory = local_engine_factory

        # Abort token shared by the dictation pipeline's cancel path
        self._abort_event = threading.Event()

    @property
    def is_loaded(self) -> bool:
        # consent is required for the engine to be
        return self._loaded and bool(self.api_key) and self.consent_given

    def load(self, progress_callback=None) -> None:
        """No-op for cloud engines, no local model to load."""
        if progress_callback:
            progress_callback("Cloud engine ready")
        self._loaded = True

    def request_abort(self) -> None:
        """Signal the in-flight HTTP request + retry loop to abort.

        Called from the dictation pipeline's abort watcher (which
        monitors ``recording._cancelled_cycle_ids``) when the user
        hits ESC or the watchdog force-recovers a stuck cloud call.
        Sets a ``threading.Event`` that the retry loop checks at the
        top of each iteration AND inside every retry backoff /
        Retry-After wait (``Event.wait(timeout=...)`` returns early
        when the event is set, so an abort during a 60s rate-limit
        wait takes effect immediately). The current HTTP request
        cannot be interrupted from Python (the thread is blocked in
        C-level ``recv``), but with the per-request timeout reduced to
        10s the worst-case latency before the abort takes effect is
        now bounded to ~10s, down from ~30s.
        """
        self._abort_event.set()

    def clear_abort(self) -> None:
        """Clear the abort token at the start of a fresh transcription cycle.

        Called by the dictation pipeline before each transcribe so a
        stale abort from the previous cycle (e.g. the user hit ESC,
        aborted, then started a new recording) does NOT suppress the
        new transcription.
        """
        self._abort_event.clear()

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio via cloud API.

        refuses to send audio if consent hasn't been
                given.  Raises CloudConsentRequiredError (a subclass of
                ConsentRequiredError / RuntimeError so existing catch clauses
                still work) so the IPC layer can detect this case and show the
                consent dialog.
        """
        if not self.consent_given:
            raise CloudConsentRequiredError(
                f"Cloud {self.provider} consent not given, refusing to send audio.",
                provider=self.provider,
            )
        if not self.is_loaded:
            # Typed ``CloudConfigError`` (was generic
            raise CloudConfigError("Cloud engine not configured (missing API key)")
        if len(audio) == 0:
            return ""
        # Honor a pre-set abort (e.g. ESC hit during audio finalization,
        if self._abort_event.is_set():
            log.info("[CLOUD] %s transcribe skipped, abort requested before first request", self.provider)
            return ""
        return self._send_request(audio)

    def transcribe_with_fallback(
        self,
        audio: np.ndarray,
        local_engine=None,
        audio_stats: tuple[float, float, float] | None = None,
    ) -> str:
        """Delegate to :func:`voice_typer.server.cloud._fallback.fall_back_to_local`."""
        return fall_back_to_local(self, audio, local_engine, audio_stats)


    def unload(self) -> None:
        """No-op for cloud engines."""
        self._loaded = False

    @property
    def device_info(self) -> str:
        return f"cloud/{self.provider}"

    @property
    def loaded_via(self) -> str:
        return f"cloud/{self.provider}/{self.model_name}"

    def _send_request(self, audio: np.ndarray) -> str:
        """Send audio to the cloud API and return transcribed text."""
        wav_bytes = _audio_to_wav_bytes(audio)
        filename = "audio.wav"

        if self.provider == "deepgram":
            return self._send_deepgram(wav_bytes)
        if self.provider == "gemini":
            return self._send_gemini(wav_bytes)
        return self._send_openai_compatible(wav_bytes, filename)

    # All three send paths share the retry skeleton below.
    def _transcribe_with_retry(
        self,
        provider: str,
        request_factory: Callable[[], Request],
        parse_response: Callable[[bytes], str],
        timeout: float | None = None,
    ) -> str:
        """Shared retry/backoff skeleton for cloud transcription HTTP calls.

        Honors the per-engine ``_abort_event`` (checked before each
        attempt AND interruptibly during every Retry-After / backoff
        wait, so an ESC-abort takes effect mid-wait instead of at the
        top of the next attempt), retries 429 once honoring
        ``Retry-After`` (capped at 60s by ``_parse_retry_after``), and
        applies exponential backoff
        (0.5s, 1.0s, 2.0s) for transient ``URLError``s. Non-retryable
        ``HTTPError``s and the catch-all ``Exception`` branch raise
        typed ``CloudEngineError`` subclasses via
        ``_cloud_http_error_class`` so the IPC layer can map them to
        distinct ``server.cloud_*`` codes.
        """
        max_retries = 3
        retried_429 = False
        for attempt in range(max_retries):
            # Check the abort token BEFORE each (potentially 10s) HTTP
            if self._abort_event.is_set():
                log.info(
                    "[CLOUD] %s abort requested, skipping retry %d/%d",
                    provider,
                    attempt + 1,
                    max_retries,
                )
                raise CloudEngineError(f"{provider} transcription aborted by user")
            req = request_factory()
            try:
                opener = _facade()._opener
                effective_timeout = timeout if timeout is not None else self._REQUEST_TIMEOUT_SECONDS
                with opener.open(req, timeout=effective_timeout) as resp:
                    _verify_cloud_peer(req, resp)
                    # SEC-030: cap response body at 50 MB to prevent
                    raw = _read_capped(resp, max_bytes=50 * 1024 * 1024)
                    if not raw.strip():
                        # HTTP 200 with an empty/whitespace-only body is
                        raise CloudEmptyResponseError(f"{provider} returned HTTP 200 with an empty body")
                    text = parse_response(raw)
                    if not text:
                        # Same anomaly class for a 200 whose JSON is
                        raise CloudEmptyResponseError(f"{provider} returned HTTP 200 with an empty transcript")
                    log.info("[CLOUD] %s transcription: %d chars", provider, len(text))
                    return text
            except CloudEmptyResponseError:
                # Propagate the typed error unchanged, do NOT let the
                raise
            except HTTPError as exc:
                # 429 Too Many Requests is the only retryable 4xx.
                if exc.code == 429 and not retried_429 and attempt < max_retries - 1:
                    retried_429 = True
                    wait = _parse_retry_after(exc.headers.get("Retry-After"))
                    log.warning(
                        "[CLOUD] %s got 429 (attempt %d/%d); honoring Retry-After, retrying once in %.1fs",
                        provider,
                        attempt + 1,
                        max_retries,
                        wait,
                    )
                    # Interruptible wait: ``Event.wait`` returns True the
                    if sleep_interruptible(wait, abort_event=self._abort_event):
                        log.info(
                            "[CLOUD] %s abort requested, aborting Retry-After wait",
                            provider,
                        )
                        raise CloudEngineError(f"{provider} transcription aborted by user") from exc
                    continue
                # Non-retryable HTTPError (4xx other than 429, or 5xx that
                safe_msg = redact_secret(redact_url(str(exc)))
                # Include exc_info so the HTTPError traceback
                log.error(
                    "[CLOUD] %s HTTP %d error (not retried): %s",
                    provider,
                    exc.code,
                    safe_msg,
                    exc_info=True,
                )
                # Raise the typed ``CloudEngineError`` subclass
                err_cls = _cloud_http_error_class(exc.code)
                raise err_cls(f"{provider} API error (HTTP {exc.code})") from exc
            except URLError as exc:
                # URLError that is NOT an HTTPError = transient
                if attempt < max_retries - 1:
                    backoff = delay_for_attempt((0.5, 1.0, 2.0), attempt)
                    log.warning(
                        "[CLOUD] %s attempt %d/%d failed, retrying in %.1fs: %s",
                        provider,
                        attempt + 1,
                        max_retries,
                        backoff,
                        redact_secret(redact_url(str(exc))),
                    )
                    # Interruptible wait (same rationale as the 429 branch
                    if sleep_interruptible(backoff, abort_event=self._abort_event):
                        log.info(
                            "[CLOUD] %s abort requested, aborting backoff wait",
                            provider,
                        )
                        raise CloudEngineError(f"{provider} transcription aborted by user") from exc
                else:
                    safe_msg = redact_secret(redact_url(str(exc)))
                    # Include exc_info so the final URLError
                    log.error(
                        "[CLOUD] %s API error after %d attempts: %s",
                        provider,
                        max_retries,
                        safe_msg,
                        exc_info=True,
                    )
                    # Typed ``CloudNetworkError`` so the IPC layer can
                    raise CloudNetworkError(f"{provider} API error") from exc
            except Exception as exc:
                # use the same ``redact_secret(redact_url(...))``
                safe_msg = redact_secret(redact_url(str(exc)))
                # Include exc_info so the unexpected-exception
                log.error("[CLOUD] %s request failed: %s", provider, safe_msg, exc_info=True)
                # include the underlying error in the user-facing
                raise CloudEngineError(f"{provider} request failed: {safe_msg}") from exc
        # Should not reach here, but just in case
        raise CloudEngineError(f"{provider} request failed after {max_retries} attempts")

    def _send_openai_compatible(self, wav_bytes: bytes, filename: str) -> str:
        """Delegate to :func:`voice_typer.server.cloud._sendpaths._send_openai_compatible`."""
        return _send_openai_compatible(self, wav_bytes, filename)

    def _send_deepgram(self, wav_bytes: bytes) -> str:
        """Delegate to :func:`voice_typer.server.cloud._sendpaths._send_deepgram`."""
        return _send_deepgram(self, wav_bytes)

    def _send_gemini(self, wav_bytes: bytes) -> str:
        """Delegate to :func:`voice_typer.server.cloud._sendpaths._send_gemini`."""
        return _send_gemini(self, wav_bytes)

    def _build_multipart_body(self, wav_bytes: bytes, filename: str, boundary: str):
        """Delegate to :func:`voice_typer.server.cloud._sendpaths._build_multipart_body`."""
        return _build_multipart_body(self, wav_bytes, filename, boundary)

    def _multipart_parts(self, wav_bytes: bytes, filename: str, boundary: str) -> list[bytes]:
        """Delegate to :func:`voice_typer.server.cloud._sendpaths._multipart_parts`."""
        return _multipart_parts(self, wav_bytes, filename, boundary)

    def test_connection(self) -> tuple[bool, str]:
        """Test the API connection. Returns (success, message).

        Redaction contract: any secret-looking substring is stripped from the
        returned message so a leaked key in an exception string does
        not propagate to the UI.

        SEC-011: previously this method sent the API key in a HEAD
        request to the user-supplied ``api_url``.  Combined with a
        SEC-002 endpoint-swap, that would leak the key to an
        attacker-controlled URL.  It also probed OpenAI's
        ``/v1/audio/transcriptions`` endpoint with HEAD, which
        returns 405 Method Not Allowed, so the test always reported
        failure even with valid credentials.

        The fix: probe a provider-known endpoint with a GET (or
        rather, just attempt a real transcription-shaped request and
        check for a 401/403 response, which proves the key was
        accepted by the auth layer even if the request body was
        empty).  We never send the API key to a URL the user didn't
        configure.
        """
        # No cloud interaction without consent (ADR-0016 Design Rule 1).
        if not self.consent_given:
            return False, "Cloud consent not given, refusing to test connection"

        if not self.api_key:
            return False, "API key not configured"

        try:
            # Opt in to allow_loopback_http=True: see the
            _facade().assert_url_allowed(
                self.api_url,
                field_name="cloud_api_url",
                client_name=f"cloud/{self.provider}",
                allow_loopback_http=True,
            )
        except ValueError as exc:
            return False, str(exc)

        # SEC-011: probe by sending an empty audio body to the real
        try:
            # Build a minimal multipart body with empty audio so the
            if self.provider == "deepgram":
                # Deepgram: send empty WAV bytes; expect 400 (bad audio)
                empty_wav = _audio_to_wav_bytes(np.zeros(0, dtype=np.float32))
                headers = {
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "audio/wav",
                }
                req = Request(self.api_url, data=empty_wav, headers=headers, method="POST")
            elif self.provider == "gemini":
                # Gemini: empty-audio POST, expect 400 = reachable.
                url = build_gemini_url(self.api_url, self.model_name)
                empty_wav = _audio_to_wav_bytes(np.zeros(0, dtype=np.float32))
                body = build_gemini_body(empty_wav)
                headers = {
                    "X-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                }
                req = Request(url, data=body, headers=headers, method="POST")
            else:
                # OpenAI-compatible: send empty multipart body.
                boundary = "----LausuTestBoundary"
                body = (
                    f"--{boundary}\r\n"
                    'Content-Disposition: form-data; name="model"\r\n\r\n'
                    f"{self.model_name}\r\n"
                    f"--{boundary}--\r\n"
                ).encode()
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                }
                req = Request(self.api_url, data=body, headers=headers, method="POST")
            # SEC-audit-006 (Round 0 forward-port): use the shared
            opener = _facade()._opener
            with opener.open(req, timeout=self._REQUEST_TIMEOUT_SECONDS) as resp:
                return True, f"Connected to {self.provider} (status {resp.status})"
        except Exception as exc:
            # A 400/401/403/422 error means the server is reachable
            msg = str(exc)
            # urllib.error.HTTPError carries the status code
            status = getattr(exc, "code", None)
            if status is not None:
                # HTTP error, server is reachable.  401/403 = key
                if status in (401, 403):
                    return False, f"Connected to {self.provider}, but API key was rejected (HTTP {status})"
                # A 5xx means the server is reachable but is itself
                if 500 <= status < 600:
                    return True, (
                        f"Connected to {self.provider}, but server returned "
                        f"HTTP {status}, provider may be temporarily unavailable"
                    )
                # Any other HTTP error means the server is up and
                return True, f"Connected to {self.provider} (HTTP {status})"
            # Chain ``redact_url`` (strips URL userinfo +
            return False, f"Connection failed: {redact_secret(redact_url(msg))}"

# Facade re-exports: the provider send paths (``_sendpaths``) and the
# cloud-to-local fallback policy (``_fallback``) keep resolving through this
# module, so every existing import path stays intact.
from voice_typer.server.cloud._fallback import (  # noqa: E402,F401  # facade re-export
    _fallback_kind,
    fall_back_to_local,
)
from voice_typer.server.cloud._sendpaths import (  # noqa: E402,F401  # facade re-export
    _build_multipart_body,
    _facade,
    _multipart_parts,
    _send_deepgram,
    _send_gemini,
    _send_openai_compatible,
    _verify_cloud_peer,
)
