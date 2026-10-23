"""Cross-layer parity: Python validators and the renderer picker agree.

The fixture is shared verbatim with
``voice_typer/client/src/renderer/src/components/__tests__/hotkey-verdict-parity.test.ts``
so a new validation rule cannot land on one side alone.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from voice_typer.server.config_validators import hotkey as hotkey_validators

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hotkey_verdicts.json"


def _load_cases() -> list[dict[str, Any]]:
    with _FIXTURE.open("r", encoding="utf-8") as f:
        return json.load(f)["cases"]


def _verdict(hotkey: str, push_to_talk: bool, platform: str) -> str | None:
    code, _ = hotkey_validators._validate_hotkey_code(hotkey)
    if code is None and push_to_talk:
        code, _ = hotkey_validators._check_push_to_talk(hotkey, platform)
    return code


@pytest.mark.parametrize(
    "case",
    _load_cases(),
    ids=lambda case: f"{case['platform']}-{case['hotkey'] or '<blank>'}-ptt={case['pushToTalk']}",
)
def test_python_matches_shared_verdict_fixture(case: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hotkey_validators, "_platform_key", lambda: case["platform"])
    assert _verdict(case["hotkey"], case["pushToTalk"], case["platform"]) == case["code"]
