"""Paste-instant race pins: a copy the user makes in the millisecond gap
inside our own paste flow must survive untouched.

Two gaps exist by construction: between our ``copy()`` and the dispatch
keystroke (gate 2 plus the SendInput fallback's own re-check) and between
the keystroke and the delayed snapshot restore (gate 3 / atexit gate).
The re-paste path reuses the same dispatch gate. Every test redirects
clipboard I/O to an in-memory string; the real clipboard is never read
or written.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from voice_typer.server import clipboard as clip_mod
from voice_typer.server.app_undo import UndoRepasteController
from voice_typer.server.branding import APP_NAME
from voice_typer.server.clipboard import ClipboardManager
from voice_typer.server.clipboard.fingerprint import text_fingerprint
from voice_typer.server.clipboard_snapshot import ClipboardSnapshot

from tests.fixtures.clipboard_helpers import make_clipboard_manager, make_clipboard_snapshot

THE_DICTATION = "our dictation text"
USER_NEW = "the user's newer copy"
USER_CLIPBOARD = "the user's own copied text"


class _FakeClipboard:
    """In-memory clipboard: no test ever touches the real one."""

    def __init__(self, text: str = USER_CLIPBOARD) -> None:
        self.text = text
        self.copies: list[str] = []

    def copy(self, text: str) -> None:
        self.copies.append(text)
        self.text = text

    def read(self) -> str:
        return self.text


class _UserCopiesAfterFirstRead(_FakeClipboard):
    """The user's copy lands between our copy-verify read and gate 2."""

    def __init__(self, our_text: str) -> None:
        super().__init__(our_text)
        self._reads = 0

    def read(self) -> str:
        self._reads += 1
        if self._reads >= 2:
            self.text = USER_NEW
        return self.text


@pytest.fixture(autouse=True)
def _isolate_clipboard(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":99")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with clip_mod._pending_restores_lock:
        clip_mod._pending_restores.clear()
    yield
    with clip_mod._pending_restores_lock:
        clip_mod._pending_restores.clear()


@contextlib.contextmanager
def _install_fake_clipboard(fake: _FakeClipboard):
    with (
        patch.object(clip_mod, "_copy_to_clipboard", side_effect=fake.copy),
        patch.object(clip_mod, "_paste_from_clipboard", side_effect=fake.read),
        patch.object(clip_mod, "_win32_empty_clipboard"),
        patch.object(clip_mod, "_win32_exclude_clipboard_from_monitoring"),
        patch.object(ClipboardSnapshot, "capture", return_value=None),
        patch.object(ClipboardManager, "_get_clipboard_sequence_number", return_value=0),
    ):
        yield fake


@pytest.fixture
def fake_clipboard():
    with _install_fake_clipboard(_FakeClipboard()) as fake:
        yield fake


@contextlib.contextmanager
def _armed_paste_path(keystrokes: list, *, windows: bool = False, macos: bool = False):
    """Arm every platform probe so a dispatch would reach its keystroke.

    If a gate blocks dispatch, nothing here fires; if a gate regresses,
    the keystroke recorder and the SendInput spies catch the leak.
    """
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(clip_mod, "is_windows", lambda: windows))
        stack.enter_context(patch.object(clip_mod, "is_macos", lambda: macos))
        stack.enter_context(patch.object(clip_mod, "is_linux", lambda: not windows and not macos))
        stack.enter_context(patch.object(clip_mod, "_is_wayland_paste_session", lambda: False))
        stack.enter_context(patch.object(clip_mod, "_have_wtype", lambda: False))
        stack.enter_context(patch.object(clip_mod, "_Controller", MagicMock()))
        stack.enter_context(patch.object(clip_mod, "_Key", MagicMock()))
        stack.enter_context(patch.object(ClipboardManager, "_is_safe_paste_target", MagicMock(return_value=True)))
        stack.enter_context(patch.object(ClipboardManager, "_check_ime_composition", MagicMock(return_value=True)))
        stack.enter_context(patch.object(ClipboardManager, "_compute_paste_delay", MagicMock(return_value=0.0)))
        stack.enter_context(
            patch.object(ClipboardManager, "_check_text_field_focus", MagicMock(return_value=(True, None)))
        )
        stack.enter_context(patch.object(ClipboardManager, "_capture_target_handle", MagicMock(return_value=(0, None))))
        stack.enter_context(patch.object(ClipboardManager, "_recheck_toctou", MagicMock(return_value=True)))
        stack.enter_context(patch.object(ClipboardManager, "_recheck_macos_toctou", MagicMock(return_value=True)))
        stack.enter_context(patch.object(ClipboardManager, "_detect_focused_process", MagicMock(return_value=None)))
        stack.enter_context(patch.object(ClipboardManager, "_release_stuck_modifiers", MagicMock()))
        stack.enter_context(
            patch.object(
                ClipboardManager,
                "_safe_key_press",
                lambda self, modifier, char: keystrokes.append((modifier, char)),
            )
        )
        yield


