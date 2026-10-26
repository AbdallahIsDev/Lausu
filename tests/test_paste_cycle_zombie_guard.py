"""A force-recovered ("zombie") worker must never paste over a live cycle.

Single-flight (AGENTS.md C-CONC-1) makes overlapping dictation impossible
except through a stuck worker: the watchdog frees the busy flag, the user
starts a new cycle, and the old Python thread wakes up later. Three gates
protect the live cycle: cycle liveness before the clipboard borrow, a
clipboard fingerprint before every keystroke, and a conditional restore.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from voice_typer.server import clipboard as clip_mod
from voice_typer.server.clipboard import ClipboardManager
from voice_typer.server.clipboard.fingerprint import clipboard_holds, text_fingerprint
from voice_typer.server.clipboard_snapshot import ClipboardSnapshot
from voice_typer.server.cycle_guard import is_cycle_live
from voice_typer.server.dictation_pipeline import DictationPipeline
from voice_typer.server.dictation_stages import (
    CancellationGuard,
    PasteStage,
    PipelineContext,
    _PipelineAbortCancelled,
)

from tests.fixtures.clipboard_helpers import make_clipboard_manager, make_clipboard_snapshot

USER_CLIPBOARD = "the user's own copied text"


class _FakeClipboard:
    """In-memory clipboard: no test ever touches the real one."""

    def __init__(self, text: str = USER_CLIPBOARD) -> None:
        self.text = text
        self.copies: list[str] = []
        self.keystrokes: list[tuple[object, ...]] = []

    def copy(self, text: str) -> None:
        self.text = text
        self.copies.append(text)

    def read(self) -> str:
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


@pytest.fixture
def fake_clipboard():
    """Redirect every clipboard read/write to an in-memory string."""
    fake = _FakeClipboard()
    with (
        patch.object(clip_mod, "_copy_to_clipboard", side_effect=fake.copy),
        patch.object(clip_mod, "_paste_from_clipboard", side_effect=fake.read),
        patch.object(clip_mod, "_win32_empty_clipboard"),
        patch.object(clip_mod, "_win32_exclude_clipboard_from_monitoring"),
        patch.object(ClipboardSnapshot, "capture", return_value=None),
        patch.object(ClipboardManager, "_get_clipboard_sequence_number", return_value=0),
    ):
        yield fake


def _make_app(cycle_id: str, *, cancelled: tuple[str, ...] = (), clipboard=None) -> SimpleNamespace:
    recording = MagicMock()
    recording._cancelled_cycle_ids = OrderedDict((cid, None) for cid in cancelled)
    recording._cancelled_cycle_ids_lock = threading.Lock()
    config = MagicMock()
    config.paste_on_stop = True
    config.clipboard_save_restore = True
    config.crash_recovery_enabled = True
    return SimpleNamespace(
        _cycle_id=cycle_id,
        recording=recording,
        config=config,
        clipboard=clipboard if clipboard is not None else make_clipboard_manager(),
        tray=MagicMock(),
        _waveform_bubble=MagicMock(),
        _busyness=MagicMock(),
        _crash_recovery=MagicMock(),
        _schedule_timer=MagicMock(),
    )


def _make_pipeline(app: SimpleNamespace, cycle_id: str) -> DictationPipeline:
    pipeline = DictationPipeline.__new__(DictationPipeline)
    pipeline._app = app
    pipeline._cycle_id = cycle_id
    pipeline._device_info = "test-device"
    pipeline._hide_or_idle_bubble = MagicMock()
    return pipeline


class TestCycleLiveness:
    def test_current_uncancelled_cycle_is_live(self):
        app = _make_app("#1")
        assert is_cycle_live(app, "#1") is True

    def test_superseded_cycle_is_not_live(self):
        app = _make_app("#2")
        assert is_cycle_live(app, "#1") is False

    def test_cancelled_cycle_is_not_live(self):
        app = _make_app("#1", cancelled=("#1",))
        assert is_cycle_live(app, "#1") is False

    def test_app_without_cycle_bookkeeping_fails_open(self):
        assert is_cycle_live(SimpleNamespace(), "#1") is True
        assert is_cycle_live(SimpleNamespace(), "") is True


class TestZombiePasteStep:
    def test_stale_cycle_touches_nothing(self, fake_clipboard):
        app = _make_app("#2", cancelled=("#1",))
        pipeline = _make_pipeline(app, "#1")
        app.clipboard.paste = MagicMock()

        pipeline._copy_and_paste("stale dictation")

        assert fake_clipboard.copies == []
        app.clipboard.paste.assert_not_called()
        assert fake_clipboard.text == USER_CLIPBOARD
        # The live cycle owns the bubble/tray; the zombie must leave them alone.
        pipeline._hide_or_idle_bubble.assert_not_called()
        app.tray.set_state.assert_not_called()

    def test_superseded_cycle_without_cancelled_flag_is_blocked(self, fake_clipboard):
        app = _make_app("#2")
        pipeline = _make_pipeline(app, "#1")

        pipeline._copy_and_paste("stale dictation")

        assert fake_clipboard.copies == []
        assert fake_clipboard.text == USER_CLIPBOARD

    def test_cancelled_current_cycle_is_blocked(self, fake_clipboard):
        app = _make_app("#1", cancelled=("#1",))
        pipeline = _make_pipeline(app, "#1")

        pipeline._copy_and_paste("cancelled dictation")

        assert fake_clipboard.copies == []
        assert fake_clipboard.text == USER_CLIPBOARD

    def test_cancellation_during_the_borrow_suppresses_the_keystroke(self, fake_clipboard):
        app = _make_app("#1")
        pipeline = _make_pipeline(app, "#1")
        app.clipboard.paste = MagicMock()
        write = fake_clipboard.copy

        def _write_then_new_cycle(text: str) -> None:
            write(text)
            app._cycle_id = "#2"  # a new dictation started mid-borrow

        with patch.object(clip_mod, "_copy_to_clipboard", side_effect=_write_then_new_cycle):
            pipeline._copy_and_paste("stale dictation")

        app.clipboard.paste.assert_not_called()
        app.tray.set_state.assert_not_called()


class TestLiveCycleStillPastes:
    def test_live_cycle_copies_and_dispatches(self, fake_clipboard):
        app = _make_app("#1")
        pipeline = _make_pipeline(app, "#1")

        with (
            # The pynput gate is runner-dependent (``_Controller`` is None when
            # the CI box cannot import pynput.keyboard), so stub it like the
            # fingerprint tests below instead of asserting on the environment.
            patch.object(clip_mod, "_Controller", MagicMock()),
            patch.object(ClipboardManager, "_is_safe_paste_target", return_value=True),
            patch.object(ClipboardManager, "_check_target_safety", return_value=(True, None)),
            patch.object(ClipboardManager, "_check_text_field_focus", return_value=(True, None)),
            patch.object(ClipboardManager, "_dispatch_keystroke", return_value=True) as dispatch,
        ):
            pipeline._copy_and_paste("live dictation")

        assert fake_clipboard.copies == ["live dictation"]
        assert fake_clipboard.text == "live dictation"
        dispatch.assert_called_once()


class TestCancellationGuardUsesLiveness:
    def _ctx(self, app, pipeline, cycle_id: str) -> PipelineContext:
        return PipelineContext(cycle_id=cycle_id, audio=None, app=app, pipeline=pipeline)

    def test_zombie_is_aborted_without_touching_the_live_bubble(self):
        app = _make_app("#2", cancelled=("#1",))
        pipeline = _make_pipeline(app, "#1")

        with pytest.raises(_PipelineAbortCancelled):
            CancellationGuard(PasteStage()).run("late text", self._ctx(app, pipeline, "#1"))

        pipeline._hide_or_idle_bubble.assert_not_called()

    def test_cancelled_current_cycle_still_tears_down_the_bubble(self):
        app = _make_app("#1", cancelled=("#1",))
        pipeline = _make_pipeline(app, "#1")

        with pytest.raises(_PipelineAbortCancelled):
            CancellationGuard(PasteStage()).run("late text", self._ctx(app, pipeline, "#1"))

        pipeline._hide_or_idle_bubble.assert_called_once()

    def test_live_cycle_runs_the_wrapped_stage(self):
        app = _make_app("#1")
        pipeline = _make_pipeline(app, "#1")
        pipeline._copy_and_paste = MagicMock()

        CancellationGuard(PasteStage()).run("text", self._ctx(app, pipeline, "#1"))

        pipeline._copy_and_paste.assert_called_once_with("text")


@patch.object(clip_mod, "is_windows", return_value=False)
@patch.object(clip_mod, "is_macos", return_value=False)
class TestFingerprintGate:
    """The fingerprint gate is the subject here, so the two gates that are
    NOT platform-neutral are stubbed out of the way:

    - ``_check_target_safety`` fails CLOSED on Linux when ``pyatspi`` is
      absent ("treating the focused field as unsafe", see
      ``safety._is_safe_paste_target_impl``), which short-circuits the
      dispatch before the fingerprint gate ever runs. Leaving it live made
      these tests pass for the wrong reason on Linux and fail on CI.
    - ``_check_text_field_focus`` is stubbed per test below for the same
      reason (no focused window exists in a test process).
    """

    @staticmethod
    def _safe_target():
        return patch.object(
            ClipboardManager,
            "_check_target_safety",
            return_value=(True, None),
        )

    def test_mismatch_aborts_before_any_keystroke(self, _macos, _windows, fake_clipboard):
        manager = make_clipboard_manager()
        fake_clipboard.text = "a newer cycle's text"
        keystrokes = fake_clipboard.keystrokes

        with (
            self._safe_target(),
            patch.object(clip_mod, "_Controller", MagicMock()),
            patch.object(clip_mod, "_Key", MagicMock()),
            patch.object(ClipboardManager, "_check_text_field_focus", return_value=(True, None)),
            patch.object(ClipboardManager, "_capture_target_handle", return_value=(0, None)),
            patch.object(ClipboardManager, "_detect_focused_process", return_value=None),
            patch.object(ClipboardManager, "_release_stuck_modifiers", lambda self: None),
            patch.object(ClipboardManager, "_safe_key_press", lambda self, *a: keystrokes.append(a)),
        ):
            pasted = manager.paste(
                snapshot=None,
                pasted_text="the dictation",
                expected_fingerprint=text_fingerprint("the dictation"),
            )

        assert pasted is False
        assert keystrokes == []

    def test_matching_clipboard_dispatches_once(self, _macos, _windows, fake_clipboard):
        manager = make_clipboard_manager()
        fake_clipboard.text = "the dictation"
        keystrokes = fake_clipboard.keystrokes

        with (
            self._safe_target(),
            patch.object(clip_mod, "_Controller", MagicMock()),
            patch.object(clip_mod, "_Key", MagicMock()),
            patch.object(ClipboardManager, "_check_text_field_focus", return_value=(True, None)),
            patch.object(ClipboardManager, "_capture_target_handle", return_value=(0, None)),
            patch.object(ClipboardManager, "_detect_focused_process", return_value=None),
            patch.object(ClipboardManager, "_release_stuck_modifiers", lambda self: None),
            patch.object(ClipboardManager, "_safe_key_press", lambda self, *a: keystrokes.append(a)),
        ):
            pasted = manager.paste(
                snapshot=None,
                pasted_text="the dictation",
                expected_fingerprint=text_fingerprint("the dictation"),
            )

        assert pasted is True
        assert len(keystrokes) == 1

    def test_unreadable_clipboard_fails_open(self, _macos, _windows, fake_clipboard):
        manager = make_clipboard_manager()
        with (
            self._safe_target(),
            patch.object(clip_mod, "_paste_from_clipboard", side_effect=OSError("locked")),
            patch.object(clip_mod, "_Controller", MagicMock()),
            patch.object(clip_mod, "_Key", MagicMock()),
            patch.object(ClipboardManager, "_check_text_field_focus", return_value=(True, None)),
            patch.object(ClipboardManager, "_capture_target_handle", return_value=(0, None)),
            patch.object(ClipboardManager, "_detect_focused_process", return_value=None),
            patch.object(ClipboardManager, "_release_stuck_modifiers", lambda self: None),
            patch.object(ClipboardManager, "_safe_key_press", lambda self, *a: None),
        ):
            pasted = manager.paste(
                snapshot=None,
                pasted_text="the dictation",
                expected_fingerprint=text_fingerprint("the dictation"),
            )

        assert pasted is True

    def test_clipboard_holds_is_tri_state(self, _macos, _windows, fake_clipboard):
        fake_clipboard.text = "ours"
        assert clipboard_holds(text_fingerprint("ours")) is True
        assert clipboard_holds(text_fingerprint("theirs")) is False
        assert clipboard_holds(None) is None


class TestConditionalRestore:
    def test_delayed_restore_skips_a_newer_cycle_content(self, fake_clipboard):
        manager = make_clipboard_manager()
        snapshot = make_clipboard_snapshot()
        snapshot.restore = MagicMock()
        fake_clipboard.text = "the newer cycle's dictation"

        with patch.object(clip_mod, "time") as mock_time:
            mock_time.sleep = MagicMock()
            manager._delayed_restore(snapshot, "the old dictation", 0.0)

        snapshot.restore.assert_not_called()
        assert fake_clipboard.text == "the newer cycle's dictation"

    def test_delayed_restore_skips_same_length_different_content(self, fake_clipboard):
        manager = make_clipboard_manager()
        snapshot = make_clipboard_snapshot()
        snapshot.restore = MagicMock()
        fake_clipboard.text = "the old dictatioN"  # same length, one byte differs

        with patch.object(clip_mod, "time") as mock_time:
            mock_time.sleep = MagicMock()
            manager._delayed_restore(snapshot, "the old dictation", 0.0)

        snapshot.restore.assert_not_called()

    def test_delayed_restore_restores_while_the_clipboard_is_ours(self, fake_clipboard):
        manager = make_clipboard_manager()
        snapshot = make_clipboard_snapshot()
        snapshot.restore = MagicMock()
        fake_clipboard.text = "the dictation"

        with patch.object(clip_mod, "time") as mock_time:
            mock_time.sleep = MagicMock()
            manager._delayed_restore(snapshot, "the dictation", 0.0)

        snapshot.restore.assert_called_once()

    def test_atexit_skips_a_newer_cycle_content(self, fake_clipboard):
        manager = make_clipboard_manager()
        snapshot = make_clipboard_snapshot()
        snapshot.restore = MagicMock()
        entry = (manager, snapshot, "the old dictation", 0.0)
        with clip_mod._pending_restores_lock:
            clip_mod._pending_restores.append(entry)
        fake_clipboard.text = "the newer cycle's dictation"

        clip_mod._force_restore_pending_at_exit()

        snapshot.restore.assert_not_called()
        assert fake_clipboard.text == "the newer cycle's dictation"
