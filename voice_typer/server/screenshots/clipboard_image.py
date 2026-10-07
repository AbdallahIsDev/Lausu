"""Hybrid Win32 clipboard writer: text + image + file list in one open."""

from __future__ import annotations

import contextlib
import logging
import struct
from pathlib import Path

log = logging.getLogger(__name__)

CF_UNICODETEXT = 13
CF_DIB = 8
CF_HDROP = 15
_GMEM_MOVEABLE = 0x0002


def is_supported() -> bool:
    from voice_typer.server.platform_utils import is_windows

    return is_windows()


def _png_to_dib_bytes(png_path: Path) -> bytes:
    # Pillow import stays lazy so non-Windows cold import never loads it.
    import io

    from PIL import Image

    with Image.open(png_path) as img:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="BMP")
        return buf.getvalue()[14:]


def _set_global_bytes(user32, kernel32, fmt: int, payload: bytes) -> bool:
    import ctypes

    handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(payload) + 1)
    if not handle:
        return False
    locked = kernel32.GlobalLock(handle)
    if not locked:
        kernel32.GlobalFree(handle)
        return False
    try:
        ctypes.memmove(locked, payload, len(payload))
    finally:
        kernel32.GlobalUnlock(handle)
    # OS takes ownership on success; only free when the call fails.
    if not user32.SetClipboardData(fmt, handle):
        kernel32.GlobalFree(handle)
        return False
    return True


def place_text_image_files(text: str, png_path: str | Path) -> bool:
    if not is_supported():
        return False
    import ctypes

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
    except (AttributeError, OSError):
        return False
    opened = False
    try:
        try:
            opened = bool(user32.OpenClipboard(0))
        except (OSError, AttributeError):
            opened = False
        if not opened:
            return False
        user32.EmptyClipboard()
        text_ok = _set_global_bytes(user32, kernel32, CF_UNICODETEXT, text.encode("utf-16-le") + b"\x00\x00")
        try:
            dib = _png_to_dib_bytes(Path(png_path))
            _set_global_bytes(user32, kernel32, CF_DIB, dib)
        except (OSError, ValueError):
            log.debug("[CLIPBOARD] screenshot DIB skipped", exc_info=True)
        try:
            files_blob = struct.pack("<IiiII", 20, 0, 0, 0, 1)
            files_blob += str(png_path).encode("utf-16-le") + b"\x00\x00\x00\x00"
            _set_global_bytes(user32, kernel32, CF_HDROP, files_blob)
        except (OSError, ValueError):
            log.debug("[CLIPBOARD] screenshot HDROP skipped", exc_info=True)
        return text_ok
    finally:
        if opened:
            with contextlib.suppress(OSError, AttributeError):
                user32.CloseClipboard()
