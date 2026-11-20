"""Clipboard-side platform fix regressions (Win32 guards, copy/verify, paste safety)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestWin32ClipboardAbstraction:
    """PLAT-027: Win32Clipboard wraps Open/Empty/Close/SeqNum."""

    def test_get_sequence_number_returns_zero_on_non_windows(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.clipboard.is_windows", lambda: False)
        from voice_typer.server.clipboard import Win32Clipboard

        assert Win32Clipboard.get_sequence_number() == 0

    def test_context_manager_skips_on_non_windows(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.clipboard.is_windows", lambda: False)
        from voice_typer.server.clipboard import Win32Clipboard

        with pytest.raises(RuntimeError, match="only available on Windows"):
            Win32Clipboard()


class TestEmptyClipboard:
    """_win32_empty_clipboard uses Win32Clipboard abstraction."""

    def test_win32_empty_clipboard_skips_on_non_windows(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.clipboard.is_windows", lambda: False)
        from voice_typer.server.clipboard import _win32_empty_clipboard

        _win32_empty_clipboard()


class TestClipboardVerification:
    """PLAT-PASTEVR: After copy(), verify clipboard content matches."""

    def test_copy_verifies_clipboard_content(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.clipboard.is_windows", lambda: False)
        import voice_typer.server.clipboard as clip_mod
        from voice_typer.server.clipboard_snapshot import ClipboardSnapshot

        mock_pyperclip = MagicMock()
        mock_pyperclip.copy.return_value = None
        mock_pyperclip.paste.return_value = "hello world"
        clip_mod.pyperclip = mock_pyperclip

        sentinel = ClipboardSnapshot(platform="linux-x11", items=[], captured_at=0.0)

        with (
            patch("voice_typer.server.clipboard._ensure_pynput_imported"),
            patch("voice_typer.server.clipboard._Controller") as mock_ctrl,
            patch.object(ClipboardSnapshot, "capture", return_value=sentinel),
        ):
            mock_instance = MagicMock()
            mock_ctrl.return_value = mock_instance
            from voice_typer.server.clipboard import ClipboardManager

            cm = ClipboardManager(paste_enabled=False)
            result = cm.copy("hello world")
        assert result is sentinel
        mock_pyperclip.copy.assert_called()

    def test_copy_retries_on_verification_mismatch(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.clipboard.is_windows", lambda: False)
        import voice_typer.server.clipboard as clip_mod
        from voice_typer.server.clipboard_snapshot import ClipboardSnapshot

        mock_pyperclip = MagicMock()
        mock_pyperclip.copy.return_value = None
        mock_pyperclip.paste.side_effect = ["wrong_value", "hello world"]
        clip_mod.pyperclip = mock_pyperclip

        sentinel = ClipboardSnapshot(platform="linux-x11", items=[], captured_at=0.0)

        with (
            patch("voice_typer.server.clipboard._ensure_pynput_imported"),
            patch("voice_typer.server.clipboard._Controller") as mock_ctrl,
            patch.object(ClipboardSnapshot, "capture", return_value=sentinel),
        ):
            mock_instance = MagicMock()
            mock_ctrl.return_value = mock_instance
            from voice_typer.server.clipboard import ClipboardManager

            cm = ClipboardManager(paste_enabled=False)
            result = cm.copy("hello world")
        assert result is sentinel
        assert mock_pyperclip.copy.call_count >= 2, (
            f"Expected copy() to be called at least 2 times (initial + retry), but got {mock_pyperclip.copy.call_count}"
        )
        for call in mock_pyperclip.copy.call_args_list:
            assert call[0][0] == "hello world"


class TestSafeKeyRelease:
    """PLAT-STUCK: _safe_key_press releases modifier even on error."""

    def test_safe_key_press_releases_modifier_on_error(self):
        with (
            patch("voice_typer.server.clipboard._ensure_pynput_imported"),
            patch("voice_typer.server.clipboard._Controller") as mock_ctrl,
        ):
            mock_instance = MagicMock()
            mock_ctrl.return_value = mock_instance
            from voice_typer.server.clipboard import ClipboardManager

            cm = ClipboardManager(paste_enabled=True)
            cm._keyboard = mock_instance

        mock_instance.press.side_effect = [None, Exception("test error")]
        with pytest.raises(Exception, match="test error"):
            cm._safe_key_press(MagicMock(), "v")
        mock_instance.release.assert_called()


class TestClipboardSaveRestore:
    """PLAT-SECURE: Before copy, save existing clipboard; after clear, restore."""

    def test_copy_saves_existing_clipboard(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.clipboard.is_windows", lambda: False)
        import voice_typer.server.clipboard as clip_mod
        from voice_typer.server.clipboard_snapshot import ClipboardSnapshot

        mock_pyperclip = MagicMock()
        mock_pyperclip.copy.return_value = None
        mock_pyperclip.paste.return_value = "new text"
        clip_mod.pyperclip = mock_pyperclip

        sentinel_snapshot = ClipboardSnapshot(
            platform="linux-x11",
            items=[("text/plain", b"previous content")],
            captured_at=0.0,
        )

        with (
            patch("voice_typer.server.clipboard._ensure_pynput_imported"),
            patch("voice_typer.server.clipboard._Controller") as mock_ctrl,
            patch.object(ClipboardSnapshot, "capture", return_value=sentinel_snapshot) as mock_capture,
        ):
            mock_instance = MagicMock()
            mock_ctrl.return_value = mock_instance
            from voice_typer.server.clipboard import ClipboardManager

            cm = ClipboardManager(paste_enabled=False)
            result = cm.copy("new text")
        assert result is sentinel_snapshot
        mock_capture.assert_called_once()


class TestElevatedTarget:
    """PLAT-013: _is_elevated_target checks if foreground is elevated."""

    def test_returns_false_on_non_windows(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.clipboard.is_windows", lambda: False)
        from voice_typer.server.clipboard import _is_elevated_target

        assert _is_elevated_target() is False


class TestPasswordField:
    """PLAT-014: _is_password_field checks UIA IsPasswordPropertyId."""

    def test_returns_false_on_non_windows(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.clipboard.is_windows", lambda: False)
        from voice_typer.server.clipboard import _is_password_field

        assert _is_password_field() is False


class TestContentEditableComment:
    """PLAT-CONTENT: Module has documentation about contentEditable limitation."""

    def test_clipboard_module_documents_content_editable(self):
        import inspect

        import voice_typer.server.clipboard as clip_mod

        source = inspect.getsource(clip_mod)
        assert "PLAT-CONTENT" in source
        assert "contentEditable" in source


class TestClipboardSequenceNumber:
    """PLAT-CLIPRACE: Win32Clipboard.get_sequence_number() exists."""

    def test_get_sequence_number_static_method(self):
        from voice_typer.server.clipboard import Win32Clipboard

        assert hasattr(Win32Clipboard, "get_sequence_number")

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Non-Windows path: Win32Clipboard.get_sequence_number is a no-op returning 0 on POSIX",
    )
    def test_get_sequence_number_returns_zero_on_non_windows(self):
        from voice_typer.server.clipboard import Win32Clipboard

        assert Win32Clipboard.get_sequence_number() == 0


class TestPynputFallbackDocumentation:
    """PLAT-001: Clipboard module documents pynput/UIPI limitation."""

    def test_clipboard_module_documents_uipi_limitation(self):
        import inspect

        import voice_typer.server.clipboard as clip_mod

        source = inspect.getsource(clip_mod)
        assert "pynput" in source
        assert "UIPI" in source
