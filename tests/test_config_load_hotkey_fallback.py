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


def test_legacy_windows_caps_ptt_config_survives_untouched(
    isolated_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caps Lock is a valid push-to-talk key on Windows; the loader must not rewrite it."""
    from voice_typer.server.config_validators import hotkey as hotkey_validators

    monkeypatch.setattr(hotkey_validators, "_platform_key", lambda: "win32")
    _write(isolated_config_dir, {"recording_mode": "push_to_talk", "hotkey": "<caps_lock>"})

    instance = Config.load()

    assert instance.hotkey == "<caps_lock>"
    assert not any("push-to-talk" in w for w in instance.last_load_warnings), (
        f"Windows caps push-to-talk must not warn. Got: {instance.last_load_warnings!r}"
    )


def test_canonical_equal_repaste_pair_is_cleared_with_one_warning(
    isolated_config_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Loader clears a repaste that canonicalises to the dictation spec."""
    _write(
        isolated_config_dir,
        {"hotkey": "<ctrl>+<f9>", "repaste_hotkey": "<ctrl_l>+<f9>"},
    )

    with caplog.at_level("WARNING", logger="voice_typer.server.config"):
        instance = Config.load()

    assert instance.repaste_hotkey == ""
    assert any("duplicates the dictation hotkey" in w for w in instance.last_load_warnings), (
        f"expected a duplicate-clear warning. Got: {instance.last_load_warnings!r}"
    )
    warnings = [r for r in caplog.records if "duplicates the dictation hotkey" in r.getMessage()]
    assert len(warnings) == 1, f"expected exactly one duplicate warning, got {len(warnings)}"


def test_macos_caps_ptt_config_is_rewritten_to_a_release_reporting_key(
    isolated_config_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from voice_typer.server.config_validators import hotkey as hotkey_validators

    monkeypatch.setattr(hotkey_validators, "_platform_key", lambda: "darwin")
    _write(isolated_config_dir, {"recording_mode": "push_to_talk", "hotkey": "<caps_lock>"})

    with caplog.at_level("WARNING", logger="voice_typer.server.config"):
        instance = Config.load()

    assert instance.hotkey == "<f2>"
    assert any("push-to-talk" in w for w in instance.last_load_warnings)
    assert len([r for r in caplog.records if "push-to-talk" in r.getMessage()]) == 1
