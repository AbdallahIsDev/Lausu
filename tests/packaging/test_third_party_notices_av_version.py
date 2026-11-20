"""Keep the PyAV version in the third-party notice in lockstep with the hash lock."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "requirements-lock.txt"
NOTICE = ROOT / "docs" / "THIRD_PARTY_NOTICES.md"


def test_notice_names_the_locked_pyav_version() -> None:
    match = re.search(r"(?m)^av==(\d+\.\d+\.\d+)\b", LOCK.read_text(encoding="utf-8"))
    assert match, "no locked PyAV version found"
    locked = match.group(1)
    text = NOTICE.read_text(encoding="utf-8")
    named = set(re.findall(r"\bav==(\d+\.\d+\.\d+)", text))
    named |= set(re.findall(r"\bPyAV (\d+\.\d+\.\d+)", text))
    assert named == {locked}, f"notice names PyAV {sorted(named)}, lock pins {locked}"
