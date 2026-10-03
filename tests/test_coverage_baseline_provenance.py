from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import coverage_ratchet_check as ratchet  # noqa: E402


@pytest.fixture
def baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A baseline carrying hand-written prose that cites a stale measurement."""
    path = tmp_path / "coverage-baseline.json"
    path.write_text(
        json.dumps(
            {
                "total_coverage": 80.0,
                "_comment": "prose citing a now-stale 84.84% measurement",
                "_updated": "2020-01-01",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ratchet, "BASELINE_PATH", path)
    return path


def test_regenerate_refreshes_machine_owned_provenance(
    baseline: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`_updated` / `_source` must never drift from the number they describe.

    Both are machine-written, so regenerating them is the only way their
    recorded date and percentage can be trusted.
    """
    assert ratchet.regenerate(85.5) == 0
    data = json.loads(baseline.read_text(encoding="utf-8"))

    assert data["total_coverage"] == 85.5
    assert data["_updated"] == date.today().isoformat()
    assert "85.5" in data["_source"]
    assert "2020-01-01" not in data["_source"]


def test_regenerate_warns_that_comment_is_hand_maintained(
    baseline: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`_comment` is narrative and is copied verbatim, never rewritten.

    A refreshed number sitting next to an unrefreshed sentence lends the
    stale prose false credibility, so the run must say so explicitly.
    """
    ratchet.regenerate(85.5)
    out = capsys.readouterr().out

    assert "HAND-MAINTAINED" in out
    assert "stale" in out.lower()


def test_regenerate_preserves_comment_verbatim(baseline: Path) -> None:
    """The prose is carried forward unchanged - the warning, not a rewrite."""
    original = json.loads(baseline.read_text(encoding="utf-8"))["_comment"]

    ratchet.regenerate(85.5)

    assert json.loads(baseline.read_text(encoding="utf-8"))["_comment"] == original


def test_regenerate_does_not_warn_when_no_comment_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A baseline with no prose must not emit the prose warning."""
    path = tmp_path / "coverage-baseline.json"
    path.write_text(json.dumps({"total_coverage": 80.0}), encoding="utf-8")
    monkeypatch.setattr(ratchet, "BASELINE_PATH", path)

    ratchet.regenerate(85.5)

    assert "HAND-MAINTAINED" not in capsys.readouterr().out
