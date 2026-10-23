"""Push-to-talk hotkey compatibility rules.

Push-to-talk needs a real key press/release pair. A modifier-only chord never
reports one on any platform (macOS Fn/Globe is the exception: the event tap
reports its own down/up pair), and Caps Lock only fails on macOS, whose tap
never reports its release. Windows and Linux listeners emit KEY_UP:CapsLock,
so Caps Lock push-to-talk is a supported Windows/Linux trigger.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from voice_typer.server.config_validators import hotkey as hotkey_validators, validate_config, validate_config_update
from voice_typer.server.config_validators.cross_field import _check_cross_field_push_to_talk
from voice_typer.server.config_validators.hotkey import _check_push_to_talk, _ptt_fallback_hotkey


class TestPushToTalkHelper:
    def test_modifier_only_is_flagged(self) -> None:
        code, _message = _check_push_to_talk("<ctrl>+<shift>", "win32")
        assert code == "ptt_modifier_only"

    def test_caps_lock_is_flagged_on_macos_only(self) -> None:
        assert _check_push_to_talk("<caps_lock>", "darwin")[0] == "ptt_caps_lock"

    @pytest.mark.parametrize("platform", ["win32", "linux"])
    def test_caps_lock_is_accepted_where_the_listener_reports_release(self, platform: str) -> None:
        assert _check_push_to_talk("<caps_lock>", platform) == (None, None)

    def test_fn_globe_is_accepted_on_macos_only(self) -> None:
        assert _check_push_to_talk("<fn>", "darwin") == (None, None)
        assert _check_push_to_talk("<globe>", "darwin") == (None, None)
        assert _check_push_to_talk("<fn>", "win32")[0] == "ptt_modifier_only"
        assert _check_push_to_talk("<fn>", "linux")[0] == "ptt_modifier_only"

    def test_regular_key_passes(self) -> None:
        assert _check_push_to_talk("<f9>", "win32") == (None, None)

    def test_blank_value_is_ignored(self) -> None:
        assert _check_push_to_talk("", "darwin") == (None, None)
        assert _check_push_to_talk(None, "darwin") == (None, None)

    def test_default_platform_is_the_running_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hotkey_validators, "_platform_key", lambda: "darwin")
        assert _check_push_to_talk("<caps_lock>")[0] == "ptt_caps_lock"
        monkeypatch.setattr(hotkey_validators, "_platform_key", lambda: "win32")
        assert _check_push_to_talk("<caps_lock>") == (None, None)


class TestPttFallbackHelper:
    def test_toggle_mode_needs_no_fallback(self) -> None:
        assert _ptt_fallback_hotkey("<caps_lock>", "toggle", "darwin") is None

    def test_valid_push_to_talk_key_needs_no_fallback(self) -> None:
        assert _ptt_fallback_hotkey("<caps_lock>", "push_to_talk", "win32") is None

    def test_macos_caps_falls_back_to_a_release_reporting_key(self) -> None:
        assert _ptt_fallback_hotkey("<caps_lock>", "push_to_talk", "darwin") == "<f2>"

    def test_modifier_only_falls_back_too(self) -> None:
        # `<caps_lock>` is the platform default and is a valid PTT key here.
        assert _ptt_fallback_hotkey("<ctrl>+<shift>", "push_to_talk", "linux") == "<caps_lock>"
        # macOS cannot use Caps Lock for PTT, so the last-resort key wins.
        assert _ptt_fallback_hotkey("<ctrl>+<shift>", "push_to_talk", "darwin") == "<f2>"


class TestCrossFieldPushToTalk:
    def test_toggle_mode_ignores_modifier_only(self) -> None:
        assert _check_cross_field_push_to_talk("<ctrl>+<shift>", "toggle") == []

    def test_push_to_talk_rejects_modifier_only(self) -> None:
        errors = _check_cross_field_push_to_talk("<ctrl>+<shift>", "push_to_talk")
        assert len(errors) == 1
        assert "hotkey is invalid for push-to-talk" in errors[0]
        assert "modifier-only" in errors[0]

    def test_push_to_talk_rejects_caps_lock_on_macos(self) -> None:
        errors = _check_cross_field_push_to_talk("<caps_lock>", "push_to_talk", "darwin")
        assert len(errors) == 1
        assert "Caps Lock" in errors[0]

    def test_push_to_talk_accepts_caps_lock_on_windows(self) -> None:
        assert _check_cross_field_push_to_talk("<caps_lock>", "push_to_talk", "win32") == []

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

    def test_hotkey_change_to_caps_lock_while_push_to_talk_fails_on_macos(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(hotkey_validators, "_platform_key", lambda: "darwin")
        current = SimpleNamespace(hotkey="<f9>", recording_mode="push_to_talk")
        _validated, errors = validate_config_update({"hotkey": "<caps_lock>"}, current=current)
        assert any("Caps Lock" in error for error in errors)

    def test_switching_mode_with_caps_lock_succeeds_on_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hotkey_validators, "_platform_key", lambda: "win32")
        current = SimpleNamespace(hotkey="<caps_lock>", recording_mode="toggle")
        validated, errors = validate_config_update({"recording_mode": "push_to_talk"}, current=current)
        assert errors == []
        assert validated == {"recording_mode": "push_to_talk"}

    def test_unrelated_update_ignores_persisted_invalid_push_to_talk(self) -> None:
        current = SimpleNamespace(hotkey="<ctrl>+<shift>", recording_mode="push_to_talk")
        _validated, errors = validate_config_update({"language": "de"}, current=current)
        assert errors == []


class TestFullConfigValidation:
    def test_modifier_only_push_to_talk_is_rejected(self) -> None:
        cfg = SimpleNamespace(hotkey="<ctrl>+<shift>", recording_mode="push_to_talk")
        errors = validate_config(cfg)
        assert any("push-to-talk" in error for error in errors)

    def test_caps_lock_push_to_talk_is_rejected_on_macos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hotkey_validators, "_platform_key", lambda: "darwin")
        cfg = SimpleNamespace(hotkey="<caps_lock>", recording_mode="push_to_talk")
        errors = validate_config(cfg)
        assert any("Caps Lock" in error for error in errors)

    def test_caps_lock_push_to_talk_is_accepted_on_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(hotkey_validators, "_platform_key", lambda: "win32")
        cfg = SimpleNamespace(hotkey="<caps_lock>", recording_mode="push_to_talk")
        assert validate_config(cfg) == []

    def test_modifier_only_toggle_is_accepted(self) -> None:
        cfg = SimpleNamespace(hotkey="<ctrl>+<shift>", recording_mode="toggle")
        assert validate_config(cfg) == []
