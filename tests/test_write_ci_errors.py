"""Tests for scripts/ci/write_ci_errors.py (the CI-errors.md generator)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "ci" / "write_ci_errors.py"
_WORKFLOW = _ROOT / ".github" / "workflows" / "build.yml"


def _load():
    spec = importlib.util.spec_from_file_location("write_ci_errors", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["write_ci_errors"] = mod
    spec.loader.exec_module(mod)
    return mod


def _junit(cases: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<testsuites><testsuite name="pytest" tests="1">{cases}</testsuite></testsuites>'
    ).encode()


def _failing_case() -> str:
    return (
        '<testcase classname="tests.test_x" name="test_boom">'
        '<failure message="AssertionError: boom">'
        "tests/test_x.py:12: in test_boom\n"
        "E   AssertionError: boom"
        "</failure></testcase>"
    )


def test_parses_failure_with_location(tmp_path: Path) -> None:
    mod = _load()
    f = tmp_path / "pytest-results.xml"
    f.write_bytes(_junit(_failing_case()))
    failures, note = mod._extract_failures(f)
    assert note == ""
    assert len(failures) == 1
    classname, name, leg, location, body = failures[0]
    assert (classname, name) == ("tests.test_x", "test_boom")
    assert location == "tests/test_x.py:12"
    assert "AssertionError: boom" in body


def test_illegal_xml_chars_do_not_break_parse(tmp_path: Path) -> None:
    """Raw control bytes in captured output must be sanitized away."""
    mod = _load()
    f = tmp_path / "pytest-results.xml"
    raw = _junit(_failing_case()).replace(b"boom", b"bo\x00om\x1b[31m")
    f.write_bytes(raw)
    failures, note = mod._extract_failures(f)
    assert note == ""
    assert len(failures) == 1


def test_truncated_file_falls_back_to_partial_extraction(tmp_path: Path) -> None:
    """A leg killed mid-write still surfaces its complete testcases."""
    mod = _load()
    f = tmp_path / "pytest-results.xml"
    case2 = _failing_case().replace("test_boom", "test_cut")
    head, sep, _ = _junit(_failing_case()).decode().partition("</testcase>")
    assert sep, "fixture must contain a complete first testcase"
    f.write_bytes((head + sep + case2[: len(case2) // 3]).encode())
    failures, note = mod._extract_failures(f)
    assert note != ""
    assert len(failures) == 1  # the complete first case survives
    assert failures[0][1] == "test_boom"


def test_empty_classname_renders_without_leading_dot(tmp_path: Path, capsys, monkeypatch) -> None:
    """Collection errors (empty classname) render as bare module path."""
    mod = _load()
    monkeypatch.setattr(mod, "OUTPUT", tmp_path / "CI-errors.md")
    d = tmp_path / "junit" / "pytest-results-ubuntu-22.04-3.12"
    d.mkdir(parents=True)
    f = d / "pytest-results.xml"
    f.write_bytes(
        _junit('<testcase classname="" name="tests.test_y"><error message="collection">oops</error></testcase>')
    )
    assert mod.main([str(f)]) == 0
    out = capsys.readouterr().out
    assert "wrote 1 failure" in out
    text = (tmp_path / "CI-errors.md").read_text(encoding="utf-8")
    assert "### 1. `tests.test_y`" in text
    assert "ubuntu-22.04-3.12" in text


def test_leg_label_from_artifact_layout(tmp_path: Path) -> None:
    mod = _load()
    assert mod._leg_of(tmp_path / "junit" / "pytest-results-windows-2022-3.13" / "x.xml") == "windows-2022-3.13"


def test_rendered_file_has_no_trailing_whitespace(tmp_path: Path, monkeypatch) -> None:
    """The pre-commit hygiene job runs ``trailing-whitespace`` over this file.

    pytest pads captured lines (``E     AssertionError: ...``) and indents blank
    ones. Those landed verbatim in the fenced block, so CI failed its own
    hygiene job on the ``CI-errors.md`` commit it had just pushed.
    """
    mod = _load()
    monkeypatch.setattr(mod, "OUTPUT", tmp_path / "CI-errors.md")
    _write_source_at(tmp_path, "tests/test_x.py", 12)
    d = tmp_path / "junit" / "pytest-results-ubuntu-22.04-3.12"
    d.mkdir(parents=True)
    f = d / "pytest-results.xml"
    f.write_bytes(
        _junit(
            '<testcase classname="tests.test_x" name="test_boom">'
            '<failure message="boom">'
            "tests/test_x.py:12: in test_boom\n"
            "  \n"
            "E     AssertionError: boom   "
            "</failure></testcase>"
        )
    )

    assert mod.main([str(f)]) == 0

    text = (tmp_path / "CI-errors.md").read_text(encoding="utf-8")
    offenders = [line for line in text.splitlines() if line != line.rstrip()]
    assert offenders == [], f"trailing whitespace would fail the hygiene hook: {offenders!r}"


def _write_source_at(tmp_path: Path, path: str, line: int, text: str = "code") -> None:
    """Create a repo-relative source file with a non-blank line at *line*."""
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [""] * line
    lines[line - 1] = text
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _junit_dir(tmp_path: Path) -> Path:
    d = tmp_path / "junit" / "pytest-results-ubuntu-22.04-3.12"
    d.mkdir(parents=True)
    return d


def test_source_sha_is_stamped_in_generated_report(tmp_path: Path, monkeypatch) -> None:
    """The report states which commit it describes, so a stale doc cannot masquerade as current."""
    mod = _load()
    monkeypatch.setattr(mod, "OUTPUT", tmp_path / "CI-errors.md")
    monkeypatch.setenv("GITHUB_SHA", "abc123def456")
    _write_source_at(tmp_path, "tests/test_x.py", 12)
    f = _junit_dir(tmp_path) / "pytest-results.xml"
    f.write_bytes(_junit(_failing_case()))

    assert mod.main([str(f)]) == 0
    text = (tmp_path / "CI-errors.md").read_text(encoding="utf-8")
    assert "Source SHA: `abc123def456`" in text
    assert "### 1. `tests.test_x.test_boom`" in text


def test_stale_cited_line_is_dropped_not_reported_as_current(tmp_path: Path, monkeypatch) -> None:
    """A cited line that is now blank belongs to a fixed failure, not the current run."""
    mod = _load()
    monkeypatch.setattr(mod, "OUTPUT", tmp_path / "CI-errors.md")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    _write_source_at(tmp_path, "tests/test_x.py", 12, text="")  # cited line now blank
    f = _junit_dir(tmp_path) / "pytest-results.xml"
    f.write_bytes(_junit(_failing_case()))

    assert mod.main([str(f)]) == 0
    text = (tmp_path / "CI-errors.md").read_text(encoding="utf-8")
    assert "Stale entries dropped" in text
    assert "tests/test_x.py:12" in text
    assert "### 1." not in text


def test_stale_cited_file_is_dropped(tmp_path: Path, monkeypatch) -> None:
    """A cited file that no longer exists is stale too."""
    mod = _load()
    monkeypatch.setattr(mod, "OUTPUT", tmp_path / "CI-errors.md")
    f = _junit_dir(tmp_path) / "pytest-results.xml"
    f.write_bytes(_junit(_failing_case()))

    assert mod.main([str(f)]) == 0
    text = (tmp_path / "CI-errors.md").read_text(encoding="utf-8")
    assert "Stale entries dropped" in text
    assert "### 1." not in text


def test_notify_job_depends_on_every_other_workflow_job() -> None:
    """The failure-notification job must watch all jobs from one list, not duplicated tables."""
    text = _WORKFLOW.read_text(encoding="utf-8")
    jobs_section = text[text.index("\njobs:\n") + len("\njobs:\n") :]
    every_job = set(re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", jobs_section, re.MULTILINE))
    notify_start = text.index("\n  notify:\n") + len("\n  notify:\n")
    tail = text[notify_start:]
    next_section = re.search(r"^\S", tail, re.MULTILINE)
    block = tail[: next_section.start()] if next_section else tail

    needs = re.search(r"^    needs: \[(?P<ids>[^\]]+)\]\s*$", block, re.MULTILINE)
    assert needs is not None, "notify job needs an explicit needs list"
    watched = {part.strip() for part in needs.group("ids").split(",")}
    expected = every_job - {"notify"}
    assert watched == expected, (
        f"notify must watch every job; missing={sorted(expected - watched)}, extra={sorted(watched - expected)}"
    )
    assert "if: always()" in block
    assert "toJSON(needs)" in block, "job results should be generated from needs so the table cannot drift"
    assert not re.search(r"needs\.[a-z][a-z0-9-]*\.result", block), "no hard-coded per-job result rows"
