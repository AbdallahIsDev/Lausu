from __future__ import annotations

import json
from pathlib import Path

import pytest
from voice_typer.server.config import Config


@pytest.fixture
def isolated_config_dir(tmp_config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("VOICE_TYPER_CONFIG_DIR", raising=False)
    return tmp_config_dir


def _write(config_dir: Path, payload: dict) -> None:
    (config_dir / "config.json").write_text(
        json.dumps({"schema_version": 3, "asr_backend": "whisper", **payload}),
        encoding="utf-8",
    )


def test_invalid_repaste_hotkey_resets_to_empty(isolated_config_dir: Path) -> None:
    _write(isolated_config_dir, {"repaste_hotkey": "<f25>"})

    instance = Config.load()

    assert instance.repaste_hotkey == ""
    assert any("repaste_hotkey" in w and "reset to ''" in w for w in instance.last_load_warnings), (
        f"expected a reset warning for repaste_hotkey. Got: {instance.last_load_warnings!r}"
    )


def test_ptt_hotkey_reset_to_platform_default(isolated_config_dir: Path) -> None:
    from voice_typer.server.config_validators.hotkey import _check_push_to_talk

    _write(isolated_config_dir, {"recording_mode": "push_to_talk", "hotkey": "<alt>"})

    instance = Config.load()

    assert instance.hotkey != "<alt>"
    assert _check_push_to_talk(instance.hotkey)[0] is None
    assert any("push-to-talk" in w for w in instance.last_load_warnings), (
        f"expected a push-to-talk reset warning. Got: {instance.last_load_warnings!r}"
    )
