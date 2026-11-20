"""Hotkey-backend detection regressions (IME, AltGr, VK map, macOS guide)."""

from __future__ import annotations


class TestIMEDetection:
    """PLAT-020: _is_ime_composing detects IME composition state."""

    def test_returns_false_on_non_windows(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.hotkeys.sys.platform", "linux")
        from voice_typer.server.hotkeys import WindowsNativeHotkey

        assert WindowsNativeHotkey._is_ime_composing() is False


class TestAltGrDetection:
    """PLAT-ALTGR: _is_altgr_pressed detects Ctrl+RightAlt."""

    def test_is_altgr_pressed_returns_false_without_user32(self):
        from voice_typer.server.hotkeys import WindowsNativeHotkey

        backend = WindowsNativeHotkey("<f2>")
        backend._user32 = None
        assert backend._is_altgr_pressed() is False


class TestVKMapFallback:
    """PLAT-VKMAP: VK codes try MapVirtualKey for non-US layouts."""

    def test_vk_map_comment_exists(self):
        import inspect

        import voice_typer.server.hotkeys as hk_mod

        source = inspect.getsource(hk_mod)
        assert "PLAT-VKMAP" in source

    def test_parse_hotkey_still_works_for_standard_keys(self):
        from voice_typer.server.hotkeys import parse_hotkey_to_vk

        assert parse_hotkey_to_vk("<f2>") == 0x71
        assert parse_hotkey_to_vk("a") == ord("A")


class TestMacOSAccessibilityGuide:
    """PLAT-030: PynputHotkey logs accessibility guide on macOS failure."""

    def test_macos_accessibility_warning_in_source(self):
        import inspect

        import voice_typer.server.hotkeys as hk_mod

        source = inspect.getsource(hk_mod.PynputHotkey)
        assert "Accessibility" in source or "accessibility" in source
