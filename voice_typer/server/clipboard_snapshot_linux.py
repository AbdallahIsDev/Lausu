"""Linux (X11 ``xclip`` / Wayland ``wl-paste``) clipboard capture and restore.

Mixin providing the four Linux clipboard methods to
``ClipboardSnapshot``; moved verbatim out of
``voice_typer.server.clipboard_snapshot``. Text-only by design
(ADR-0010 §4.5/§4.6): both tools hold one target per selection. Logging
resolves the facade logger at call time (``_facade.log``) because tests
patch ``clipboard_snapshot.log``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

from voice_typer.server._lazy_import import lazy_module

if TYPE_CHECKING:
    from voice_typer.server.clipboard_snapshot import ClipboardSnapshot

_facade = lazy_module("voice_typer.server.clipboard_snapshot")


class LinuxClipboardMixin:
    """X11 / Wayland text-target clipboard capture and restore."""

    # Host state owned by ``ClipboardSnapshot`` (the dataclass composing this
    # mixin); declared so the standalone mixin type-checks.
    items: list[Any]

    @classmethod
    def _capture_x11(cls) -> ClipboardSnapshot | None:
        """Capture text targets from the X11 clipboard via xclip.

        Documented limitation (ADR-0010 §4.5, §11.1): xclip can only
        hold one target per clipboard selection. A full multi-format X11
        implementation requires Gtk.Clipboard via PyGObject, which is
        not a dependency of this project. Images and file lists are not
        preserved.
        """
        import subprocess

        text_targets = [
            "text/plain;charset=utf-8",
            "UTF8_STRING",
            "text/plain",
            "STRING",
        ]

        items: list[tuple[str, bytes]] = []
        for target in text_targets:
            try:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", target, "-o"],
                    capture_output=True,
                    timeout=2.0,
                )
                if result.returncode == 0 and result.stdout:
                    items.append((target, result.stdout))
                    break  # first available text target is sufficient
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        if not items:
            return None

        return cast("type[ClipboardSnapshot]", cls)(
            platform="linux-x11",
            items=items,
            captured_at=time.monotonic(),
        )

    def _restore_x11(self) -> bool:
        """Restore text content to the X11 clipboard via xclip.

        (session-DE, Medium, Data integrity): the pre-fix code
                called ``subprocess.run(...)`` without ``check=True``, so a
                non-zero ``xclip`` exit (no ``DISPLAY``, X11 connection
                refused, compositor error) did NOT raise, the function
                returned ``True`` unconditionally and the caller logged
                "Restored snapshot" while the user's clipboard still contained
                the dictated text. Silent data loss with false-success signal.
                Now we pass ``check=True`` so non-zero exits raise
                ``CalledProcessError``, catch it alongside
                ``TimeoutExpired``/``FileNotFoundError``, and return ``False``
                on failure with a WARNING log.
        """
        import subprocess

        if not self.items:
            return True  # nothing to restore

        target, data = self.items[0]
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", target, "-i"],
                input=data,
                timeout=2.0,
                check=True,
            )
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            _facade.log.debug("[CLIPBOARD-SNAPSHOT] xclip restore failed (timeout or missing)")
            return False
        except subprocess.CalledProcessError as exc:
            _facade.log.warning(
                "[CLIPBOARD-SNAPSHOT] xclip restore failed (exit %d), "
                "clipboard may still contain dictated text (DE-61)",
                exc.returncode,
            )
            return False

    @classmethod
    def _capture_wayland(cls) -> ClipboardSnapshot | None:
        """Capture text targets from the Wayland clipboard via wl-paste.

        Documented limitation (ADR-0010 §4.6, §11.2): wl-copy can only
        serve one stdin stream for all --type flags. A full multi-format
        Wayland implementation requires a custom wl_data_source client,
        which is out of scope.
        """
        import subprocess

        text_targets = [
            "text/plain;charset=utf-8",
            "text/plain",
            "UTF8_STRING",
        ]

        items: list[tuple[str, bytes]] = []
        for target in text_targets:
            try:
                result = subprocess.run(
                    ["wl-paste", "--type", target],
                    capture_output=True,
                    timeout=2.0,
                )
                if result.returncode == 0 and result.stdout:
                    items.append((target, result.stdout))
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue

        if not items:
            return None

        return cast("type[ClipboardSnapshot]", cls)(
            platform="linux-wayland",
            items=items,
            captured_at=time.monotonic(),
        )

    def _restore_wayland(self) -> bool:
        """Restore text content to the Wayland clipboard via wl-copy.

        (session-DE, Medium, Data integrity): the pre-fix code
                called ``subprocess.run(...)`` without ``check=True``, so a
                non-zero ``wl-copy`` exit (compositor error, no Wayland
                display) did NOT raise, the function returned ``True``
                unconditionally and the caller logged "Restored snapshot"
                while the user's clipboard still contained the dictated text.
                Silent data loss with false-success signal. Now we pass
                ``check=True`` so non-zero exits raise ``CalledProcessError``,
                catch it alongside ``TimeoutExpired``/``FileNotFoundError``,
                and return ``False`` on failure with a WARNING log.
        """
        import subprocess

        if not self.items:
            return True

        target, data = self.items[0]
        try:
            subprocess.run(
                ["wl-copy", "--type", target],
                input=data,
                timeout=2.0,
                check=True,
            )
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            _facade.log.debug("[CLIPBOARD-SNAPSHOT] wl-copy restore failed (timeout or missing)")
            return False
        except subprocess.CalledProcessError as exc:
            _facade.log.warning(
                "[CLIPBOARD-SNAPSHOT] wl-copy restore failed (exit %d), "
                "clipboard may still contain dictated text (DE-61)",
                exc.returncode,
            )
            return False
