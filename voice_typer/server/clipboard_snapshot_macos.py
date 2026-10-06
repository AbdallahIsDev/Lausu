"""macOS (NSPasteboard) clipboard capture and restore.

Mixin providing ``_capture_macos`` / ``_restore_macos`` to
``ClipboardSnapshot``; moved verbatim out of
``voice_typer.server.clipboard_snapshot``. Logging resolves the facade
logger at call time (``_facade.log``) because tests patch
``clipboard_snapshot.log``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.clipboard_snapshot_formats import _MAX_FORMAT_BYTES

if TYPE_CHECKING:
    from voice_typer.server.clipboard_snapshot import ClipboardSnapshot

_facade = lazy_module("voice_typer.server.clipboard_snapshot")


class MacosClipboardMixin:
    """NSPasteboard capture/restore (multi-item pasteboards preserved)."""

    # Host state owned by ``ClipboardSnapshot`` (the dataclass composing this
    # mixin); declared so the standalone mixin type-checks.
    items: list[Any]

    @classmethod
    def _capture_macos(cls) -> ClipboardSnapshot | None:
        """Capture all formats from the macOS pasteboard via NSPasteboard.

        Records the pasteboard item index so multi-item pasteboards
        (e.g. multiple files copied from Finder) can be restored as
        separate NSPasteboardItem objects.
        """
        try:
            import AppKit  # type: ignore[import-not-found]
        except ImportError:
            _facade.log.debug("[CLIPBOARD-SNAPSHOT] AppKit unavailable")
            return None

        pb = AppKit.NSPasteboard.generalPasteboard()
        items: list[tuple[int, str, bytes]] = []

        for idx, item in enumerate(pb.pasteboardItems()):
            for type_name in item.types():
                nsdata = item.dataForType_(type_name)
                if nsdata is None:
                    continue
                length = nsdata.length()
                # Bounded RAM (mirrors the Windows path): skip formats
                if length > _MAX_FORMAT_BYTES:
                    _facade.log.debug(
                        "[CLIPBOARD-SNAPSHOT] skipping type=%r idx=%d: %d bytes exceeds %d-byte cap",
                        type_name,
                        idx,
                        length,
                        _MAX_FORMAT_BYTES,
                    )
                    continue
                # NSData.bytes() returns a pointer; .as_buffer(n) gives
                data = b"" if length == 0 else bytes(nsdata.bytes().as_buffer(length))
                items.append((idx, str(type_name), data))

        if not items:
            return None

        return cast("type[ClipboardSnapshot]", cls)(
            platform="macos",
            items=items,
            captured_at=time.monotonic(),
        )

    def _restore_macos(self) -> bool:
        """Restore all captured formats to the macOS pasteboard.

        Groups items by their original pasteboard item index and writes
        one NSPasteboardItem per original index, preserving multi-item
        pasteboards.

        (Data integrity): the pre-fix code called
                ``item.setData_forType_`` and ``pb.writeObjects_`` without
                inspecting their return values, a per-item failure (e.g.
                an unsupported type-name, a payload that violates the
                type's contract) or a ``writeObjects_`` rejection (which
                returns NO if NO items were accepted) was silently
                swallowed, the function returned ``True`` unconditionally,
                and the caller logged "Restored snapshot" while the
                clipboard was left empty (``clearContents`` having already
                wiped it). Mirror of the Windows ``_restore_windows``
                pattern: track ``success_count`` (increment only when
                ``setData_forType_`` returns True), inspect
                ``writeObjects_``'s BOOL return, and return ``False`` with
                a WARNING log if zero items were set OR ``writeObjects_``
                returned False.
        """
        try:
            import AppKit  # type: ignore[import-not-found]
            import Foundation  # type: ignore[import-not-found]
        except ImportError:
            _facade.log.debug("[CLIPBOARD-SNAPSHOT] AppKit/Foundation unavailable for restore")
            return False

        pb = AppKit.NSPasteboard.generalPasteboard()
        pb.clearContents()

        # Group items by pasteboard item index so multi-item pasteboards
        from collections import defaultdict

        grouped: dict[int, list[tuple[str, bytes]]] = defaultdict(list)
        for idx, type_name, data in self.items:
            grouped[idx].append((type_name, data))

        success_count = 0
        ns_items = []
        for idx in sorted(grouped.keys()):
            item = AppKit.NSPasteboardItem.alloc().init()
            for type_name, data in grouped[idx]:
                nsdata = Foundation.NSData.dataWithBytes_length_(data, len(data)) if data else Foundation.NSData.data()
                if item.setData_forType_(nsdata, type_name):
                    success_count += 1
                else:
                    _facade.log.debug(
                        "[CLIPBOARD-SNAPSHOT] setData_forType_ failed for idx=%d type=%r",
                        idx,
                        type_name,
                    )
            ns_items.append(item)

        # ``writeObjects_`` returns YES only if at least one NSPasteboardItem
        write_ok = bool(pb.writeObjects_(ns_items)) if ns_items else True

        if success_count == 0 or not write_ok:
            _facade.log.warning(
                "[CLIPBOARD-SNAPSHOT] _restore_macos: %d/%d items set, "
                "writeObjects_=%s, clipboard may be empty after clearContents",
                success_count,
                len(self.items),
                write_ok,
            )
            return False
        return True
