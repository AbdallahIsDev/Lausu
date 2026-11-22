"""Guard against workflow YAML drifting away from the collector's workflow list."""

from __future__ import annotations

import re
from pathlib import Path

from scripts.ci_errors.analyze import COLLECTOR_EXCLUSIONS, TRACKED_WORKFLOWS

_ROOT = Path(__file__).resolve().parents[2]
_NAME_RE = re.compile(r'^name:\s*["\']?([^"\'\n]+?)["\']?\s*$', re.MULTILINE)


def _workflow_names() -> set[str]:
    names: set[str] = set()
    for path in (_ROOT / ".github" / "workflows").glob("*.yml"):
        match = _NAME_RE.search(path.read_text(encoding="utf-8"))
        if match:
            names.add(match.group(1).strip())
    return names


def test_workflow_names_match_tracked_and_excluded_lists() -> None:
    names = _workflow_names()
    assert names == TRACKED_WORKFLOWS | COLLECTOR_EXCLUSIONS
    assert not (TRACKED_WORKFLOWS & COLLECTOR_EXCLUSIONS)


def test_exclusions_are_not_stale() -> None:
    assert _workflow_names() >= COLLECTOR_EXCLUSIONS
