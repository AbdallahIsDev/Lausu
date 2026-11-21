"""GitHub REST API backend (fallback when ``gh`` is unavailable)."""

from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path

from ..result import PublishResult

log = logging.getLogger(__name__)


# ── GitHub API backend (fallback when ``gh`` is unavailable) ────────────

# We use ``urllib.request`` (stdlib) to avoid adding a ``requests`` /
# ``httpx`` dependency just for the publisher. The publisher runs in CI
# where ``gh`` is the preferred backend; the API fallback is a safety
# net for environments without ``gh`` (e.g. a local dev machine).


def _api_request(
    method: str,
    url: str,
    *,
    token: str,
    body: bytes | None = None,
    content_type: str = "application/json",
) -> tuple[int, bytes]:
    """Make a GitHub API request via :mod:`urllib.request`.

    Returns ``(status_code, response_body_bytes)``. Raises ``OSError``
    on network failure.
    """
    import urllib.request

    req = urllib.request.Request(url, method=method, data=body)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Content-Type", content_type)
    req.add_header("User-Agent", "lausu-release-publisher")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as exc:
        # HTTPError is a subclass of URLError (OSError), read the body
        # so the caller can surface the GitHub API error message. The
        # read is best-effort: we already have the HTTP status code (the
        # most important field); the body is just supplementary context.
        # ``exc.read()`` can raise ``OSError`` (socket closed / partial
        # body) or ``http.client.HTTPException`` (IncompleteRead), we
        # suppress any failure so a flaky body read does not mask the
        # original HTTP error.
        body_bytes = b""
        with contextlib.suppress(Exception):
            body_bytes = exc.read()
        return exc.code, body_bytes


def api_create_release(
    tag: str,
    *,
    repo: str,
    token: str,
    notes: str | None,
    draft: bool,
    prerelease: bool,
    target: str | None,
    title: str | None,
) -> tuple[str | None, str | None]:
    """Create a release via the GitHub REST API.

    Returns ``(release_url, error_message)``. On success,
    ``error_message`` is ``None``. On failure, ``release_url`` is
    ``None`` and ``error_message`` describes the failure.
    """
    url = f"https://api.github.com/repos/{repo}/releases"
    payload: dict[str, object] = {
        "tag_name": tag,
        "name": title or tag,
        "body": notes or "",
        "draft": draft,
        "prerelease": prerelease,
    }
    if target:
        payload["target_commitish"] = target
    body = json.dumps(payload).encode("utf-8")
    status, resp_body = _api_request("POST", url, token=token, body=body)
    if status not in (200, 201):
        return None, f"GitHub API returned {status}: {resp_body.decode('utf-8', errors='replace')[:500]}"
    try:
        data = json.loads(resp_body)
    except json.JSONDecodeError:
        return None, f"GitHub API returned non-JSON response: {resp_body[:200]!r}"
    release_url = data.get("html_url")
    upload_url_template = data.get("upload_url", "")
    # The upload_url is a templated URL like
    # ``https://uploads.github.com/repos/.../releases/123/assets{?name,label}``.
    # Strip the template suffix so we can append ``?name=<asset>``.
    upload_url = upload_url_template.split("{", 1)[0] if upload_url_template else None
    return release_url, upload_url


def api_upload_asset(
    upload_url: str,
    asset: Path,
    *,
    token: str,
) -> tuple[bool, str | None]:
    """Upload a single asset via the GitHub REST API.

    Returns ``(success, error_message)``. On success, ``error_message``
    is ``None``.
    """
    import urllib.parse

    if not asset.exists():
        return False, f"asset not found: {asset}"
    asset_name = asset.name
    url = f"{upload_url}?name={urllib.parse.quote(asset_name)}"
    body = asset.read_bytes()
    # GitHub requires ``application/octet-stream`` for asset uploads.
    status, resp_body = _api_request("POST", url, token=token, body=body, content_type="application/octet-stream")
    if status not in (200, 201):
        body_snippet = resp_body.decode("utf-8", errors="replace")[:500]
        return False, f"GitHub API returned {status} for {asset_name}: {body_snippet}"
    return True, None


def _publish_via_api(
    tag: str,
    assets: list[Path],
    *,
    repo: str,
    notes: str | None,
    draft: bool,
    prerelease: bool,
    target: str | None,
    title: str | None,
    token: str | None,
) -> PublishResult:
    """Publish via the GitHub REST API backend (fallback when ``gh`` is unavailable)."""
    if token is None:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return PublishResult(
            success=False,
            tag=tag,
            errors=[
                "GitHub API backend requires a token. Set GH_TOKEN / GITHUB_TOKEN env var "
                "or pass --token. (The gh CLI backend authenticates via `gh auth login`.)"
            ],
            backend="api",
        )

    # Create the release.
    # ``api_create_release`` returns ``(release_url, upload_url)`` on
    # success and ``(None, error_message)`` on failure. The two cases
    # are distinguished by whether ``release_url`` is ``None``.
    release_url, upload_url_or_err = api_create_release(
        tag,
        repo=repo,
        token=token,
        notes=notes,
        draft=draft,
        prerelease=prerelease,
        target=target,
        title=title,
    )
    upload_url: str | None = None
    if release_url is not None:
        # Success, ``upload_url_or_err`` is actually the upload_url.
        upload_url = upload_url_or_err
    else:
        # Failure, ``upload_url_or_err`` is the error message. Check
        # whether the failure is the "release already exists" case
        # (GitHub returns 422 with ``already_exists`` in the body). If
        # so, re-fetch the release by tag to get its upload_url.
        err_msg = upload_url_or_err or "unknown API error creating release"
        if "already_exists" in err_msg.lower() or "already_exists" in err_msg:
            url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
            status, resp_body = _api_request("GET", url, token=token)
            if status != 200:
                return PublishResult(
                    success=False,
                    tag=tag,
                    errors=[f"failed to fetch existing release {tag}: status {status}"],
                    backend="api",
                )
            try:
                data = json.loads(resp_body)
            except json.JSONDecodeError:
                return PublishResult(
                    success=False,
                    tag=tag,
                    errors=["existing release returned non-JSON"],
                    backend="api",
                )
            release_url = data.get("html_url")
            upload_url = (data.get("upload_url") or "").split("{", 1)[0] or None
        else:
            return PublishResult(
                success=False,
                tag=tag,
                errors=[err_msg],
                backend="api",
            )

    if not upload_url:
        return PublishResult(
            success=False,
            tag=tag,
            errors=["release has no upload_url, cannot upload assets"],
            backend="api",
        )

    # Upload assets.
    errors: list[str] = []
    uploaded: list[str] = []
    for asset in assets:
        ok, err = api_upload_asset(upload_url, asset, token=token)
        if ok:
            uploaded.append(asset.name)
        else:
            errors.append(err or f"unknown error uploading {asset.name}")

    return PublishResult(
        success=len(errors) == 0,
        tag=tag,
        release_url=release_url,
        uploaded=uploaded,
        errors=errors,
        backend="api",
    )


__all__ = ["_api_request", "_publish_via_api", "api_create_release", "api_upload_asset"]
