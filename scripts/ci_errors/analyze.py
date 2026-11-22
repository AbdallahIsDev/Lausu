"""Report selection rules, run dedupe and size rotation inputs."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from .extract import classify, error_excerpt, pytest_failures
from .types import Entry, ReportModel, RunInfo

MAX_RECENT = 60
MAX_RESOLVED = 20
CANCEL_GRACE = timedelta(hours=3)
REPORT_CAP_BYTES = 400 * 1024
MAX_JOB_ENTRIES = 8

# Workflows the collector never reports on: itself and a retired queue.
COLLECTOR_EXCLUSIONS = frozenset({"CI error collector", "Mutation testing (mutmut) — RETIRED"})
# Baseline for the workflow-list drift test; update alongside the YAML files.
TRACKED_WORKFLOWS = frozenset(
    {
        "Build installer",
        "Client CI",
        "CodeQL",
        "Host Validation (Cannot-Verify close-out)",
        "Perf regression",
        "Populate model hashes",
        "runtime-pack-publish",
        "Build all platforms",
        "Build Linux",
        "Build macOS",
        "Build Windows ARM validation",
        "Build Windows",
    }
)

BAD_CONCLUSIONS = frozenset({"failure", "timed_out", "cancelled"})
_LEG_RE = re.compile(r"\(([^)]+)\)")


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def dedupe_runs(runs: list[RunInfo]) -> list[RunInfo]:
    """One run per (id, attempt), newest first."""
    unique = {run.key: run for run in runs}
    return sorted(unique.values(), key=lambda run: run.order, reverse=True)


def generation_time(runs: list[RunInfo]) -> str:
    """Wall clock is banned for idempotency: stamp the newest input update."""
    stamps = [run.updated_at or run.created_at for run in runs if run.updated_at or run.created_at]
    return max(stamps) if stamps else "unknown"


def data_commit(runs: list[RunInfo]) -> str:
    """Head commit of the newest main-branch run in the data set."""
    on_main = sorted(
        (run for run in runs if run.branch == "main" and run.head_sha),
        key=lambda run: run.order,
        reverse=True,
    )
    return on_main[0].head_sha[:7] if on_main else "unknown"


def _age_beyond_grace(run: RunInfo, now: str) -> bool:
    moment, reference = _parse_time(run.updated_at or run.created_at), _parse_time(now)
    return bool(moment and reference and reference - moment > CANCEL_GRACE)


def currently_failing(runs: list[RunInfo], now: str) -> list[RunInfo]:
    """Latest unfinished-green run per (workflow, main); cancelled after 3 h."""
    grouped: dict[str, list[RunInfo]] = {}
    for run in runs:
        if run.branch == "main" and run.status == "completed" and run.workflow_name not in COLLECTOR_EXCLUSIONS:
            grouped.setdefault(run.workflow_name, []).append(run)
    result: list[RunInfo] = []
    for group in grouped.values():
        for run in sorted(group, key=lambda item: item.order, reverse=True):
            if run.conclusion == "success":
                break
            if run.conclusion == "failure" or (
                run.conclusion in {"cancelled", "timed_out"} and _age_beyond_grace(run, now)
            ):
                result.append(run)
                break
    return sorted(result, key=lambda run: run.order, reverse=True)


def recent_failures(runs: list[RunInfo]) -> list[RunInfo]:
    """Last 60 failures on main plus workflow_dispatch failures on any branch."""
    selected = [
        run
        for run in runs
        if run.conclusion == "failure" and (run.branch == "main" or run.event == "workflow_dispatch")
    ]
    return selected[:MAX_RECENT]


def resolved_recently(runs: list[RunInfo]) -> list[tuple[RunInfo, RunInfo]]:
    """Pairs of (fixing success, red run immediately before it), newest first."""
    grouped: dict[tuple[str, str], list[RunInfo]] = {}
    for run in runs:
        grouped.setdefault((run.workflow_name, run.branch), []).append(run)
    pairs: list[tuple[RunInfo, RunInfo]] = []
    for group in grouped.values():
        ascending = sorted(group, key=lambda run: run.order)
        red: RunInfo | None = None
        for run in ascending:
            if run.conclusion == "failure":
                red = run
            elif run.conclusion == "success" and red is not None:
                pairs.append((run, red))
                red = None
    return sorted(pairs, key=lambda pair: pair[0].order, reverse=True)[:MAX_RESOLVED]


def entries_for_run(run: RunInfo) -> list[Entry]:
    """One entry per non-green job; job logs supply the step and excerpt."""
    if run.conclusion not in BAD_CONCLUSIONS:
        return []
    failed = [job for job in run.jobs if job.conclusion in BAD_CONCLUSIONS]
    jobs = failed[:MAX_JOB_ENTRIES] or [None]
    entries: list[Entry] = []
    for job in jobs:
        step = ""
        conclusion = run.conclusion
        log = ""
        if job is not None:
            bad_steps = [item for item in job.steps if item.conclusion in BAD_CONCLUSIONS]
            step = bad_steps[0].name if bad_steps else "(job-level failure)"
            conclusion = job.conclusion or run.conclusion
            log = run.logs.get(job.id, "")
        excerpt = error_excerpt(log) if log else "(no job log available)"
        match = _LEG_RE.search(job.name) if job is not None else None
        leg = match.group(1) if match else (", ".join(job.labels) if job is not None else "")
        category = classify(step, excerpt, conclusion)
        entries.append(
            Entry(
                workflow=run.workflow_name,
                run_id=run.id,
                run_attempt=run.run_attempt,
                url=run.html_url,
                event=run.event,
                branch=run.branch,
                sha=run.head_sha[:7],
                subject=run.commit_subject,
                conclusion=run.conclusion,
                job=job.name if job is not None else "(job details unavailable)",
                leg=leg,
                step=step,
                classification=category,
                excerpt=excerpt,
                pytest_failures=pytest_failures(log) if log and category == "pytest" else (),
            )
        )
    return entries


def build_model(runs: list[RunInfo]) -> ReportModel:
    """Compute all three sections from deduped runs."""
    ordered = dedupe_runs(runs)
    now = generation_time(ordered)
    model = ReportModel(generated_at=now, data_commit=data_commit(ordered))
    for run in currently_failing(ordered, now):
        model.currently_failing.extend(entries_for_run(run))
    for run in recent_failures(ordered):
        model.recent_failures.extend(entries_for_run(run))
    for fixing, red in resolved_recently(ordered):
        for original in entries_for_run(red):
            entry = replace(original, fixing_run_id=fixing.id, fixing_url=fixing.html_url)
            model.resolved_recently.append(entry)
    model.resolved_recently = model.resolved_recently[:MAX_RESOLVED]
    return model


def runs_needing_detail(model: ReportModel) -> set[int]:
    """Run ids whose jobs/logs must be fetched before rendering."""
    return {
        entry.run_id
        for section in (model.currently_failing, model.recent_failures, model.resolved_recently)
        for entry in section
    }
