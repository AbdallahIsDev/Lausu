"""Log-text extraction: ANSI, secrets, error windows, pytest nodes, categories."""

from __future__ import annotations

import re

from .types import PytestFailure

_ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-_])")
_SECRET_LINE_RE = re.compile(
    r"(?i)(gh[pousr]_[A-Za-z0-9]{16,}|(?:token|secret|password|passwd|api[_-]?key)"
    r"\s*[:=]\s*\S|-----BEGIN [A-Z ]+PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._-]{16,})"
)
_ERROR_MARKER_RE = re.compile(
    r"(?i)(##\[error\]|assertionerror|internalerror|traceback|fatal|panic|critical"
    r"|\berror\b|\bfailed\b|exception|exit code [1-9])"
)
_LOG_PREFIX_RE = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z\s*(?:\[gw\d+\]\s*)?")
_FRAME_RE = re.compile(r'^\s*(?:E\s+|INTERNALERROR>\s+)*File "([^"]+)", line (\d+)')
_SHORT_FRAME_RE = re.compile(r"^([\w\-./\\]+\.py):(\d+):")
_FAILED_NODE_RE = re.compile(
    r"\b(?:FAILED|ERROR)\s+(?P<node>[\w./\\\-]+(?:\.py)?::\S+)"
    r"(?:\s+-\s+(?P<message>.*))?"
)
_ASSERTION_RE = re.compile(r"(?:AssertionError|Assertion failed|Error|FAILED)(?::\s*(?P<message>.*))?")

MAX_EXCERPT_LINES = 40
MAX_EXCERPT_CHARS = 4096


def strip_ansi(text: str) -> str:
    """Remove SGR/OSC escape sequences, including split colour resets."""
    return _ANSI_RE.sub("", text)


def drop_secret_lines(lines: list[str]) -> list[str]:
    """Drop any line that carries a credential instead of redacting it."""
    return [line for line in lines if not _SECRET_LINE_RE.search(line)]


def _normalized_lines(text: str) -> list[str]:
    lines = []
    for raw in strip_ansi(text).splitlines():
        line = _LOG_PREFIX_RE.sub("", raw.rstrip())
        lines.append(line.strip())
    return lines


def error_excerpt(text: str, max_lines: int = MAX_EXCERPT_LINES, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """Return <=40 lines around the first error marker, hard-capped at 4 KB.

    The tail is kept when truncating: the final exception line is the part a
    reader needs, and GH job logs pad successful steps ahead of it.
    """
    lines = drop_secret_lines(_normalized_lines(text))
    marker = next((i for i, line in enumerate(lines) if _ERROR_MARKER_RE.search(line)), None)
    if marker is None:
        window = lines[-max_lines:]
    else:
        window = lines[marker : marker + max_lines]
        if len(window) < max_lines:
            start = max(0, marker - (max_lines - len(window)))
            window = lines[start : marker + max_lines]
    trimmed = "\n".join(line.rstrip() for line in window).strip()
    if len(trimmed) > max_chars:
        header = "... (truncated)\n"
        kept: list[str] = []
        for line in reversed(trimmed.splitlines()):
            candidate = "\n".join([line, *kept])
            if len(candidate) + len(header) > max_chars:
                break
            kept.insert(0, line)
        trimmed = header + trimmed[-(max_chars - len(header)) :] if not kept else header + "\n".join(kept)
    return trimmed or "(no error lines)"


_RULES = (
    ("CodeQL", r"codeql|analyze \((?:rust|python|javascript|java)\)"),
    ("pytest", r"pytest|tests with coverage"),
    ("ruff", r"\bruff\b"),
    ("pyrefly", r"pyrefly"),
    ("mypy ratchet", r"mypy"),
    ("eslint/vitest", r"eslint|vitest|biome|jest|typecheck"),
    ("pre-commit hygiene", r"pre-commit|hygiene|trailing-whitespace|end-of-file-fixer"),
    ("gate", r"gate|drift guard|selfcheck"),
    ("cargo test/clippy/audit", r"cargo|clippy|audit|rustsec"),
    ("build/freeze", r"build|freeze|nuitka|bundle|onefile|tauri"),
)
_INFRA_RE = re.compile(r"\b(cancelled|timed out|timeout|runner lost|no space left)\b")


def classify(step: str, text: str = "", conclusion: str = "") -> str:
    """Map a failing step plus its error text to a stable category label.

    Step names win over log text: a gate log mentions cargo and a hygiene log
    mentions builds, so text-only matching mislabels both.
    """
    if conclusion in {"cancelled", "timed_out"}:
        return "infrastructure/cancelled/timeout"
    for hay in (step.lower(), text[:1500].lower()):
        if _INFRA_RE.search(hay):
            return "infrastructure/cancelled/timeout"
        for label, pattern in _RULES:
            if re.search(pattern, hay):
                return label
    return "other"


def location_and_error(text: str) -> tuple[str, str]:
    """Deepest repo traceback frame and the trailing assertion line.

    Mirrors scripts/ci/write_ci_errors.py: its files are JUnit XML, while job
    logs have no XML artifacts, so the same heuristics run over step text.
    """
    lines = _normalized_lines(text)
    location = "(unknown location)"
    for line in lines:
        match = _FRAME_RE.match(line) or _SHORT_FRAME_RE.match(line)
        if match is None:
            continue
        path, lineno = match.group(1), match.group(2)
        norm = path.replace("\\", "/")
        repo_at = norm.lower().rfind("lausu/")
        short = norm[repo_at + len("lausu/") :] if repo_at != -1 else norm
        if short.startswith(("tests/", "voice_typer/")):
            location = f"{short}:{lineno}"
    error = "(no error line)"
    for line in reversed(lines):
        if re.match(r"^(?:E\s+|INTERNALERROR>\s+E\s+)", line):
            match = _ASSERTION_RE.search(line)
            if match:
                error = f"AssertionError: {match.group('message')}" if match.group("message") else "AssertionError"
                break
    return location, error


def pytest_failures(text: str) -> tuple[PytestFailure, ...]:
    """Extract failed node ids and assertion messages from a pytest job log.

    JUnit XML artifacts are not part of the API fixtures, so this applies the
    write_ci_errors.py node/location heuristics to the failed-step log text.
    """
    lines = _normalized_lines(text)
    found: dict[str, PytestFailure] = {}
    for index, line in enumerate(lines):
        match = _FAILED_NODE_RE.search(line)
        if match is None:
            continue
        node = match.group("node")
        message = (match.group("message") or "").strip()
        if not message:

            def _assertion(later: str) -> str | None:
                found = _ASSERTION_RE.search(later)
                return found.group(0) if found else None

            message = next(
                (text for text in (_assertion(later) for later in lines[index + 1 : index + 21]) if text),
                "(no assertion message)",
            )
        window = lines[index + 1 : index + 31]
        next_failure = next((offset for offset, later in enumerate(window) if _FAILED_NODE_RE.search(later)), None)
        if next_failure is not None:
            window = window[:next_failure]
        location, _ = location_and_error("\n".join(window))
        found.setdefault(node, PytestFailure(node, location, message.strip()))
    return tuple(found.values())
