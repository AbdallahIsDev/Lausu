"""Hybrid clipboard tests (mocked Win32, no real clipboard)."""

import ctypes
from pathlib import Path
from unittest.mock import MagicMock

from voice_typer.server.screenshots import clipboard_image


def test_noop_off_windows(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(clipboard_image, "is_supported", lambda: False)
    assert clipboard_image.place_text_image_files("hi", tmp_path / "x.png") is False


def test_places_all_three_formats(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(clipboard_image, "is_supported", lambda: True)
    monkeypatch.setattr(clipboard_image, "_png_to_dib_bytes", lambda p: b"DIBBYTES")
    user32 = MagicMock()
    user32.OpenClipboard.return_value = 1
    user32.SetClipboardData.return_value = 1
    kernel32 = MagicMock()
    kernel32.GlobalAlloc.return_value = 0x1000
    kernel32.GlobalLock.return_value = 0x2000
    fake_windll = MagicMock()
    fake_windll.user32 = user32
    fake_windll.kernel32 = kernel32
    monkeypatch.setattr(ctypes, "windll", fake_windll, raising=False)
    monkeypatch.setattr("ctypes.memmove", lambda dst, src, n: None)
    png = tmp_path / "shot-1.png"
    png.write_bytes(b"fake")
    assert clipboard_image.place_text_image_files("text " + str(png), png) is True
    formats = [c.args[0] for c in user32.SetClipboardData.call_args_list]
    assert clipboard_image.CF_UNICODETEXT in formats
    assert clipboard_image.CF_DIB in formats
    assert clipboard_image.CF_HDROP in formats
