"""Focused tests for log extraction, caps and classification."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from scripts.ci_errors.extract import (
    MAX_EXCERPT_CHARS,
    MAX_EXCERPT_LINES,
    classify,
    drop_secret_lines,
    error_excerpt,
    location_and_error,
    pytest_failures,
    strip_ansi,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ci_errors"


def test_strip_ansi_removes_sgr_and_osc() -> None:
    raw = "\x1b[31mRED\x1b[0m \x1b]0;title\x07ok"
    plain = strip_ansi(raw)
    assert plain == "RED ok"
    assert "\x1b" not in plain


def test_excerpt_caps_lines_bytes_and_drops_secrets() -> None:
    lines = ["##[error] boom", "token: ghp_abcdefghijklmnopqrstuvwxyz0123456789"]
    lines += [f"context line {i}" for i in range(80)]
    excerpt = error_excerpt("\n".join(lines))
    assert len(excerpt.splitlines()) <= MAX_EXCERPT_LINES
    assert len(excerpt.encode("utf-8")) <= MAX_EXCERPT_CHARS
    assert "ghp_" not in excerpt
    assert "boom" in excerpt


def test_excerpt_hard_caps_one_giant_line_from_the_tail() -> None:
    excerpt = error_excerpt("##[error] " + "x" * 20000)
    assert len(excerpt.encode("utf-8")) <= MAX_EXCERPT_CHARS
    assert "truncated" in excerpt


def test_excerpt_without_marker_keeps_last_lines() -> None:
    excerpt = error_excerpt("\n".join(f"line {i}" for i in range(100)))
    assert "line 99" in excerpt
    assert "line 0" not in excerpt
    assert len(excerpt.splitlines()) <= MAX_EXCERPT_LINES


def test_drop_secret_lines_keeps_benign_text() -> None:
    kept = drop_secret_lines(["ordinary failure", "password=hunter2", "secret: abc", "ghp_" + "a" * 30, "ok"])
    assert kept == ["ordinary failure", "ok"]


@pytest.mark.parametrize(
    ("step", "expected"),
    [
        ("Run tests with coverage", "pytest"),
        ("Ruff format check", "ruff"),
        ("mypy ratchet", "mypy ratchet"),
        ("Pyrefly check", "pyrefly"),
        ("Lint (Biome)", "eslint/vitest"),
        ("vitest run", "eslint/vitest"),
        ("Run rustsec/audit-check@v2", "cargo test/clippy/audit"),
        ("cargo clippy --all-targets", "cargo test/clippy/audit"),
        ("Run pre-commit hygiene hooks", "pre-commit hygiene"),
        ("Analyze (rust)", "CodeQL"),
        ("Post-build verification gate (bundle)", "gate"),
        ("Freeze with Nuitka", "build/freeze"),
        ("Run tests", "other"),
    ],
)
def test_classify(step: str, expected: str) -> None:
    assert classify(step, "") == expected


def test_classify_cancelled_conclusion_wins() -> None:
    assert classify("Run tests with coverage", "", "cancelled") == "infrastructure/cancelled/timeout"


def test_pytest_nodes_from_log_text() -> None:
    log = (_FIXTURES / "pytest_log_synthetic.txt").read_text(encoding="utf-8")
    failures = pytest_failures(log)
    assert [item.node_id for item in failures] == [
        "tests/clipboard/test_win32_send_ctrl_v.py::test_input_struct_layout",
        "tests/test_stream_lifecycle_module.py::test_retry_ladder",
    ]
    assert failures[0].location == "tests/clipboard/test_win32_send_ctrl_v.py:17"
    assert "expected 40, got 32" in failures[0].message
    assert failures[1].location == "tests/test_stream_lifecycle_module.py:88"
    assert "ladder drifted" in failures[1].message


def test_location_and_error_from_real_internal_error_log() -> None:
    log = (_FIXTURES / "log_45024078547_137214309926.txt").read_text(encoding="utf-8")
    location, error = location_and_error(log)
    assert location == "(unknown location)"
    assert "AssertionError" in error


def test_error_marker_prefers_first_failure_not_last_success() -> None:
    excerpt = error_excerpt("all good\n##[error] first failure\n" + "\n".join(f"ok {i}" for i in range(50)))
    assert "first failure" in excerpt
    assert "ok 49" not in excerpt
    assert re.search(r"error", excerpt, re.IGNORECASE)
