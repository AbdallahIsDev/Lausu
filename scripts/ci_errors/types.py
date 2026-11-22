"""Value types shared by the fixture reader, analyzer and renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepInfo:
    """One step of a workflow job."""

    name: str
    number: int
    conclusion: str


@dataclass(frozen=True)
class JobInfo:
    """One job of a workflow run, with its non-green steps."""

    id: int
    name: str
    conclusion: str
    labels: tuple[str, ...]
    steps: tuple[StepInfo, ...]


@dataclass(frozen=True)
class RunInfo:
    """A workflow run plus its jobs and job logs, shaped like the REST API."""

    id: int
    run_attempt: int
    workflow_name: str
    event: str
    branch: str
    head_sha: str
    commit_subject: str
    status: str
    conclusion: str
    created_at: str
    updated_at: str
    html_url: str
    jobs: tuple[JobInfo, ...] = ()
    logs: dict[int, str] = field(default_factory=dict)

    @property
    def key(self) -> tuple[int, int]:
        return (self.id, self.run_attempt)

    @property
    def order(self) -> tuple[str, int, int]:
        return (self.created_at, self.id, self.run_attempt)


@dataclass(frozen=True)
class PytestFailure:
    """A failing pytest node id and the assertion attached to it."""

    node_id: str
    location: str
    message: str


@dataclass(frozen=True)
class Entry:
    """One rendered failure: a run, one of its jobs and its failed step."""

    workflow: str
    run_id: int
    run_attempt: int
    url: str
    event: str
    branch: str
    sha: str
    subject: str
    conclusion: str
    job: str
    leg: str
    step: str
    classification: str
    excerpt: str
    pytest_failures: tuple[PytestFailure, ...] = ()
    fixing_run_id: int | None = None
    fixing_url: str = ""


@dataclass
class ReportModel:
    """Everything the renderer needs, computed from a set of runs."""

    generated_at: str
    data_commit: str
    currently_failing: list[Entry] = field(default_factory=list)
    recent_failures: list[Entry] = field(default_factory=list)
    resolved_recently: list[Entry] = field(default_factory=list)


def as_int(value: Any, default: int = 0) -> int:
    """Coerce API number-or-string fields without raising on nulls."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_text(value: Any) -> str:
    """API strings are nullable; render missing values as empty strings."""
    return value.strip() if isinstance(value, str) else ""
