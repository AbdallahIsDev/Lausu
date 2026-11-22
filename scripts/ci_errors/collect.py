"""CLI: `python -m ci_errors.collect --repo <owner/name> --output CI-errors.md`.

Ingest mode (--run-id) and rebuild mode (--rebuild --limit N) use urllib.
Offline mode (--input DIR) reads fixture JSON and never touches the network.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from .analyze import BAD_CONCLUSIONS, build_model, runs_needing_detail
from .fixtures import load_fixture_dir, parse_jobs_payload, parse_run_payload
from .github import GitHubClient
from .render import render_report, write_report
from .types import RunInfo

MAX_DETAIL_FETCH = 100


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect failed GitHub Actions runs into markdown")
    parser.add_argument("--repo", default="AbdallahIsDev/Lausu", help="owner/name")
    parser.add_argument("--output", required=True, help="markdown report path")
    parser.add_argument("--input", help="offline fixture directory (no network)")
    parser.add_argument("--run-id", type=int, help="ingest one workflow run id")
    parser.add_argument("--rebuild", action="store_true", help="rebuild from the last N runs")
    parser.add_argument("--limit", type=int, default=200, help="runs to fetch in rebuild mode")
    return parser.parse_args(argv)


def _online_runs(args: argparse.Namespace) -> list[RunInfo]:
    client = GitHubClient(args.repo)
    payloads = client.list_runs(args.limit if args.rebuild else min(args.limit, 200))
    if args.run_id is not None and not any(int(item.get("id", 0)) == args.run_id for item in payloads):
        payloads.append(client.get_run(args.run_id))
    return [parse_run_payload(item) for item in payloads]


def _enrich(runs: list[RunInfo], needed: set[int], client: GitHubClient) -> list[RunInfo]:
    enriched: list[RunInfo] = []
    fetched = 0
    for run in runs:
        if run.id not in needed or run.jobs or fetched >= MAX_DETAIL_FETCH:
            enriched.append(run)
            continue
        fetched += 1
        jobs = parse_jobs_payload(client.list_jobs(run.id))
        logs = {job.id: client.get_job_log(job.id) for job in jobs if job.conclusion in BAD_CONCLUSIONS}
        enriched.append(replace(run, jobs=jobs, logs=logs))
    return enriched


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.input:
        runs = load_fixture_dir(args.input)
    else:
        runs = _online_runs(args)
        wanted = runs_needing_detail(build_model(runs))
        runs = _enrich(runs, wanted, GitHubClient(args.repo))

    model = build_model(runs)
    text = render_report(model)
    write_report(Path(args.output), text)
    print(
        f"ci-errors: {len(model.currently_failing)} currently failing, "
        f"{len(model.recent_failures)} recent, {len(model.resolved_recently)} resolved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
