"""Read offline fixture JSON/log files shaped like GitHub Actions API responses."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from .types import JobInfo, RunInfo, StepInfo, as_int, as_text


def parse_run_payload(data: dict[str, Any]) -> RunInfo:
    """Map one `GET /actions/runs/<id>` payload to a RunInfo."""
    head_commit = data.get("head_commit") or {}
    return RunInfo(
        id=as_int(data.get("id")),
        run_attempt=as_int(data.get("run_attempt"), 1) or 1,
        workflow_name=as_text(data.get("name")),
        event=as_text(data.get("event")),
        branch=as_text(data.get("head_branch")),
        head_sha=as_text(data.get("head_sha")),
        commit_subject=as_text(head_commit.get("message")).splitlines()[0] if isinstance(head_commit, dict) else "",
        status=as_text(data.get("status")),
        conclusion=as_text(data.get("conclusion")),
        created_at=as_text(data.get("created_at")),
        updated_at=as_text(data.get("updated_at")),
        html_url=as_text(data.get("html_url")),
    )


def parse_jobs_payload(data: dict[str, Any]) -> tuple[JobInfo, ...]:
    """Map one `GET /actions/runs/<id>/jobs` payload to JobInfo values."""
    jobs: list[JobInfo] = []
    for raw in data.get("jobs", []):
        steps = tuple(
            StepInfo(
                name=as_text(step.get("name")),
                number=as_int(step.get("number")),
                conclusion=as_text(step.get("conclusion")),
            )
            for step in raw.get("steps", [])
        )
        jobs.append(
            JobInfo(
                id=as_int(raw.get("id")),
                name=as_text(raw.get("name")),
                conclusion=as_text(raw.get("conclusion")),
                labels=tuple(as_text(label) for label in raw.get("labels", [])),
                steps=steps,
            )
        )
    return tuple(jobs)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a JSON object")
    return data


def load_fixture_dir(directory: str | Path) -> list[RunInfo]:
    """Load every `run_*.json` (plus matching jobs/logs) from one directory.

    Layout: `run_<id>.json`, `jobs_<id>.json`, `log_<id>_<job_id>.txt`.
    The first two files are verbatim API payloads; logs are job log text.
    """
    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    runs: dict[int, RunInfo] = {}
    for path in sorted(root.glob("run_*.json")):
        run = parse_run_payload(_read_json(path))
        if run.id:
            runs[run.id] = run
    for path in sorted(root.glob("jobs_*.json")):
        run_id = as_int(path.stem.removeprefix("jobs_"))
        run = runs.get(run_id)
        if run is None:
            continue
        runs[run_id] = _replace_jobs(run, parse_jobs_payload(_read_json(path)))
    for path in sorted(root.glob("log_*.txt")):
        parts = path.stem.split("_")
        if len(parts) < 3:
            continue
        run_id, job_id = as_int(parts[1]), as_int(parts[2])
        run = runs.get(run_id)
        if run is None or job_id not in {job.id for job in run.jobs}:
            continue
        logs = dict(run.logs)
        logs[job_id] = path.read_text(encoding="utf-8", errors="replace")
        runs[run_id] = _replace_logs(run, logs)
    return sorted(runs.values(), key=lambda run: run.order, reverse=True)


def _replace_jobs(run: RunInfo, jobs: tuple[JobInfo, ...]) -> RunInfo:
    return replace(run, jobs=jobs)


def _replace_logs(run: RunInfo, logs: dict[int, str]) -> RunInfo:
    return replace(run, logs=logs)
