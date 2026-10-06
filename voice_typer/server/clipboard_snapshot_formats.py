"""Shared clipboard format tables and capture limits.

Standard Windows clipboard format ids, the builtin id→name map, the
GDI-handle formats that cannot be round-tripped, and the per-format /
total capture caps. Moved verbatim out of
``voice_typer.server.clipboard_snapshot`` (which re-exports every name).
"""

from __future__ import annotations

# https://learn.microsoft.com/en-us/windows/win32/dataxchg/standard-clipboard-formats
_CF_TEXT = 1
_CF_BITMAP = 2
_CF_METAFILEPICT = 3
_CF_SYLK = 4
_CF_DIF = 5
_CF_TIFF = 6
_CF_OEMTEXT = 7
_CF_DIB = 8
_CF_PALETTE = 9
_CF_PENDATA = 10
_CF_RIFF = 11
_CF_WAVE = 12
_CF_UNICODETEXT = 13
_CF_ENHMETAFILE = 14
_CF_HDROP = 15
_CF_LOCALE = 16
_CF_DIBV5 = 17

# Builtin format ID → human-readable name. Used when GetClipboardFormatNameW
_BUILTIN_FORMAT_NAMES: dict[int, str] = {
    _CF_TEXT: "CF_TEXT",
    _CF_BITMAP: "CF_BITMAP",
    _CF_METAFILEPICT: "CF_METAFILEPICT",
    _CF_SYLK: "CF_SYLK",
    _CF_DIF: "CF_DIF",
    _CF_TIFF: "CF_TIFF",
    _CF_OEMTEXT: "CF_OEMTEXT",
    _CF_DIB: "CF_DIB",
    _CF_PALETTE: "CF_PALETTE",
    _CF_PENDATA: "CF_PENDATA",
    _CF_RIFF: "CF_RIFF",
    _CF_WAVE: "CF_WAVE",
    _CF_UNICODETEXT: "CF_UNICODETEXT",
    _CF_ENHMETAFILE: "CF_ENHMETAFILE",
    _CF_HDROP: "CF_HDROP",
    _CF_LOCALE: "CF_LOCALE",
    _CF_DIBV5: "CF_DIBV5",
}

# Formats that cannot be round-tripped through GlobalAlloc + memmove because
_NON_RESTORABLE_FORMATS: frozenset[int] = frozenset(
    {
        _CF_BITMAP,
        _CF_METAFILEPICT,
        _CF_ENHMETAFILE,
    }
)

# Clipboard format ids below this value are Win32 PREDEFINED (builtin)
# formats: CF_TEXT=1 .. CF_DIBV5=17 plus the reserved 0x0080-0x00FF range.
# RegisterClipboardFormat returns ids AT OR ABOVE it for custom formats.
_REGISTERED_FORMAT_MIN = 0xC000

# Maximum bytes captured for a single clipboard format. Formats larger
_MAX_FORMAT_BYTES = 16 * 1024 * 1024

# Running-total cap on the bytes captured across ALL formats in
_MAX_TOTAL_SNAPSHOT_BYTES = 64 * 1024 * 1024


def _builtin_format_name(fmt: int) -> str:
    """Return the standard name for a builtin clipboard format, or ''."""
    return _BUILTIN_FORMAT_NAMES.get(fmt, "")
