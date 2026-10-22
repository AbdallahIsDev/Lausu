"""Push-to-talk hotkey compatibility rules.

Push-to-talk needs a real key press/release pair: a modifier-only chord never
reports a release on every platform, and macOS never reports Caps Lock's
release at all.
"""

from __future__ import annotations

from types import SimpleNamespace

from voice_typer.server.config_validators import validate_config, validate_config_update
from voice_typer.server.config_validators.cross_field import _check_cross_field_push_to_talk
from voice_typer.server.config_validators.hotkey import _check_push_to_talk


class TestPushToTalkHelper:
    def test_modifier_only_is_flagged(self) -> None:
        code, _message = _check_push_to_talk("<ctrl>+<shift>")
        assert code == "ptt_modifier_only"

    def test_caps_lock_is_flagged(self) -> None:
        code, _message = _check_push_to_talk("<caps_lock>")
        assert code == "ptt_caps_lock"

    def test_regular_key_passes(self) -> None:
        assert _check_push_to_talk("<f9>") == (None, None)

    def test_blank_value_is_ignored(self) -> None:
        assert _check_push_to_talk("") == (None, None)
        assert _check_push_to_talk(None) == (None, None)


class TestCrossFieldPushToTalk:
    def test_toggle_mode_ignores_modifier_only(self) -> None:
        assert _check_cross_field_push_to_talk("<ctrl>+<shift>", "toggle") == []

    def test_push_to_talk_rejects_modifier_only(self) -> None:
        errors = _check_cross_field_push_to_talk("<ctrl>+<shift>", "push_to_talk")
        assert len(errors) == 1
        assert "hotkey is invalid for push-to-talk" in errors[0]
        assert "modifier-only" in errors[0]

    def test_push_to_talk_rejects_caps_lock(self) -> None:
        errors = _check_cross_field_push_to_talk("<caps_lock>", "push_to_talk")
        assert len(errors) == 1
        assert "Caps Lock" in errors[0]

    def test_push_to_talk_accepts_regular_key(self) -> None:
        assert _check_cross_field_push_to_talk("<f9>", "push_to_talk") == []

    def test_missing_mode_skips_check(self) -> None:
        assert _check_cross_field_push_to_talk("<ctrl>+<shift>", None) == []


class TestSetConfigPushToTalk:
    def test_switching_to_push_to_talk_with_modifier_only_hotkey_fails(self) -> None:
        current = SimpleNamespace(hotkey="<ctrl>+<shift>", recording_mode="toggle")
        _validated, errors = validate_config_update({"recording_mode": "push_to_talk"}, current=current)
        assert any("push-to-talk" in error for error in errors)

    def test_switching_to_toggle_with_modifier_only_hotkey_passes(self) -> None:
        current = SimpleNamespace(hotkey="<ctrl>+<shift>", recording_mode="toggle")
        _validated, errors = validate_config_update({"recording_mode": "toggle"}, current=current)
        assert errors == []

    def test_hotkey_change_to_modifier_only_while_push_to_talk_fails(self) -> None:
        current = SimpleNamespace(hotkey="<f9>", recording_mode="push_to_talk")
        _validated, errors = validate_config_update({"hotkey": "<ctrl>+<shift>"}, current=current)
        assert any("push-to-talk" in error for error in errors)

    def test_hotkey_change_to_caps_lock_while_push_to_talk_fails(self) -> None:
        current = SimpleNamespace(hotkey="<f9>", recording_mode="push_to_talk")
        _validated, errors = validate_config_update({"hotkey": "<caps_lock>"}, current=current)
        assert any("Caps Lock" in error for error in errors)

    def test_unrelated_update_ignores_persisted_invalid_push_to_talk(self) -> None:
        current = SimpleNamespace(hotkey="<ctrl>+<shift>", recording_mode="push_to_talk")
        _validated, errors = validate_config_update({"language": "de"}, current=current)
        assert errors == []


class TestFullConfigValidation:
    def test_modifier_only_push_to_talk_is_rejected(self) -> None:
        cfg = SimpleNamespace(hotkey="<ctrl>+<shift>", recording_mode="push_to_talk")
        errors = validate_config(cfg)
        assert any("push-to-talk" in error for error in errors)

    def test_caps_lock_push_to_talk_is_rejected(self) -> None:
        cfg = SimpleNamespace(hotkey="<caps_lock>", recording_mode="push_to_talk")
        errors = validate_config(cfg)
        assert any("Caps Lock" in error for error in errors)

    def test_modifier_only_toggle_is_accepted(self) -> None:
        cfg = SimpleNamespace(hotkey="<ctrl>+<shift>", recording_mode="toggle")
        assert validate_config(cfg) == []
