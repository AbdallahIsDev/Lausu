"""Windows (Win32) clipboard capture and restore.

Mixin providing ``_capture_windows`` / ``_restore_windows`` to
``ClipboardSnapshot``; moved verbatim out of
``voice_typer.server.clipboard_snapshot``. Logging resolves the facade
logger at call time (``_facade.log``) because tests patch
``clipboard_snapshot.log``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.clipboard_snapshot_formats import (
    _MAX_FORMAT_BYTES,
    _MAX_TOTAL_SNAPSHOT_BYTES,
    _NON_RESTORABLE_FORMATS,
    _REGISTERED_FORMAT_MIN,
    _builtin_format_name,
)

if TYPE_CHECKING:
    from voice_typer.server.clipboard_snapshot import ClipboardSnapshot

_facade = lazy_module("voice_typer.server.clipboard_snapshot")


class WindowsClipboardMixin:
    """Win32 ``EnumClipboardFormats`` walk + ``GlobalAlloc`` restore."""

    # Host state owned by ``ClipboardSnapshot`` (the dataclass composing this
    # mixin); declared so the standalone mixin type-checks.
    items: list[Any]

    @staticmethod
    def _configure_win32_signatures(user32: Any, kernel32: Any) -> None:
        """Pin ctypes ``restype``/``argtypes`` for the Win32 calls we use.

        Without this, ctypes defaults every return value and unspecified
        argument to a 32-bit C ``int``. On 64-bit Windows, clipboard
        HANDLEs and the pointers from ``GlobalLock`` are 64-bit, so the
        default truncates them to 32 bits, a corrupted pointer that,
        when handed to ``ctypes.string_at``/``memmove``, reads or writes
        a garbage address and corrupts the heap (STATUS_HEAP_CORRUPTION,
        0xC0000374). Declaring the signatures makes ctypes marshal the
        full 64-bit values.
        """
        import ctypes
        from ctypes import c_int, c_size_t, c_uint, c_void_p, c_wchar_p

        user32.OpenClipboard.argtypes = [c_void_p]
        user32.OpenClipboard.restype = c_int
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = c_int
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = c_int
        user32.EnumClipboardFormats.argtypes = [c_uint]
        user32.EnumClipboardFormats.restype = c_uint
        user32.GetClipboardFormatNameW.argtypes = [c_uint, c_wchar_p, c_int]
        user32.GetClipboardFormatNameW.restype = c_int
        user32.GetClipboardData.argtypes = [c_uint]
        user32.GetClipboardData.restype = c_void_p
        user32.SetClipboardData.argtypes = [c_uint, c_void_p]
        user32.SetClipboardData.restype = c_void_p
        user32.RegisterClipboardFormatW.argtypes = [c_wchar_p]
        user32.RegisterClipboardFormatW.restype = c_uint

        kernel32.GlobalSize.argtypes = [c_void_p]
        kernel32.GlobalSize.restype = c_size_t
        kernel32.GlobalLock.argtypes = [c_void_p]
        kernel32.GlobalLock.restype = c_void_p
        kernel32.GlobalUnlock.argtypes = [c_void_p]
        kernel32.GlobalUnlock.restype = c_int
        kernel32.GlobalAlloc.argtypes = [c_uint, c_size_t]
        kernel32.GlobalAlloc.restype = c_void_p
        kernel32.GlobalFree.argtypes = [c_void_p]
        kernel32.GlobalFree.restype = c_void_p
        _ = ctypes  # keep the import referenced for clarity

    @classmethod
    def _capture_windows(cls) -> ClipboardSnapshot | None:
        """Capture all formats from the Windows clipboard via Win32 API.

        Walks ``EnumClipboardFormats`` and reads every available format
        as raw bytes via ``GetClipboardData`` + ``GlobalLock`` +
        ``GlobalSize``. Returns ``None`` if the clipboard cannot be
        opened (another app holds it).
        """
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        cls._configure_win32_signatures(user32, kernel32)

        # OpenClipboard(0). Pass NULL owner so we don't associate the
        if not user32.OpenClipboard(0):
            _facade.log.debug("[CLIPBOARD-SNAPSHOT] OpenClipboard failed")
            return None
        try:
            items: list[tuple[int, str, bytes]] = []
            # Running total of bytes captured across ALL formats
            total_bytes = 0
            fmt = 0
            while True:
                fmt = user32.EnumClipboardFormats(fmt)
                if fmt == 0:
                    break

                # Skip GDI-handle formats (CF_BITMAP, CF_METAFILEPICT,
                if fmt in _NON_RESTORABLE_FORMATS:
                    continue

                # Get human-readable name (for registered formats).
                name_buf = ctypes.create_unicode_buffer(256)
                name_len = user32.GetClipboardFormatNameW(fmt, name_buf, 256)
                name = name_buf.value if name_len > 0 else _builtin_format_name(fmt)

                handle = user32.GetClipboardData(fmt)
                if not handle:
                    continue

                size = kernel32.GlobalSize(handle)
                if size == 0:
                    continue

                # Bounded RAM: skip formats whose payload exceeds the cap.
                if size > _MAX_FORMAT_BYTES:
                    _facade.log.debug(
                        "[CLIPBOARD-SNAPSHOT] skipping fmt=%d name=%r: %d bytes exceeds %d-byte cap",
                        fmt,
                        name,
                        size,
                        _MAX_FORMAT_BYTES,
                    )
                    continue

                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    continue
                try:
                    data = ctypes.string_at(ptr, size)
                finally:
                    kernel32.GlobalUnlock(handle)

                items.append((fmt, name, data))

                # Track the running total of bytes captured
                total_bytes += size
                if total_bytes >= _MAX_TOTAL_SNAPSHOT_BYTES:
                    _facade.log.debug(
                        "[CLIPBOARD-SNAPSHOT] total bytes captured (%d) >= %d-byte cap, "
                        "stopping format walk after %d formats (remaining formats are best-effort)",
                        total_bytes,
                        _MAX_TOTAL_SNAPSHOT_BYTES,
                        len(items),
                    )
                    break

            if not items:
                # Empty clipboard. Return None so the caller skips restore.
                return None

            return cast("type[ClipboardSnapshot]", cls)(
                platform="windows",
                items=items,
                captured_at=time.monotonic(),
            )
        finally:
            user32.CloseClipboard()

    def _restore_windows(self) -> bool:
        """Restore all captured formats to the Windows clipboard.

                Re-registers registered formats by name (the ID may differ from
                the original because Windows assigns IDs dynamically). Skips
                GDI-handle formats (CF_BITMAP, CF_METAFILEPICT, CF_ENHMETAFILE)
                which cannot be round-tripped through GlobalAlloc.

        (session-DE, Medium, Data integrity): the pre-fix code
                called ``EmptyClipboard()`` unconditionally, then iterated
                ``self.items`` calling ``SetClipboardData`` per format. Per-item
                failures were logged at DEBUG and the item skipped; the function
                returned ``True`` unconditionally, even if EVERY
                ``SetClipboardData`` call failed (e.g. all ``GlobalAlloc``
                returned 0 due to memory pressure). After ``EmptyClipboard()``
                ran, the user's original clipboard content was gone, but the
                caller logged "Restored snapshot": false success with silent
                permanent data loss.

                Fix: track a success count during the loop. If zero items were
                successfully set, return ``False`` and log at WARNING so the
                caller logs failure instead of "Restored snapshot". The
                ``EmptyClipboard()`` call is preserved (the capture-then-swap
                pattern would be more complex and is left as a future
                improvement); the fix narrows the false-success case from
                "zero items set → True" to "zero items set → False + WARNING".
        """
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        self._configure_win32_signatures(user32, kernel32)

        # GMEM_MOVEABLE, required by SetClipboardData.
        gmem_moveable = 0x0002

        if not user32.OpenClipboard(0):
            _facade.log.debug("[CLIPBOARD-SNAPSHOT] OpenClipboard for restore failed")
            return False
        try:
            user32.EmptyClipboard()
            success_count = 0
            for fmt, name, data in self.items:
                # Skip GDI-handle formats, they cannot be restored from
                if fmt in _NON_RESTORABLE_FORMATS:
                    continue

                # Builtin formats are addressed by NUMBER. Re-registering a
                # builtin's display name ("CF_UNICODETEXT") would create a NEW
                # custom id, so the data would land under that id and the
                # builtin lookup would find nothing: the user's text would be
                # silently lost. Only genuinely registered formats (ids >=
                # 0xC000) are re-registered by name, because Windows assigns
                # their ids dynamically per session.
                target_fmt = fmt
                if fmt >= _REGISTERED_FORMAT_MIN and name:
                    registered = user32.RegisterClipboardFormatW(name)
                    if registered:
                        target_fmt = registered
                    else:
                        _facade.log.debug(
                            "[CLIPBOARD-SNAPSHOT] RegisterClipboardFormatW failed for %r, skipping",
                            name,
                        )
                        continue

                h_mem = kernel32.GlobalAlloc(gmem_moveable, len(data))
                if not h_mem:
                    continue
                ptr = kernel32.GlobalLock(h_mem)
                if not ptr:
                    kernel32.GlobalFree(h_mem)
                    continue
                try:
                    ctypes.memmove(ptr, data, len(data))
                finally:
                    kernel32.GlobalUnlock(h_mem)

                # SetClipboardData takes ownership of h_mem on success.
                if not user32.SetClipboardData(target_fmt, h_mem):
                    kernel32.GlobalFree(h_mem)
                    _facade.log.debug(
                        "[CLIPBOARD-SNAPSHOT] SetClipboardData failed for fmt=%d name=%r",
                        target_fmt,
                        name,
                    )
                    continue
                success_count += 1
            if success_count == 0:
                # zero items were successfully set. EmptyClipboard()
                _facade.log.warning(
                    "[CLIPBOARD-SNAPSHOT] _restore_windows: 0/%d formats set, "
                    "clipboard is empty after EmptyClipboard (DE-62)",
                    len(self.items),
                )
                return False
            return True
        finally:
            user32.CloseClipboard()