class TestCopyInGapAbortsDispatch:
    """The user copies between our copy() and paste(): nothing dispatches."""

    @staticmethod
    def _copy_then_user_copies(fake: _FakeClipboard) -> ClipboardManager:
        manager = make_clipboard_manager()
        manager.copy(THE_DICTATION)
        fake.text = USER_NEW  # the user's copy lands during the gap
        return manager

    @staticmethod
    def _assert_nothing_dispatched(fake: _FakeClipboard, keystrokes: list, pasted: bool) -> None:
        assert pasted is False
        assert keystrokes == []
        assert fake.text == USER_NEW
        assert fake.copies == [THE_DICTATION]
        assert clip_mod._pending_restores == []

    def test_windows_non_terminal_never_sends_ctrl_v(self, fake_clipboard):
        keystrokes: list = []
        sendinput = MagicMock(return_value=True)
        with (
            _armed_paste_path(keystrokes, windows=True),
            patch.object(clip_mod, "_send_ctrl_v_win32", sendinput),
        ):
            manager = self._copy_then_user_copies(fake_clipboard)
            pasted = manager.paste(
                snapshot=None,
                pasted_text=THE_DICTATION,
                expected_fingerprint=text_fingerprint(THE_DICTATION),
            )
        sendinput.assert_not_called()
        self._assert_nothing_dispatched(fake_clipboard, keystrokes, pasted)

    def test_windows_terminal_sendinput_never_fires(self, fake_clipboard):
        keystrokes: list = []
        shift_insert = MagicMock(return_value=True)
        with (
            _armed_paste_path(keystrokes, windows=True),
            patch.object(ClipboardManager, "_is_terminal_process", MagicMock(return_value=True)),
            patch.object(clip_mod, "_send_shift_insert_win32", shift_insert),
        ):
            manager = self._copy_then_user_copies(fake_clipboard)
            manager._keyboard = None  # pynput unavailable: SendInput branch
            pasted = manager.paste(
                snapshot=None,
                pasted_text=THE_DICTATION,
                expected_fingerprint=text_fingerprint(THE_DICTATION),
            )
        shift_insert.assert_not_called()
        self._assert_nothing_dispatched(fake_clipboard, keystrokes, pasted)

    def test_windows_terminal_pynput_never_types(self, fake_clipboard):
        keystrokes: list = []
        shift_insert = MagicMock(return_value=True)
        with (
            _armed_paste_path(keystrokes, windows=True),
            patch.object(ClipboardManager, "_is_terminal_process", MagicMock(return_value=True)),
            patch.object(clip_mod, "_send_shift_insert_win32", shift_insert),
        ):
            manager = self._copy_then_user_copies(fake_clipboard)
            pasted = manager.paste(
                snapshot=None,
                pasted_text=THE_DICTATION,
                expected_fingerprint=text_fingerprint(THE_DICTATION),
            )
        shift_insert.assert_not_called()
        self._assert_nothing_dispatched(fake_clipboard, keystrokes, pasted)

    def test_macos_never_types(self, fake_clipboard):
        keystrokes: list = []
        with _armed_paste_path(keystrokes, macos=True):
            manager = self._copy_then_user_copies(fake_clipboard)
            pasted = manager.paste(
                snapshot=None,
                pasted_text=THE_DICTATION,
                expected_fingerprint=text_fingerprint(THE_DICTATION),
            )
        self._assert_nothing_dispatched(fake_clipboard, keystrokes, pasted)

    def test_linux_never_types(self, fake_clipboard):
        keystrokes: list = []
        with _armed_paste_path(keystrokes):
            manager = self._copy_then_user_copies(fake_clipboard)
            pasted = manager.paste(
                snapshot=None,
                pasted_text=THE_DICTATION,
                expected_fingerprint=text_fingerprint(THE_DICTATION),
            )
        self._assert_nothing_dispatched(fake_clipboard, keystrokes, pasted)


