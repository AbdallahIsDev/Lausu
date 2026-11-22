"""Deterministic markdown rendering with size-capped recent-failure rotation."""

from __future__ import annotations

from pathlib import Path

from .analyze import REPORT_CAP_BYTES
from .types import Entry, ReportModel

_SECTIONS = (
    ("Currently failing", "currently_failing"),
    ("Recent failures", "recent_failures"),
    ("Resolved recently", "resolved_recently"),
)


def _fence(text: str) -> str:
    return "```text\n" + text.replace("```", "~~~") + "\n```"


def _entry_lines(entry: Entry, index: int) -> list[str]:
    lines = [
        f"### {index}. {entry.workflow} — {entry.conclusion}",
        "",
        f"- Run: [{entry.run_id}]({entry.url}) (attempt {entry.run_attempt})",
        f"- Event: {entry.event} · Branch: {entry.branch}",
        f"- Commit: `{entry.sha}` — {entry.subject}",
        f"- Job: {entry.job} · Leg: {entry.leg or 'n/a'}",
        f"- Step: {entry.step}",
        f"- Category: {entry.classification}",
    ]
    if entry.fixing_run_id is not None:
        lines.append(f"- Fixed by: [{entry.fixing_run_id}]({entry.fixing_url}) (success)")
    lines += ["", "- Error excerpt:", "", _fence(entry.excerpt), ""]
    if entry.pytest_failures:
        lines += ["- Failing pytest nodes:"]
        for failure in entry.pytest_failures:
            location = f" @ `{failure.location}`" if failure.location != "(unknown location)" else ""
            lines.append(f"  - `{failure.node_id}`{location} — {failure.message}")
        lines.append("")
    return lines


def _render(model: ReportModel, recent: list[Entry], dropped: int) -> str:
    lines = [
        "# CI Errors",
        "",
        f"> Generated: {model.generated_at}",
        f"> Data branch commit: `{model.data_commit}`",
        "",
    ]
    if dropped:
        lines += [f"> Recent failures rotated out to fit the size cap: {dropped}.", ""]
    for title, attribute in _SECTIONS:
        entries = recent if attribute == "recent_failures" else getattr(model, attribute)
        lines += [f"## {title}", ""]
        if not entries:
            lines += ["_None._", ""]
            continue
        for index, entry in enumerate(entries, 1):
            lines += _entry_lines(entry, index)
    return "\n".join(lines).rstrip() + "\n"


def render_report(model: ReportModel) -> str:
    """Drop oldest Recent failures until the report fits, never Currently failing."""
    recent = list(model.recent_failures)
    dropped = 0
    while True:
        text = _render(model, recent, dropped)
        if len(text.encode("utf-8")) <= REPORT_CAP_BYTES or not recent:
            return text
        recent.pop()
        dropped += 1


def write_report(path: str | Path, text: str) -> None:
    """Explicit LF bytes: write_text translates newlines on Windows."""
    Path(path).write_bytes(text.encode("utf-8"))
