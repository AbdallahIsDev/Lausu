"""Asset validation and the backend-agnostic publish flow."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .backends.api import _publish_via_api
from .backends.gh import _publish_via_gh
from .result import DEFAULT_GH_CLI, DEFAULT_REPO, PublishResult

log = logging.getLogger(__name__)


def validate_assets(assets: list[Path]) -> list[str]:
    """Return a list of error messages for missing / invalid assets.

    An asset is invalid if:
      * it does not exist (broken CI artifact path).
      * it is empty (0 bytes, a failed build produced an empty file).
      * it is a directory (caller passed a dir instead of a file).
    """
    errors: list[str] = []
    for asset in assets:
        if not asset.exists():
            errors.append(f"asset not found: {asset}")
            continue
        if asset.is_dir():
            errors.append(f"asset is a directory, not a file: {asset}")
            continue
        if asset.stat().st_size == 0:
            errors.append(f"asset is empty (0 bytes): {asset}")
    return errors


def publish_release(
    tag: str,
    assets: list[Path],
    *,
    repo: str = DEFAULT_REPO,
    notes: str | None = None,
    notes_file: Path | None = None,
    draft: bool = False,
    prerelease: bool = False,
    target: str | None = None,
    title: str | None = None,
    gh_cli: str = DEFAULT_GH_CLI,
    runner: callable | None = None,
    token: str | None = None,
    backend: str | None = None,
) -> PublishResult:
    """Publish a GitHub Release with the given assets.

    Args:
        tag: the release tag (e.g. ``"v1.2.3"``).
        assets: list of asset file paths to upload.
        repo: the ``owner/name`` repo slug.
        notes: release notes body (markdown). Mutually exclusive with
            ``notes_file``.
        notes_file: path to a release-notes file. Mutually exclusive
            with ``notes``.
        draft: create as a draft release (not visible to users).
        prerelease: mark as a pre-release.
        target: target commitish (branch / SHA) for the release.
        title: release title (defaults to the tag).
        gh_cli: the ``gh`` CLI binary name (defaults to ``"gh"``).
        runner: injectable subprocess runner for testing (defaults to
            :func:`subprocess.run`).
        token: GitHub API token (for the API backend). Falls back to
            the ``GH_TOKEN`` / ``GITHUB_TOKEN`` env var.
        backend: force a specific backend (``"gh"`` or ``"api"``).
            ``None`` (default) auto-selects: ``"gh"`` if the ``gh`` CLI
            is available, else ``"api"``.

    Returns:
        :class:`PublishResult`. Never raises, all errors are captured
        in ``result.errors``. The caller checks ``result.success``.
    """
    # Validate assets first, fail fast on missing/empty files.
    asset_errors = validate_assets(assets)
    if asset_errors:
        return PublishResult(
            success=False,
            tag=tag,
            errors=asset_errors,
            backend=backend or "gh",
        )

    # Auto-select backend if not forced.
    if backend is None:
        gh_path = shutil.which(gh_cli) if runner is None else DEFAULT_GH_CLI
        backend = "gh" if gh_path else "api"
        log.info("[RELEASE] auto-selected backend: %s", backend)

    if backend == "gh":
        return _publish_via_gh(
            tag,
            assets,
            repo=repo,
            notes=notes,
            notes_file=notes_file,
            draft=draft,
            prerelease=prerelease,
            target=target,
            title=title,
            gh_cli=gh_cli,
            runner=runner,
        )
    if backend == "api":
        return _publish_via_api(
            tag,
            assets,
            repo=repo,
            notes=notes,
            draft=draft,
            prerelease=prerelease,
            target=target,
            title=title,
            token=token,
        )
    return PublishResult(
        success=False,
        tag=tag,
        errors=[f"unknown backend: {backend!r} (expected 'gh' or 'api')"],
        backend=backend,
    )


__all__ = ["publish_release", "validate_assets"]