class TestFallbackKeystrokeRechecks:
    """The SendInput fallback re-checks the clipboard at the keystroke moment."""

    def test_fallback_recheck_blocks_after_a_late_copy(self, fake_clipboard):
        keystrokes: list = []
        fallback_invoked: list = []

        def _sendinput(*, fallback, probe):
            probe.append(0)  # none of the SendInput events were delivered
            fake_clipboard.text = USER_NEW  # the user copies mid-dispatch
            fallback_invoked.append(True)
            fallback()
            return False

        with (
            _armed_paste_path(keystrokes, windows=True),
            patch.object(clip_mod, "_send_ctrl_v_win32", _sendinput),
        ):
            manager = make_clipboard_manager()
            manager.copy(THE_DICTATION)
            pasted = manager.paste(
                snapshot=None,
                pasted_text=THE_DICTATION,
                expected_fingerprint=text_fingerprint(THE_DICTATION),
            )

        assert fallback_invoked == [True], "the fallback must have run its own re-check"
        assert pasted is False
        assert keystrokes == []
        assert fake_clipboard.text == USER_NEW

    def test_fallback_dispatches_while_the_clipboard_is_ours(self, fake_clipboard):
        keystrokes: list = []

        def _sendinput(*, fallback, probe):
            probe.append(0)
            fallback()
            return False

        with (
            _armed_paste_path(keystrokes, windows=True),
            patch.object(clip_mod, "_send_ctrl_v_win32", _sendinput),
        ):
            key = clip_mod._Key
            manager = make_clipboard_manager()
            manager.copy(THE_DICTATION)
            pasted = manager.paste(
                snapshot=None,
                pasted_text=THE_DICTATION,
                expected_fingerprint=text_fingerprint(THE_DICTATION),
            )

        # Delivery stays unconfirmed (the stub reported 0 events), but the
        # fallback keystroke itself must have gone out.
        assert pasted is False
        assert keystrokes == [(key.ctrl, "v")]


def _make_repaste_app(manager: ClipboardManager, latest_text: str) -> SimpleNamespace:
    app = SimpleNamespace(
        history_db=MagicMock(),
        clipboard=manager,
        tray=MagicMock(),
        _last_transcription=None,
    )
    app.history_db.get_latest_text.return_value = latest_text
    return app


