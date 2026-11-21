"""``gh`` CLI backend: command builders, probes and the publish flow."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from ..result import PublishResult

log = logging.getLogger(__name__)


# ── gh CLI backend ──────────────────────────────────────────────────────


def build_gh_create_command(
    tag: str,
    *,
    repo: str,
    notes: str | None,
    notes_file: Path | None,
    draft: bool,
    prerelease: bool,
    target: str | None,
    title: str | None,
) -> list[str]:
    """Build the ``gh release create`` argv.

    The command creates the release WITHOUT assets, assets are uploaded
    in a separate ``gh release upload`` step so a partial asset upload
    can be retried without recreating the release.

    ``--generate-notes`` is intentionally NOT used, the caller passes
    explicit ``--notes`` / ``--notes-file`` so the release notes are
    deterministic (GitHub's auto-generated notes include commit titles
    that may leak internal context).
    """
    cmd: list[str] = [
        "gh",
        "release",
        "create",
        tag,
        "--repo",
        repo,
    ]
    if draft:
        cmd.append("--draft")
    if prerelease:
        cmd.append("--prerelease")
    if target:
        cmd.extend(["--target", target])
    if title:
        cmd.extend(["--title", title])
    if notes_file is not None:
        cmd.extend(["--notes-file", str(notes_file)])
    elif notes is not None:
        cmd.extend(["--notes", notes])
    else:
        # No notes: use an empty string so GitHub doesn't auto-generate.
        cmd.extend(["--notes", ""])
    return cmd


def build_gh_upload_command(
    tag: str,
    assets: list[Path],
    *,
    repo: str,
    clobber: bool = True,
) -> list[str]:
    """Build the ``gh release upload`` argv.

    ``--clobber`` replaces existing assets with the same name (idempotent
    re-run). Without it, ``gh release upload`` fails on the first
    duplicate asset name.
    """
    cmd: list[str] = [
        "gh",
        "release",
        "upload",
        tag,
        *[str(a) for a in assets],
        "--repo",
        repo,
    ]
    if clobber:
        cmd.append("--clobber")
    return cmd


def run_gh(cmd: list[str], *, runner: callable | None = None) -> subprocess.CompletedProcess:
    """Run a ``gh`` command, returning the completed process.

    ``runner`` is injectable for testing (defaults to
    :func:`subprocess.run`). Tests substitute a fake to avoid spawning
    ``gh``.
    """
    if runner is None:
        runner = subprocess.run  # type: ignore[assignment]
    return runner(cmd, capture_output=True, text=True, timeout=300)  # type: ignore[call-arg]


def gh_release_exists(tag: str, *, repo: str, runner: callable | None = None) -> bool:
    """Return True if a release with *tag* already exists.

    Uses ``gh release view``: exit 0 means the release exists, non-zero
    means it doesn't (or ``gh`` failed).
    """
    cmd = ["gh", "release", "view", tag, "--repo", repo]
    result = run_gh(cmd, runner=runner)
    return result.returncode == 0


def gh_release_url(tag: str, *, repo: str, runner: callable | None = None) -> str | None:
    """Return the GitHub release URL for *tag*, or ``None`` if it can't be resolved."""
    cmd = ["gh", "release", "view", tag, "--repo", repo, "--json", "url", "--jq", ".url"]
    result = run_gh(cmd, runner=runner)
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    return url or None


def _publish_via_gh(
    tag: str,
    assets: list[Path],
    *,
    repo: str,
    notes: str | None,
    notes_file: Path | None,
    draft: bool,
    prerelease: bool,
    target: str | None,
    title: str | None,
    gh_cli: str,
    runner: callable | None,
) -> PublishResult:
    """Publish via the ``gh`` CLI backend."""
    # Create the release if it doesn't exist (idempotent).
    if gh_release_exists(tag, repo=repo, runner=runner):
        log.info("[RELEASE] release %s already exists, uploading assets only", tag)
    else:
        cmd = build_gh_create_command(
            tag,
            repo=repo,
            notes=notes,
            notes_file=notes_file,
            draft=draft,
            prerelease=prerelease,
            target=target,
            title=title,
        )
        cmd[0] = gh_cli  # respect the configured binary name
        result = run_gh(cmd, runner=runner)
        if result.returncode != 0:
            return PublishResult(
                success=False,
                tag=tag,
                errors=[f"gh release create failed (exit {result.returncode}): {result.stderr.strip()}"],
                backend="gh",
            )

    # Upload assets (``--clobber`` makes it idempotent).
    upload_cmd = build_gh_upload_command(tag, assets, repo=repo, clobber=True)
    upload_cmd[0] = gh_cli
    upload_result = run_gh(upload_cmd, runner=runner)
    if upload_result.returncode != 0:
        return PublishResult(
            success=False,
            tag=tag,
            release_url=gh_release_url(tag, repo=repo, runner=runner),
            errors=[f"gh release upload failed (exit {upload_result.returncode}): {upload_result.stderr.strip()}"],
            backend="gh",
        )

    return PublishResult(
        success=True,
        tag=tag,
        release_url=gh_release_url(tag, repo=repo, runner=runner),
        uploaded=[a.name for a in assets],
        backend="gh",
    )


__all__ = [
    "_publish_via_gh",
    "build_gh_create_command",
    "build_gh_upload_command",
    "gh_release_exists",
    "gh_release_url",
    "run_gh",
]
