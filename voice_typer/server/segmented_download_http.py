"""HTTP transport for the segmented downloader.

Opener construction (proxy-aware, redirects disabled), the manual
redirect resolver with auth-stripping on host change, the 1-byte Range
probe for lengthless servers, and the transient-status / Retry-After
helpers. Moved verbatim out of ``voice_typer.server.segmented_download``
(which re-exports every name). ``MAX_REDIRECTS`` is read through the
facade at call time because tests patch ``segmented_download.MAX_REDIRECTS``.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.branding import APP_NAME
from voice_typer.server.retry import (
    parse_retry_after as _shared_parse_retry_after,
)
from voice_typer.server.segmented_download_base import (
    MAX_RETRY_AFTER_S,
    REQUEST_TIMEOUT_S,
    SegmentedDownloadError,
    SegmentRange,
)

_dl = lazy_module("voice_typer.server.segmented_download")


def build_opener(
    proxies: dict[str, str] | None = None,
    *,
    user_agent: str,
) -> Any:
    """Build a urllib opener honoring proxies (same convention as the
    update-checker's transport: ``offline_pack.proxy_env()``)."""
    handlers: list[Any] = []
    if proxies:
        handlers.append(urllib.request.ProxyHandler(proxies))
    handlers.append(_NoAutoRedirectHandler())
    opener = urllib.request.build_opener(*handlers)
    opener.addheaders = [("User-Agent", user_agent)]
    return opener


class _NoAutoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Disable urllib's automatic redirect following."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN202
        return None


def _strip_auth_on_host_change(headers: dict, old_host: str, new_host: str) -> dict:
    if old_host.lower() != new_host.lower():
        return {k: v for k, v in headers.items() if k.lower() != "authorization"}
    return dict(headers)


def resolve_download(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_s: float = REQUEST_TIMEOUT_S,
    opener_factory: Callable[[], Any] | None = None,
) -> tuple[str, int | None, str | None]:
    """Resolve ``url`` to (final_url, total_size, etag)."""
    from urllib.parse import urlparse

    opener = opener_factory() if opener_factory else build_opener(None, user_agent=f"{APP_NAME}/segmented-downloader")
    current = url
    base_headers = dict(headers or {})
    for _ in range(_dl.MAX_REDIRECTS + 1):
        parsed = urlparse(current)
        if parsed.scheme.lower() != "https":
            raise SegmentedDownloadError(f"refusing non-https redirect target: {current}")
        head_req = _make_request(current, base_headers, method="HEAD")
        try:
            with opener.open(head_req, timeout=timeout_s) as resp:
                status = _status_of(resp)
                if status in (301, 302, 303, 307, 308):
                    location = resp.getheader("Location")
                    if not location:
                        raise SegmentedDownloadError("redirect without Location")
                    base_headers = _strip_auth_on_host_change(
                        base_headers, parsed.hostname or "", urlparse(location).hostname or ""
                    )
                    current = location
                    continue
                if status != 200:
                    raise SegmentedDownloadError(f"HEAD returned HTTP {status}")
                length = resp.getheader("Content-Length")
                etag = resp.getheader("ETag")
                if length is not None:
                    return current, int(length), etag
                break  # lengthless HEAD → Range probe below
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                location = e.headers["Location"]
                base_headers = _strip_auth_on_host_change(
                    base_headers, parsed.hostname or "", urlparse(location).hostname or ""
                )
                current = location
                continue
            raise SegmentedDownloadError(f"HEAD failed: HTTP {e.code}") from e
    else:
        raise SegmentedDownloadError("too many redirects resolving download URL")

    # Lengthless server: probe with a 1-byte Range request.
    probe_headers = dict(base_headers)
    probe_headers["Range"] = "bytes=0-0"
    probe_req = _make_request(current, probe_headers, method="GET")
    try:
        with opener.open(probe_req, timeout=timeout_s) as resp:
            if _status_of(resp) != 206:
                # The ETag lives on the RESPONSE, not the request headers.
                return current, None, resp.getheader("ETag")
            content_range = resp.getheader("Content-Range", "")
            total = _parse_total_from_content_range(content_range)
            return current, total, resp.getheader("ETag")
    except urllib.error.HTTPError as e:
        raise SegmentedDownloadError(f"Range probe failed: HTTP {e.code}") from e
    return current, None, None


def _make_request(url: str, headers: dict[str, str], method: str = "GET") -> Any:
    req = urllib.request.Request(url, headers=dict(headers), method=method)
    return req


def _status_of(resp: Any) -> int:
    status = getattr(resp, "status", None)
    if status is not None:
        return int(status)
    return int(resp.getcode())


def _parse_total_from_content_range(content_range: str) -> int | None:
    """Parse ``bytes <s>-<e>/<total>`` → total. ``None`` when unparsable."""
    m = re.search(r"bytes\s+\d+-\d+/(\d+)", content_range)
    return int(m.group(1)) if m else None


def _parse_retry_after(value: str | None) -> float:
    # Missing/unparsable headers mean no server-directed wait here.
    return _shared_parse_retry_after(value, default=0.0, cap=MAX_RETRY_AFTER_S)


def _is_transient_http(status: int) -> bool:
    return status == 429 or 500 <= status <= 599


class _RangeUnsupportedError(SegmentedDownloadError):
    """Server answered 200 to a Range request for a partial segment."""


def _body_matches_segment(resp: Any, seg: SegmentRange) -> bool:
    """True when a 200 response body IS the whole requested segment
    (single-segment file served without Range support)."""
    try:
        length = resp.getheader("Content-Length")
        return length is not None and int(length) == seg.length
    except (TypeError, ValueError):
        return False
