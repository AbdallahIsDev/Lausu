"""Canonical ``pack-manifest.json`` URLs + manifest size/timeout bounds.

Extracted from ``update_check.py``: this module only resolves the candidate
manifest URLs and holds the shared size/timeout limits (no network access).
"""

from __future__ import annotations

import os as _os

from voice_typer.server.branding import APP_REPO

# Stable GitHub Releases URL for the pack manifest. GitHub serves the
DEFAULT_OFFLINE_PACK_MANIFEST_URL = f"https://github.com/{APP_REPO}/releases/latest/download/pack-manifest.json"

# Rolling tag the publish workflow also updates. `releases/latest` moves
# whenever ANY release (including app releases without a pack) is cut, so
# the latest/download URL 404s after an app-only release. The `offline-pack`
# tag is pack-only and stays valid across app releases.
ROLLING_OFFLINE_PACK_MANIFEST_URL = f"https://github.com/{APP_REPO}/releases/download/offline-pack/pack-manifest.json"


def pack_manifest_url_candidates(manifest_url: str | None = None) -> list[str]:
    """Ordered candidate URLs for ``pack-manifest.json`` (first success wins).

    Explicit ``manifest_url`` / ``VT_PACK_MANIFEST_URL`` still win as a
    single candidate (opt-in override, no fallback surprise).
    """
    if manifest_url is not None:
        return [manifest_url]
    env = _os.environ.get("VT_PACK_MANIFEST_URL")
    if env:
        return [env]
    return [DEFAULT_OFFLINE_PACK_MANIFEST_URL, ROLLING_OFFLINE_PACK_MANIFEST_URL]


def _resolve_manifest_url(manifest_url: str | None) -> str:
    """Return the primary manifest URL (kept for call sites that need one)."""
    return pack_manifest_url_candidates(manifest_url)[0]


# 1 MiB cap on the remote manifest. Real pack-manifest.json is <2 KB
MAX_MANIFEST_BYTES = 1 * 1024 * 1024
