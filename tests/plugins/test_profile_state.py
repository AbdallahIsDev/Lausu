"""Clean-exit and scoped microphone grants before the dedicated profile launches."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tools.internal_plugins._common.bridge import profile_state


@pytest.fixture
def prefs(tmp_path: Path):
    path = tmp_path / "Default" / "Preferences"
    path.parent.mkdir()
    path.write_text(
        json.dumps({"profile": {"exit_type": "Crashed"}, "unrelated": {"keep": 1}}),
        encoding="utf-8",
    )
    return path


def test_prepare_profile_marks_clean_exit_and_grants_only_platform_origins(prefs: Path):
    assert profile_state.prepare_profile(str(prefs.parent.parent)) is True
    data = json.loads(prefs.read_text(encoding="utf-8"))
    assert data["profile"]["exit_type"] == "Normal"
    assert data["unrelated"] == {"keep": 1}
    mic = data["content_settings"]["exceptions"]["media_stream_mic"]
    assert set(mic) == set(profile_state.MIC_ORIGINS)
    assert all(entry["setting"] == 1 for entry in mic.values())


def test_prepare_profile_is_idempotent(prefs: Path):
    assert profile_state.prepare_profile(str(prefs.parent.parent)) is True
    assert profile_state.prepare_profile(str(prefs.parent.parent)) is False


def test_explicit_microphone_block_is_not_overridden(prefs: Path):
    data = json.loads(prefs.read_text(encoding="utf-8"))
    data["content_settings"] = {"exceptions": {"media_stream_mic": {"https://chatgpt.com:443,*": {"setting": 2}}}}
    prefs.write_text(json.dumps(data), encoding="utf-8")

    profile_state.prepare_profile(str(prefs.parent.parent))

    mic = json.loads(prefs.read_text(encoding="utf-8"))["content_settings"]["exceptions"]["media_stream_mic"]
    assert mic["https://chatgpt.com:443,*"]["setting"] == 2


def test_running_profile_preferences_are_left_alone(prefs: Path):
    before = prefs.read_text(encoding="utf-8")
    profile_state.apply_before_launch(str(prefs.parent.parent), "Default", lambda _dir: [123])
    assert prefs.read_text(encoding="utf-8") == before
