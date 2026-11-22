"""Focused tests for run selection, dedupe, rotation and determinism."""

from __future__ import annotations

from pathlib import Path

from scripts.ci_errors.analyze import (
    CANCEL_GRACE,
    MAX_RECENT,
    REPORT_CAP_BYTES,
    build_model,
    currently_failing,
    dedupe_runs,
    recent_failures,
    resolved_recently,
    runs_needing_detail,
)
from scripts.ci_errors.render import render_report
from scripts.ci_errors.types import Entry, JobInfo, ReportModel, RunInfo, StepInfo

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ci_errors"
_NOW = "2026-11-22T20:00:00Z"


def make_run(
    run_id: int,
    *,
    created: str = "2026-11-22T10:00:00Z",
    conclusion: str = "failure",
    workflow: str = "Build Windows",
    branch: str = "main",
    event: str = "push",
    attempt: int = 1,
    jobs: tuple[JobInfo, ...] = (),
    logs: dict[int, str] | None = None,
    sha: str = "abcdef1234567890",
) -> RunInfo:
    return RunInfo(
        id=run_id,
        run_attempt=attempt,
        workflow_name=workflow,
        event=event,
        branch=branch,
        head_sha=sha,
        commit_subject="fix(ci): repair the gate",
        status="completed",
        conclusion=conclusion,
        created_at=created,
        updated_at=created,
        html_url=f"https://github.com/AbdallahIsDev/Lausu/actions/runs/{run_id}",
        jobs=jobs,
        logs=logs or {},
    )


def test_dedupe_by_run_id_and_attempt() -> None:
    runs = [
        make_run(1, created="2026-11-22T09:00:00Z"),
        make_run(1, created="2026-11-22T10:00:00Z", attempt=2),
        make_run(2, created="2026-11-22T11:00:00Z"),
    ]
    assert [run.key for run in dedupe_runs(runs)] == [(2, 1), (1, 2), (1, 1)]
    assert len(dedupe_runs([runs[0], runs[0]])) == 1


def test_later_success_clears_currently_failing() -> None:
    red = make_run(1, created="2026-11-22T10:00:00Z")
    green = make_run(2, created="2026-11-22T11:00:00Z", conclusion="success")
    assert currently_failing([red, green], _NOW) == []
    assert currently_failing([green, red], _NOW) == []
    later_red = make_run(3, created="2026-11-22T12:00:00Z")
    assert [run.id for run in currently_failing([green, later_red], _NOW)] == [3]


def test_cancelled_counts_only_after_three_hours() -> None:
    red = make_run(1, created="2026-11-22T10:00:00Z")
    old_cancel = make_run(2, created="2026-11-22T11:00:00Z", conclusion="cancelled")
    fresh_cancel = make_run(3, created="2026-11-22T19:00:00Z", conclusion="cancelled")
    assert CANCEL_GRACE.total_seconds() == 3 * 3600
    assert [run.id for run in currently_failing([red, old_cancel, fresh_cancel], _NOW)] == [2]
    green = make_run(4, created="2026-11-22T19:30:00Z", conclusion="success")
    assert currently_failing([red, old_cancel, fresh_cancel, green], _NOW) == []


def test_currently_failing_ignores_non_main_branches() -> None:
    pr = make_run(1, branch="feature", event="pull_request")
    assert currently_failing([pr], _NOW) == []


def test_recent_failures_scope_order_cap_and_dedupe() -> None:
    runs = [make_run(i, created=f"2026-11-22T{i // 60:02d}:{i % 60:02d}:00Z") for i in range(70)]
    runs.append(
        make_run(
            999,
            created="2026-11-23T00:00:00Z",
            branch="feature",
            event="workflow_dispatch",
            workflow="Build installer",
        )
    )
    runs.append(make_run(1, created="2026-11-22T00:01:00Z"))
    selected = recent_failures(dedupe_runs(runs))
    assert len(selected) == MAX_RECENT
    assert selected[0].id == 999
    assert len({run.key for run in selected}) == len(selected)
    assert all(run.conclusion == "failure" for run in selected)


def test_resolved_recently_pairs_fix_with_previous_red() -> None:
    runs: list[RunInfo] = []
    for index in range(25):
        stamp = f"2026-11-22T{index:02d}:00:00Z"
        runs.append(make_run(100 + index, created=stamp))
        runs.append(make_run(200 + index, created=f"2026-11-22T{index:02d}:30:00Z", conclusion="success"))
    pairs = resolved_recently(dedupe_runs(runs))
    assert len(pairs) == 20
    assert pairs[0][0].id == 224 and pairs[0][1].id == 124
    assert all(fixing.conclusion == "success" and red.conclusion == "failure" for fixing, red in pairs)


def test_model_entry_fields_and_pytest_nodes() -> None:
    job = JobInfo(
        id=10,
        name="test (ubuntu-22.04, 3.13)",
        conclusion="failure",
        labels=("ubuntu-22.04",),
        steps=(StepInfo("Run tests with coverage", 13, "failure"),),
    )
    log = (_FIXTURES / "pytest_log_synthetic.txt").read_text(encoding="utf-8")
    run = make_run(7, jobs=(job,), logs={10: log})
    model = build_model([run])
    entry = model.currently_failing[0]
    assert entry.workflow == "Build Windows"
    assert entry.run_id == 7 and entry.run_attempt == 1
    assert entry.branch == "main" and entry.event == "push"
    assert entry.sha == "abcdef1"
    assert entry.conclusion == "failure"
    assert entry.job == job.name and entry.leg == "ubuntu-22.04, 3.13"
    assert entry.step == "Run tests with coverage"
    assert entry.classification == "pytest"
    assert len(entry.pytest_failures) == 2
    assert model.generated_at == run.updated_at and model.data_commit == "abcdef1"
    assert runs_needing_detail(model) == {7}


def test_render_is_idempotent_and_deterministic() -> None:
    runs = [
        make_run(1, created="2026-11-22T10:00:00Z"),
        make_run(2, created="2026-11-22T11:00:00Z", conclusion="success"),
    ]
    first = render_report(build_model(runs))
    assert first == render_report(build_model(list(reversed(runs))))
    assert "## Currently failing" in first
    assert "## Recent failures" in first
    assert "## Resolved recently" in first


def test_size_rotation_drops_oldest_recent_but_never_current() -> None:
    current = Entry(
        "Build installer",
        1,
        1,
        "https://example/1",
        "push",
        "main",
        "aaaaaaa",
        "current marker",
        "failure",
        "hygiene",
        "",
        "hooks",
        "pre-commit hygiene",
        "boom",
    )
    model = ReportModel(
        generated_at="2026-11-22T20:00:00Z",
        data_commit="aaaaaaa",
        currently_failing=[current],
        recent_failures=[
            Entry(
                "Build installer",
                index,
                1,
                f"https://example/{index}",
                "push",
                "main",
                "bbbbbbb",
                "x" * 12000,
                "failure",
                "job",
                "",
                "step",
                "ruff",
                "boom",
            )
            for index in range(2, 102)
        ],
    )
    text = render_report(model)
    assert len(text.encode("utf-8")) <= REPORT_CAP_BYTES
    assert "current marker" in text
    assert text.count("https://example/") < 100
    assert "rotated out" in text
