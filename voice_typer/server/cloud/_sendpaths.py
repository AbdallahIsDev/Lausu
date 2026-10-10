"""Provider send paths and the shared retry skeleton for the cloud engine.

One concern only: shape one provider request (OpenAI-compatible, Deepgram,
Gemini) and drive it through the shared retry/backoff skeleton, including the
peer-IP pin that keeps a validated URL from being answered by a different
host. Everything provider-stateless lives in the sibling leaf modules
(:mod:`._transport`, :mod:`._retry`, :mod:`._defaults`, :mod:`._providers.*`).

FACADE-NAMESPACE PATCH CONTRACT: tests and production patch engine-adjacent
singletons through the ``cloud_engines`` facade namespace
(``setattr(cloud_engines, "_opener", mock)``,
``patch("voice_typer.server.cloud_engines.assert_url_allowed")``). This module
therefore resolves ``_opener`` and ``assert_url_allowed`` from that facade at
call time (see :func:`_facade`) instead of importing them statically.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, Protocol
from urllib.request import Request

from voice_typer.server.asr_errors import CloudNetworkError
from voice_typer.server.cloud._providers.deepgram import build_listen_url
from voice_typer.server.cloud._providers.gemini import (
    build_gemini_body,
    build_gemini_url,
    parse_gemini_transcript,
)
from voice_typer.server.cloud._providers.openai import build_multipart_body, build_multipart_parts

log = logging.getLogger(__name__)


class _SendPathHost(Protocol):
    """Engine surface the provider send paths drive (owned by ``CloudEngine``)."""

    api_url: str
    api_key: str
    provider: str
    model_name: str
    language: str
    _GEMINI_REQUEST_TIMEOUT_SECONDS: float

    def _transcribe_with_retry(
        self,
        provider: str,
        request_factory: Callable[[], Request],
        parse_response: Callable[[bytes], str],
        timeout: float | None = None,
    ) -> str: ...

    def _build_multipart_body(self, wav_bytes: bytes, filename: str, boundary: str) -> Any: ...


def _facade():
    """Resolve the compatibility facade namespace at call time.

    The facade module (``voice_typer.server.cloud_engines``) owns the
    engine-adjacent singletons tests rebind to steer the engine
    (``_opener``, ``assert_url_allowed``). Reading them through the
    facade at call time, instead of importing them at module level —
    keeps that contract intact now that the class body lives in this
    leaf. Call-time-only import: the facade imports this package at
    module level, so the facade is always fully initialized by the
    time an engine method runs (no import cycle).
    """
    from voice_typer.server import cloud_engines

    return cloud_engines


def _verify_cloud_peer(req: Request, resp: object) -> None:
    """Verify the connected peer IP matches the validated URL IPs."""
    try:
        facade = _facade()
        expected = facade.resolve_allowed_url_ips(
            req.full_url,
            field_name="cloud_api_url",
            client_name="cloud",
            allow_loopback_http=True,
        )
    except Exception:
        log.debug("[CLOUD] peer-IP pin lookup failed", exc_info=True)
        return
    try:
        raw = getattr(resp, "fp", None)
        sock = getattr(raw, "raw", None)
        sock = getattr(sock, "_sock", sock)
        peer = sock.getpeername()[0] if hasattr(sock, "getpeername") else None
    except Exception:
        log.debug("[CLOUD] peer-IP read failed", exc_info=True)
        return
    if peer is None:
        return
    try:
        facade.verify_peer_ip_allowed(peer, expected, host=req.host)
    except ValueError as exc:
        log.exception("[CLOUD] peer IP %r outside validated set, refusing", peer)
        raise CloudNetworkError("cloud peer IP outside validated set") from exc


def _send_openai_compatible(engine: _SendPathHost, wav_bytes: bytes, filename: str) -> str:
    """Send request to OpenAI-compatible API (OpenAI, Groq).

    URL allowlist: asserts the configured ``api_url`` is in the
    trusted-host allowlist before sending any audio.  This closes
    the SEC-002 endpoint-swap vector at the cloud-engine layer:
    even if an attacker finds another path to write
    ``config.cloud_api_url``, this engine refuses to send audio
    to an untrusted host.

    PERF: exponential backoff retry (3 attempts) for transient
    network errors. HTTP goes through the shared module-level
    OpenerDirector (built once, so the handler chain, redirect
    refusal, plaintext-HTTP refusal, is not reconstructed per
    request); note the stdlib opener does NOT pool connections —
    each request opens a fresh TCP/TLS connection and sends
    ``Connection: close``.

    Thin wrapper around ``_transcribe_with_retry``, supplies the
    OpenAI-specific request factory (multipart body, rebuilt per
    attempt because ``_StreamingMultipartBody`` carries internal
    state) and the OpenAI response parser (``result["text"]``).
    """
    # Defense-in-depth: SEC-002 already validates URL scheme at
    _facade().assert_url_allowed(
        engine.api_url,
        field_name="cloud_api_url",
        client_name=f"cloud/{engine.provider}",
        allow_loopback_http=True,
    )

    boundary = "----LausuBoundary7MA4YWxkTrZu0gW"

    def _build_request() -> Request:
        # Rebuild `body` and `req` INSIDE the retry loop.
        body = engine._build_multipart_body(wav_bytes, filename, boundary)
        headers = {
            "Authorization": f"Bearer {engine.api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            # PERF: pass Content-Length explicitly so urllib
            "Content-Length": str(len(body)),
        }
        return Request(engine.api_url, data=body, headers=headers, method="POST")

    def _parse(raw: bytes) -> str:
        result = json.loads(raw.decode("utf-8"))
        return result.get("text", "").strip()

    return engine._transcribe_with_retry(engine.provider, _build_request, _parse)


def _send_deepgram(engine: _SendPathHost, wav_bytes: bytes) -> str:
    """Send request to Deepgram API.

            Same URL allowlist + log redaction as the
            OpenAI-compatible path.

            SEC-005: query parameters (model, language) are validated
            and URL-encoded by the Deepgram provider module
            (``voice_typer.server.cloud._providers.deepgram``) to prevent
            parameter injection via crafted config values.

    PERF: exponential backoff retry (3 attempts) for
    transient network errors, matching the OpenAI-compatible path
    (now shared via ``_transcribe_with_retry``).
    """
    # Opt in to allow_loopback_http=True: see the
    _facade().assert_url_allowed(
        engine.api_url,
        field_name="cloud_api_url",
        client_name="cloud/deepgram",
        allow_loopback_http=True,
    )

    # SEC-005: the provider module escapes special characters in the
    url = build_listen_url(engine.api_url, engine.model_name, engine.language)

    # Deepgram's body is a plain ``bytes`` object (no internal
    def _build_request() -> Request:
        headers = {
            "Authorization": f"Token {engine.api_key}",
            "Content-Type": "audio/wav",
        }
        return Request(url, data=wav_bytes, headers=headers, method="POST")

    def _parse(raw: bytes) -> str:
        result = json.loads(raw.decode("utf-8"))
        # Deepgram response format
        channels = result.get("results", {}).get("channels", [])
        if channels:
            alternatives = channels[0].get("alternatives", [])
            if alternatives:
                return alternatives[0].get("transcript", "").strip()
        return ""

    return engine._transcribe_with_retry(engine.provider, _build_request, _parse)


def _send_gemini(engine: _SendPathHost, wav_bytes: bytes) -> str:
    """Send request to Gemini generateContent API.

    Same URL allowlist + retry skeleton as the other providers.
    Key travels in the ``X-goog-api-key`` header, never ``?key=``.
    Uses ``_GEMINI_REQUEST_TIMEOUT_SECONDS`` (120s): measured
    transcriptions take ~17s per 8s clip, the shared 10s aborts
    every call.
    """
    _facade().assert_url_allowed(
        engine.api_url,
        field_name="cloud_api_url",
        client_name="cloud/gemini",
        allow_loopback_http=True,
    )
    url = build_gemini_url(engine.api_url, engine.model_name)

    def _build_request() -> Request:
        body = build_gemini_body(wav_bytes)
        headers = {
            "X-goog-api-key": engine.api_key,
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        return Request(url, data=body, headers=headers, method="POST")

    return engine._transcribe_with_retry(
        engine.provider,
        _build_request,
        parse_gemini_transcript,
        timeout=engine._GEMINI_REQUEST_TIMEOUT_SECONDS,
    )


def _build_multipart_body(engine: _SendPathHost, wav_bytes: bytes, filename: str, boundary: str):
    """Build multipart/form-data body for OpenAI-compatible APIs.

    PERF: returns a streaming ``_StreamingMultipartBody`` file-like
    object (defined in ``voice_typer.server.cloud._transport``) that
    yields the pre-built parts as ~64 KB chunks on demand, avoiding a
    SECOND full-body copy, the naive ``b"".join(parts)`` built one
    contiguous ~5.2 MB ``bytes`` object next to the WAV that is
    already resident in ``parts``; ``Content-Length`` is computed
    upfront via ``__len__`` so the server knows the total size
    without chunked transfer encoding.
    Shaping itself lives in
    ``voice_typer.server.cloud._providers.openai``.
    """
    return build_multipart_body(wav_bytes, filename, boundary, engine.model_name, engine.language)


def _multipart_parts(engine: _SendPathHost, wav_bytes: bytes, filename: str, boundary: str) -> list[bytes]:
    """Return the ordered list of byte chunks that compose the body.

    Shaping lives in ``voice_typer.server.cloud._providers.openai``.
    """
    return build_multipart_parts(wav_bytes, filename, boundary, engine.model_name, engine.language)
