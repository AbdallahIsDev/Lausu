"""End-to-end tests over real GitHub Actions fixture payloads."""

from __future__ import annotations

from pathlib import Path

import scripts.ci_errors.collect as collect
from scripts.ci_errors.analyze import build_model, entries_for_run
from scripts.ci_errors.fixtures import load_fixture_dir

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ci_errors"


def test_fixture_dir_loads_real_runs_jobs_and_logs() -> None:
    runs = {run.id: run for run in load_fixture_dir(_FIXTURES)}
    assert len(runs) == 5
    installer = runs[45024078547]
    assert installer.conclusion == "failure"
    assert installer.commit_subject
    assert len(installer.jobs) == 23
    assert len(installer.logs) == 4
    assert runs[45024128135].conclusion == "success"
    assert runs[44937471544].event == "workflow_dispatch"


def test_categories_from_real_failure_logs() -> None:
    model = build_model(load_fixture_dir(_FIXTURES))
    found = {(entry.run_id, entry.classification) for entry in model.recent_failures}
    assert (45024078547, "cargo test/clippy/audit") in found
    assert (45024078547, "pytest") in found
    assert (45024078547, "pre-commit hygiene") in found
    assert (44937471544, "gate") in found
    codeql = next(run for run in load_fixture_dir(_FIXTURES) if run.id == 43843418145)
    assert entries_for_run(codeql)[0].classification == "CodeQL"
    assert (43843418145, "CodeQL") not in found  # pull_request, not main/dispatch
    audit = next(
        entry
        for entry in model.recent_failures
        if entry.run_id == 45024078547 and entry.classification == "cargo test/clippy/audit"
    )
    assert "Critical vulnerabilities" in audit.excerpt
    assert audit.job == "Rust clippy + cargo audit"


def test_successful_run_produces_no_entries() -> None:
    run = next(run for run in load_fixture_dir(_FIXTURES) if run.id == 45024128135)
    assert entries_for_run(run) == []


def test_offline_cli_is_byte_identical_and_never_uses_network(monkeypatch, tmp_path, capsys) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("offline mode must not call the network")

    monkeypatch.setattr(collect, "GitHubClient", forbidden)
    output = tmp_path / "CI-errors.md"
    for _ in range(2):
        assert collect.main(["--input", str(_FIXTURES), "--output", str(output)]) == 0
    assert b"## Currently failing" in output.read_bytes()
    assert b"## Recent failures" in output.read_bytes()
    assert b"## Resolved recently" in output.read_bytes()
    assert "currently failing" in capsys.readouterr().out


def test_unavailable_job_log_is_not_fatal(monkeypatch) -> None:
    from scripts.ci_errors.github import GitHubClient

    client = GitHubClient("AbdallahIsDev/Lausu", token="unused")

    def forbidden_request(*args, **kwargs):
        raise RuntimeError("GitHub API 403 for /repos/x/actions/jobs/1/logs")

    monkeypatch.setattr(client, "_request", forbidden_request)
    assert client.get_job_log(1) == "(job log unavailable: HTTP 403)"