class TestRepasteGap:
    """Re-paste shares the dispatch gate; the same gap is covered there."""

    def test_user_copy_between_copy_and_paste_blocks_repaste(self):
        manager = make_clipboard_manager()
        fake = _UserCopiesAfterFirstRead(THE_DICTATION)
        app = _make_repaste_app(manager, THE_DICTATION)
        i18n_t = MagicMock(side_effect=lambda key, **kw: key)
        keystrokes: list = []

        with (
            _install_fake_clipboard(fake),
            patch("voice_typer.server.app_undo.i18n.t", i18n_t),
            _armed_paste_path(keystrokes),
        ):
            UndoRepasteController(app).repaste_last()

        assert fake.copies == [THE_DICTATION]
        assert fake.text == USER_NEW
        assert keystrokes == []
        assert clip_mod._pending_restores == []
        app.tray.notify.assert_called_once_with(APP_NAME, "notify.app.repaste_blocked")

    def test_repaste_dispatches_when_the_clipboard_still_holds_it(self, fake_clipboard):
        manager = make_clipboard_manager()
        app = _make_repaste_app(manager, THE_DICTATION)
        i18n_t = MagicMock(side_effect=lambda key, **kw: key)
        keystrokes: list = []

        with (
            patch("voice_typer.server.app_undo.i18n.t", i18n_t),
            _armed_paste_path(keystrokes),
        ):
            UndoRepasteController(app).repaste_last()

        assert fake_clipboard.copies == [THE_DICTATION]
        assert len(keystrokes) == 1
        app.tray.notify.assert_called_once_with(APP_NAME, "notify.app.repaste_done")


class TestRestoreDuringDelayWindow:
    """Gate 3: the restore re-checks the clipboard after the delay."""

    def test_user_copy_during_the_restore_delay_is_preserved(self, fake_clipboard):
        manager = make_clipboard_manager()
        snapshot = make_clipboard_snapshot()
        snapshot.restore = MagicMock()
        fake_clipboard.text = THE_DICTATION

        def _user_copies_during_the_delay(_seconds: float) -> None:
            fake_clipboard.text = USER_NEW

        with patch.object(clip_mod, "time") as mock_time:
            mock_time.sleep = MagicMock(side_effect=_user_copies_during_the_delay)
            manager._delayed_restore(snapshot, THE_DICTATION, 0.0)

        mock_time.sleep.assert_called_once()
        snapshot.restore.assert_not_called()
        assert fake_clipboard.text == USER_NEW

    def test_atexit_restores_while_the_clipboard_holds_the_dictation(self, fake_clipboard):
        manager = make_clipboard_manager()
        snapshot = make_clipboard_snapshot()
        snapshot.restore = MagicMock()
        entry = (manager, snapshot, THE_DICTATION, 0.0)
        with clip_mod._pending_restores_lock:
            clip_mod._pending_restores.append(entry)
        fake_clipboard.text = THE_DICTATION

        clip_mod._force_restore_pending_at_exit()

        snapshot.restore.assert_called_once()
        assert clip_mod._pending_restores == []

    def test_atexit_skips_when_the_user_copied_something_newer(self, fake_clipboard):
        manager = make_clipboard_manager()
        snapshot = make_clipboard_snapshot()
        snapshot.restore = MagicMock()
        entry = (manager, snapshot, THE_DICTATION, 0.0)
        with clip_mod._pending_restores_lock:
            clip_mod._pending_restores.append(entry)
        fake_clipboard.text = USER_NEW  # provably the user's own copy

        clip_mod._force_restore_pending_at_exit()

        snapshot.restore.assert_not_called()
        assert fake_clipboard.text == USER_NEW
        assert clip_mod._pending_restores == []


class TestUnreadableClipboardFailsOpen:
    """An unreadable clipboard (tri-state None) must not block Windows dispatch."""

    def test_windows_dispatch_continues_when_the_read_fails(self, fake_clipboard):
        keystrokes: list = []
        sendinput = MagicMock(return_value=True)
        with (
            _armed_paste_path(keystrokes, windows=True),
            patch.object(clip_mod, "_paste_from_clipboard", side_effect=OSError("clipboard busy")),
            patch.object(clip_mod, "_send_ctrl_v_win32", sendinput),
        ):
            manager = make_clipboard_manager()
            pasted = manager.paste(
                snapshot=None,
                pasted_text=THE_DICTATION,
                expected_fingerprint=text_fingerprint(THE_DICTATION),
            )

        assert pasted is True
        sendinput.assert_called_once()
        assert keystrokes == []
