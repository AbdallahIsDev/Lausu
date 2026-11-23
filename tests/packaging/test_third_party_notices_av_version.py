"""Keep the PyAV version in the third-party notice in lockstep with the hash lock."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "requirements-lock.txt"
NOTICE = ROOT / "docs" / "THIRD_PARTY_NOTICES.md"


def test_pyav_version_is_gone_from_lock_and_notice() -> None:
    # ADR-0031 Phase 1: PyAV is removed from both surfaces together so the
    # GPL DLLs it carried cannot come back through a stale pin.
    assert not re.search(r"(?m)^av==", LOCK.read_text(encoding="utf-8")), "PyAV still in lock"
    text = NOTICE.read_text(encoding="utf-8")
    assert not re.search(r"\bav==\d+\.\d+\.\d+", text), "PyAV version still in notice"
    assert "## PyAV" not in text, "PyAV section still in notice"
