"""Shared HTTP plumbing for remote provider clients.

Reuses the repository's secure opener (no redirect following, validated peer
IPs) and maps transport failures onto the existing ``Cloud*`` error classes so
every IPC/UI error path stays shared.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from voice_typer.server._http_safety import build_secure_opener
from voice_typer.server._secrets import assert_url_allowed, redact_secret, redact_url
from voice_typer.server.asr_errors import (
    CloudAuthError,
    CloudEmptyResponseError,
    CloudEngineError,
    CloudNetworkError,
    CloudRateLimitError,
    CloudServerError,
)
from voice_typer.server.model_providers.errors import ProviderRuntimeError

log = logging.getLogger(__name__)

#: Cap on any provider response body (SEC-030 parity with the cloud engine).
MAX_RESPONSE_BYTES = 50 * 1024 * 1024

_default_opener = build_secure_opener()

Opener = Any


def secure_opener() -> Opener:
    return _default_opener


def _validate_provider_url(
    url: str,
    *,
    provider: str,
    field_name: str,
    allow_loopback_http: bool,
) -> None:
    """Reject an unusable endpoint as a typed provider error.

    A bare ``ValueError`` here would reach the dispatcher's catch-all and be
    reported as ``server.internal_error`` with no actionable message.
    """
    try:
        assert_url_allowed(
            url,
            field_name=field_name,
            client_name=provider,
            allow_loopback_http=allow_loopback_http,
        )
    except ValueError as exc:
        raise ProviderRuntimeError(str(exc), provider=provider) from exc


def read_capped(resp: Any, max_bytes: int = MAX_RESPONSE_BYTES) -> bytes:
    """Read at most ``max_bytes`` from a response object."""
    chunks: list[bytes] = []
    remaining = max_bytes
    while remaining > 0:
        chunk = resp.read(min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def map_http_error(exc: HTTPError, provider: str) -> CloudEngineError:
    """Map an HTTP status onto the existing typed cloud error classes."""
    if exc.code in (401, 403):
        return CloudAuthError(f"{provider} rejected the API key (HTTP {exc.code})")
    if exc.code == 429:
        return CloudRateLimitError(f"{provider} rate limited the request")
    if 500 <= exc.code < 600:
        return CloudServerError(f"{provider} server error (HTTP {exc.code})")
    return CloudEngineError(f"{provider} API error (HTTP {exc.code})")


def request_json(
    url: str,
    *,
    provider: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
    opener: Opener | None = None,
    field_name: str = "provider_api_url",
    allow_loopback_http: bool = True,
) -> Any:
    """Perform one JSON request against a validated provider URL."""
    _validate_provider_url(
        url,
        provider=provider,
        field_name=field_name,
        allow_loopback_http=allow_loopback_http,
    )
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    merged = {"Content-Type": "application/json", "Accept": "application/json", **(headers or {})}
    req = Request(url, data=payload, headers=merged, method=method)
    active = opener or secure_opener()
    try:
        with active.open(req, timeout=timeout) as resp:
            raw = read_capped(resp)
    except HTTPError as exc:
        log.warning(
            "[PROVIDERS] %s HTTP %d: %s",
            provider,
            exc.code,
            redact_secret(redact_url(str(exc))),
        )
        raise map_http_error(exc, provider) from exc
    except URLError as exc:
        raise CloudNetworkError(f"{provider} is unreachable: {redact_secret(redact_url(str(exc)))}") from exc
    except Exception as exc:
        raise CloudEngineError(f"{provider} request failed: {redact_secret(str(exc))}") from exc
    if not raw.strip():
        raise CloudEmptyResponseError(f"{provider} returned an empty body")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise CloudEngineError(f"{provider} returned invalid JSON") from exc


def iter_sse_json(resp: Any, *, provider: str) -> Iterator[dict[str, Any]]:
    """Yield decoded JSON objects from a ``text/event-stream`` response."""
    while True:
        line = resp.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace").strip()
        if not text or text.startswith(":"):
            continue
        if not text.startswith("data:"):
            continue
        data = text[len("data:") :].strip()
        if data == "[DONE]":
            break
        try:
            yield json.loads(data)
        except json.JSONDecodeError:
            log.debug("[PROVIDERS] %s skipping malformed SSE chunk", provider)


def open_stream(
    url: str,
    *,
    provider: str,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 120.0,
    opener: Opener | None = None,
    field_name: str = "provider_api_url",
) -> Any:
    """Open a streaming request and return the live response object."""
    _validate_provider_url(
        url,
        provider=provider,
        field_name=field_name,
        allow_loopback_http=True,
    )
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    merged = {"Content-Type": "application/json", "Accept": "text/event-stream", **(headers or {})}
    req = Request(url, data=payload, headers=merged, method="POST")
    active = opener or secure_opener()
    try:
        return active.open(req, timeout=timeout)
    except HTTPError as exc:
        raise map_http_error(exc, provider) from exc
    except URLError as exc:
        raise CloudNetworkError(f"{provider} is unreachable: {redact_secret(redact_url(str(exc)))}") from exc


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_stream_factory(*args: Any, **kwargs: Any) -> Callable[..., Any]:
    """Small seam so tests can inject a fake stream opener."""

    def _factory(**overrides: Any) -> Any:
        merged = {**kwargs, **overrides}
        return open_stream(*args, **merged)

    return _factory


__all__ = [
    "MAX_RESPONSE_BYTES",
    "bearer",
    "iter_sse_json",
    "open_stream",
    "read_capped",
    "request_json",
    "secure_opener",
]
