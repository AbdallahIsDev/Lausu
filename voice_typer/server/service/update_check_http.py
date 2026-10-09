"""Manifest fetch + SSRF-gated HTTP transport for the pack update check.

Extracted from ``update_check.py``: candidate URL resolution, the
SSRF-revalidating redirect handler, the bounded body read, and schema
validation of the remote ``pack-manifest.json``.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from collections.abc import Callable

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.branding import APP_NAME
from voice_typer.server.service import offline_pack
from voice_typer.server.service.offline_pack import (
    OfflinePackManifest,
    assert_offline_pack_url_allowed,
    proxy_env,
)
from voice_typer.server.service.update_check_urls import (
    MAX_MANIFEST_BYTES,
    pack_manifest_url_candidates,
)

log = logging.getLogger("voice_typer.server.service.update_check")

# The default transport is patched on the facade (``update_check._http_get_manifest``)
# by tests, so it MUST be resolved through the facade at call time, never by value.
_facade = lazy_module("voice_typer.server.service.update_check")


class _SSRFAwareRedirectHandler(urllib.request.HTTPRedirectHandler):
    """``HTTPRedirectHandler`` subclass that re-validates each 3xx hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Re-validate ``newurl`` through :func:`assert_offline_pack_url_allowed`."""
        try:
            assert_offline_pack_url_allowed(newurl)
        except ValueError as exc:
            # Convert ``ValueError`` (raised by ``assert_url_allowed``)
            raise RuntimeError(
                f"SSRF block on redirect target (refusing to follow "
                f"{code} redirect to a non-allowlisted / private IP "
                f"target): {exc}"
            ) from exc
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# Upper bound on the launch-time remote-manifest fetch. The interactive
LAUNCH_MANIFEST_TIMEOUT_S = 8.0


def _http_get_manifest(url: str, *, max_bytes: int = MAX_MANIFEST_BYTES, timeout: float = 30.0) -> str:
    """Default HTTP transport, fetches *url* and returns the body as text."""
    proxies = proxy_env()
    if proxies:
        proxy_handler = urllib.request.ProxyHandler(proxies)
        opener = urllib.request.build_opener(_SSRFAwareRedirectHandler(), proxy_handler)
    else:
        opener = urllib.request.build_opener(_SSRFAwareRedirectHandler())
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"{APP_NAME}/pack-update-checker", "Accept": "application/json"},
    )
    with opener.open(req, timeout=timeout) as resp:
        status = resp.getcode()
        if status != 200:
            raise RuntimeError(f"unexpected HTTP status {status} for {url}")
        # Read in chunks; abort if the running total exceeds max_bytes.
        total = 0
        chunks: list[bytes] = []
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise RuntimeError(
                    f"manifest exceeds max_bytes={max_bytes} "
                    f"(read {total} bytes so far), refusing to continue "
                    f"reading to prevent unbounded memory consumption"
                )
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace")


def _is_missing_manifest_404(exc: BaseException) -> bool:
    """True when *exc* is an HTTP 404 from the manifest fetch."""
    if getattr(exc, "code", None) == 404:
        return True
    text = str(exc)
    return "HTTP Error 404" in text or "HTTP status 404" in text


def fetch_remote_manifest(
    url: str,
    *,
    http_get: Callable[..., str] | None = None,
    max_bytes: int = MAX_MANIFEST_BYTES,
    timeout: float = 30.0,
    failure_info: dict | None = None,
) -> OfflinePackManifest | None:
    """Fetch + validate the remote ``pack-manifest.json``."""
    # SSRF gate first, refuse to fetch from a private/disallowed host
    def _record(*, not_found: bool, error: str = "") -> None:
        if failure_info is not None:
            failure_info["not_found"] = not_found
            if error:
                failure_info["error"] = error
    try:
        assert_offline_pack_url_allowed(url)
    except ValueError as exc:
        log.warning("[UPDATE] SSRF block on manifest URL: %s", exc)
        _record(not_found=False, error=str(exc))
        return None

    if http_get is None:
        http_get = _facade._http_get_manifest
    try:
        # The default transport accepts a ``timeout``; injected test
        if http_get is _facade._http_get_manifest:
            body = http_get(url, max_bytes=max_bytes, timeout=timeout)
        else:
            body = http_get(url, max_bytes=max_bytes)
    except (OSError, RuntimeError) as exc:
        # Strip the scheme so the line stays short; host + path are the
        if _is_missing_manifest_404(exc):
            # DEBUG: an unpublished manifest is the steady state (no
            # release cut yet), not news worth an INFO line per URL.
            log.debug(
                "[UPDATE] remote pack manifest not published yet (%s): %s",
                exc,
                url.split("://", 1)[-1],
            )
            _record(not_found=True, error=str(exc))
        else:
            log.warning(
                "[UPDATE] Manifest fetch failed (%s): %s",
                exc,
                url.split("://", 1)[-1],
            )
            _record(not_found=False, error=str(exc))
        return None
    except Exception as exc:
        log.debug("[UPDATE] candidate %s raised", url, exc_info=True)
        _record(not_found=_is_missing_manifest_404(exc), error=str(exc))
        return None

    # Parse + validate via the shared schema validator (the SAME
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        log.warning("[UPDATE] remote manifest from %s is not valid JSON", url)
        _record(not_found=False, error="invalid JSON")
        return None
    manifest = offline_pack.validate_offline_pack_manifest_dict(data, source=url)
    if manifest is None:
        log.warning("[UPDATE] remote manifest from %s failed schema validation", url)
        _record(not_found=False, error="schema validation failed")
        return None
    return manifest


def fetch_remote_manifest_first_success(
    urls: list[str] | None = None,
    *,
    http_get: Callable[..., str] | None = None,
    max_bytes: int = MAX_MANIFEST_BYTES,
    timeout: float = 30.0,
    failure_info: dict | None = None,
) -> tuple[OfflinePackManifest | None, str | None]:
    """Try each candidate URL until one returns a valid manifest.

    Returns ``(manifest, url)`` or ``(None, None)``. Stops at the first
    schema-valid hit so a stale rolling-tag copy cannot override a fresher
    ``latest`` manifest that is actually present.
    """
    candidates = urls if urls is not None else pack_manifest_url_candidates()
    not_found_flags: list[bool] = []
    for url in candidates:
        try:
            info: dict = {}
            manifest = fetch_remote_manifest(
                url, http_get=http_get, max_bytes=max_bytes, timeout=timeout, failure_info=info
            )
        except Exception:  # defensive: one bad candidate must not abort the list
            log.debug("[UPDATE] candidate %s raised", url, exc_info=True)
            not_found_flags.append(False)
            continue
        if manifest is not None:
            return manifest, url
        not_found_flags.append(bool(info.get("not_found", False)))
    if failure_info is not None:
        failure_info["all_not_found"] = bool(not_found_flags) and all(not_found_flags)
    return None, None
