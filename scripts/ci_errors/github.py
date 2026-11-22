"""Minimal stdlib GitHub Actions API client (urllib + JSON only)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import urlsplit

API_ROOT = "https://api.github.com"


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Signed log URLs reject GitHub's Authorization header."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urlsplit(new.full_url).netloc != urlsplit(req.full_url).netloc:
            for name in list(new.headers):
                if name.lower() in {"authorization", "x-github-api-version"}:
                    del new.headers[name]
        return new


class GitHubClient:
    """Read-only client for workflow runs, jobs and job logs."""

    def __init__(self, repo: str, token: str | None = None, timeout: int = 30) -> None:
        self.repo = repo
        self.token = os.environ.get("GITHUB_TOKEN", "") if token is None else token
        self.timeout = timeout
        self.opener = urllib.request.build_opener(_SafeRedirect())

    def _request(self, path: str, params: dict[str, Any] | None = None, text: bool = False):
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{API_ROOT}{path}{query}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ci-errors-collector",
            "X-GitHub-Api-Version": "2026-03-10",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GitHub API {exc.code} for {path}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitHub API unreachable for {path}: {exc.reason}") from exc
        return body.decode("utf-8", errors="replace") if text else json.loads(body)

    def get_run(self, run_id: int) -> dict[str, Any]:
        return self._request(f"/repos/{self.repo}/actions/runs/{run_id}")

    def list_runs(self, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        runs: list[dict[str, Any]] = []
        page = 1
        per_page = min(100, limit)
        while len(runs) < limit:
            batch = self._request(f"/repos/{self.repo}/actions/runs", {"per_page": per_page, "page": page}).get(
                "workflow_runs", []
            )
            runs.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return runs[:limit]

    def list_jobs(self, run_id: int) -> dict[str, Any]:
        return self._request(f"/repos/{self.repo}/actions/runs/{run_id}/jobs", {"per_page": 100})

    def get_job_log(self, job_id: int) -> str:
        path = f"/repos/{self.repo}/actions/jobs/{job_id}/logs"
        try:
            return self._request(path, text=True)
        except RuntimeError as exc:
            match = re.search(r"GitHub API (\d{3}) for", str(exc))
            if match and match.group(1) in {"403", "404", "410"}:
                return f"(job log unavailable: HTTP {match.group(1)})"
            raise
