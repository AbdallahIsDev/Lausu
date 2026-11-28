"""Source-checkout-only permission for a local HTTP pack fixture server.

Single purpose: let an end-to-end test drive the real downloader against a
loopback server. The opt-in is ignored in every frozen/installed build.
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from voice_typer.server._paths import LOOPBACK_HOSTS
from voice_typer.server.media_ingest.ffmpeg_binaries import is_frozen_build

ENV_LOCAL_PACK_DEV_SERVER = "VT_PACK_DEV_LOCAL_SERVER"


def allow_local_pack_dev_server(url: str) -> bool:
    """True only for opt-in loopback HTTP from a non-frozen interpreter."""
    if is_frozen_build():
        return False
    if os.environ.get(ENV_LOCAL_PACK_DEV_SERVER, "").strip().lower() not in {"1", "true", "yes"}:
        return False
    try:
        parsed = urlparse(url)
    except (TypeError, ValueError):
        return False
    if parsed.scheme != "http":
        return False
    host = (parsed.hostname or "").lower()
    if host in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
