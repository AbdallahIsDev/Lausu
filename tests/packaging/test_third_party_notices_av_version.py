"""Keep the retired media runtime's pin absent from lock and notices."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "requirements-lock.txt"
NOTICE = ROOT / "docs" / "THIRD_PARTY_NOTICES.md"
# Any single-word heading naming the retired media wrapper is a regression.
_RETIRED_SECTION_RE = re.compile(r"(?im)^##\s+\S*av\S*\s*$")


def test_retired_media_pin_is_gone_from_lock_and_notice() -> None:
    assert not re.search(r"(?m)^av==", LOCK.read_text(encoding="utf-8")), "legacy media pin still in lock"
    text = NOTICE.read_text(encoding="utf-8")
    assert not re.search(r"\bav==\d+\.\d+\.\d+", text), "legacy media version still in notice"
    assert not _RETIRED_SECTION_RE.search(text), "legacy media section still in notice"
