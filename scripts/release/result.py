"""Shared value type and defaults for the release publisher.

Dependency-free on purpose: every other publisher module imports from here,
so keeping ``PublishResult`` out of the backend/publisher modules avoids a
circular import.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from voice_typer.server.branding import APP_REPO

DEFAULT_REPO = APP_REPO
DEFAULT_GH_CLI = "gh"


@dataclass
class PublishResult:
    """Outcome of a release publish attempt.

    Fields:
        success: True if all assets were uploaded (or already present).
        tag: the release tag (e.g. ``"v1.2.3"``).
        release_url: the GitHub release URL (``https://github.com/.../releases/tag/v1.2.3``).
        uploaded: list of asset names that were uploaded this run.
        skipped: list of asset names that were already present (idempotent re-run).
        errors: list of per-asset error messages (empty on full success).
        backend: which backend was used (``"gh"`` or ``"api"``).
    """

    success: bool
    tag: str
    release_url: str | None = None
    uploaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    backend: str = "gh"


__all__ = ["DEFAULT_GH_CLI", "DEFAULT_REPO", "PublishResult"]
