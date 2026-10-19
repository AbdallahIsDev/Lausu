"""Clipboard text fingerprint: the ownership check behind paste and restore.

A dictation owns the clipboard only while the clipboard holds its exact
text; the same comparison gates the keystroke dispatch and the
conditional restore of the user's saved clipboard.
"""

from __future__ import annotations

import hashlib

from voice_typer.server import clipboard as _cb


def text_fingerprint(text: str) -> tuple[int, str]:
    """Fingerprint ``text`` the way the OS stores it (UTF-8 bytes)."""
    data = text.encode("utf-8", "surrogatepass")
    return (len(data), hashlib.sha256(data).hexdigest())


def clipboard_holds(fingerprint: tuple[int, str] | None) -> bool | None:
    """Compare the live clipboard with ``fingerprint``.

    ``True`` = holds exactly that text, ``False`` = holds something else,
    ``None`` = the clipboard cannot be read here. Callers pick their safe
    side: dispatch treats ``None`` as unknown and proceeds (pre-check
    behavior), restore requires ``True``.
    """
    if fingerprint is None:
        return None
    try:
        current = _cb._paste_from_clipboard()
    except Exception:
        _cb.log.debug("[CLIPBOARD] fingerprint read failed", exc_info=True)
        return None
    if not isinstance(current, str):
        return None
    return text_fingerprint(current) == fingerprint
