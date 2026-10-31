"""Backend thumbnail fetch for the media completion event (ADR-0023).

The renderer's CSP is ``img-src 'self' data:``, so a remote preview URL cannot
be rendered directly — and widening CSP to ``https:`` would let an extractor
trigger arbitrary remote image loads (tracking pixels). The thumbnail is
therefore fetched here, size- and type-capped, and shipped inline as a data
URL. Every failure is ``None``: a preview must never fail a job.
"""

from __future__ import annotations

import base64
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse

from voice_typer.server.security.url_allowlist import _resolve_public_ips

log = logging.getLogger(__name__)

TIMEOUT_SECONDS: float = 5.0
MAX_REDIRECTS: int = 2
MAX_BYTES: int = 400 * 1024
#: Only real image types are inlined; anything else (HTML error pages, SVG
#: with script, TIFF) is refused rather than handed to an <img>.
ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})

_USER_AGENT = "Mozilla/5.0 (compatible; media-thumbnail-fetcher)"


def _is_public_http_url(url: str, *, resolve) -> bool:
    """http(s) only, and the host must resolve to public addresses."""
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        resolve(parsed.hostname)
    except Exception:  # noqa: BLE001, a refused host IS the answer
        return False
    return True


class _BoundedRedirects(urllib.request.HTTPRedirectHandler):
    """Follow at most ``MAX_REDIRECTS`` hops, each still a public http(s) URL."""

    max_redirections = MAX_REDIRECTS

    def __init__(self, resolve) -> None:
        super().__init__()
        self._resolve = resolve

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, signature is urllib's
        if not _is_public_http_url(newurl, resolve=self._resolve):
            raise ValueError(f"thumbnail redirect refused: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener(resolve) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_BoundedRedirects(resolve))


def fetch_thumbnail_data_url(url: str | None, *, resolve=None, opener=None) -> str | None:
    """Fetch ``url`` and return a ``data:<mime>;base64,...`` string, else ``None``."""
    if not url:
        return None
    resolve = resolve or _resolve_public_ips
    if not _is_public_http_url(url, resolve=resolve):
        log.debug("[MEDIA] thumbnail refused (not a public http(s) URL)")
        return None
    try:
        client = opener if opener is not None else _build_opener(resolve)
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with client.open(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = str(response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                log.debug("[MEDIA] thumbnail refused (content-type=%s)", content_type or "missing")
                return None
            body = response.read(MAX_BYTES + 1)
        if not body or len(body) > MAX_BYTES:
            log.debug("[MEDIA] thumbnail refused (bytes=%d)", len(body))
            return None
        encoded = base64.b64encode(body).decode("ascii")
        return f"data:{content_type};base64,{encoded}"
    except (urllib.error.URLError, ValueError, OSError) as exc:
        log.debug("[MEDIA] thumbnail unavailable: %s", type(exc).__name__)
        return None
