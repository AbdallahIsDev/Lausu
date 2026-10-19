"""Clipboard-on-quit: the pending restore runs before teardown kills it.

docs/voice_typer_recording_edge_cases.md §5: a graceful quit killed the
``clipboard-restore`` daemon and ended in ``os._exit`` (atexit skipped),
so the user's original clipboard never came back. ``do_cleanup`` now runs
the pending restore synchronously, bounded and best-effort, before the
teardown phases; a violent kill or power loss cannot run code and stays
accepted-unfixable.

No test touches the real clipboard: reads/writes go through patched
``clipboard`` primitives.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from voice_typer.server import clipboard as clip_mod
from voice_typer.server.clipboard import restore as restore_mod
from voice_typer.server.shutdown.cleanup import _restore_clipboard_before_teardown, do_cleanup, do_fast_cleanup

from tests.fixtures.shutdown_helpers import (
    make_cancelled_registry_recording,
    make_quiet_cleanup_controller,
)

DICTATED = "dictated text that owns the clipboard"


@pytest.fixture(autouse=True)
def _clear_pending_restores():
    with clip_mod._pending_restores_lock:
        clip_mod._pending_restores.clear()
    yield
    with clip_mod._pending_restores_lock:
        clip_mod._pending_restores.clear()


def _register(snapshot, text: str = DICTATED, delay: float = 1.5):
    entry = (MagicMock(name="manager"), snapshot, text, delay)
    with clip_mod._pending_restores_lock:
        clip_mod._pending_restores.append(entry)
    return entry


def _make_app(cycle_id="#7") -> SimpleNamespace:
    return SimpleNamespace(
        _cleanup_done=False,
        _cycle_id=cycle_id,
        recording=make_cancelled_registry_recording(),
        _ipc_server=None,
    )


class TestPendingRestoreFlush:
    def test_matching_clipboard_is_restored_and_claimed(self):
        snapshot = MagicMock(name="snapshot")
        _register(snapshot)
        with patch.object(clip_mod, "_paste_from_clipboard", return_value=DICTATED):
            restored = restore_mod.restore_pending_before_shutdown()
        assert restored == 1
        snapshot.restore.assert_called_once_with()
        assert clip_mod._pending_restores == []

    def test_changed_clipboard_is_left_alone(self):
        snapshot = MagicMock(name="snapshot")
        _register(snapshot)
        with patch.object(clip_mod, "_paste_from_clipboard", return_value="the user's own text"):
            restored = restore_mod.restore_pending_before_shutdown()
        assert restored == 0
        snapshot.restore.assert_not_called()

    def test_unreadable_clipboard_still_restores(self):
        """An unreadable clipboard cannot belong to a newer cycle."""
        snapshot = MagicMock(name="snapshot")
        _register(snapshot)
        with patch.object(clip_mod, "_paste_from_clipboard", side_effect=RuntimeError("no clipboard")):
            restored = restore_mod.restore_pending_before_shutdown()
        assert restored == 1
        snapshot.restore.assert_called_once_with()

    def test_flush_is_idempotent(self):
        snapshot = MagicMock(name="snapshot")
        _register(snapshot)
        with patch.object(clip_mod, "_paste_from_clipboard", return_value=DICTATED):
            assert restore_mod.restore_pending_before_shutdown() == 1
            assert restore_mod.restore_pending_before_shutdown() == 0
        snapshot.restore.assert_called_once_with()

    def test_failing_snapshot_never_raises(self):
        first, second = MagicMock(name="first"), MagicMock(name="second")
        first.restore.side_effect = RuntimeError("clipboard locked")
        _register(first)
        _register(second)
        with patch.object(clip_mod, "_paste_from_clipboard", return_value=DICTATED):
            restored = restore_mod.restore_pending_before_shutdown()
        # The failing snapshot does not stop the next one.
        assert restored == 1
        second.restore.assert_called_once_with()


class TestDoCleanupRunsTheFlush:
    def test_do_cleanup_restores_pending_before_any_phase(self):
        order: list[str] = []
        snapshot = MagicMock(name="snapshot")
        snapshot.restore.side_effect = lambda: order.append("restore")
        _register(snapshot)
        app = _make_app()
        controller = make_quiet_cleanup_controller(app, order=order)

        with patch.object(clip_mod, "_paste_from_clipboard", return_value=DICTATED):
            do_cleanup(controller)

        assert order[:2] == ["restore", "drain"], f"pending restore must land before the phases; got {order}"

    def test_fast_cleanup_restores_pending(self, monkeypatch):
        monkeypatch.setattr("voice_typer.server.shutdown_controller.os._exit", lambda code=0: None)
        snapshot = MagicMock(name="snapshot")
        _register(snapshot)
        app = _make_app("#9")
        app._crash_recovery = None
        app.history_db = None
        app.recorder = None
        app._mutex_handle = None
        app._restore_volume = MagicMock()
        app._duck_crash_recovery = MagicMock()
        controller = make_quiet_cleanup_controller(app)

        with patch.object(clip_mod, "_paste_from_clipboard", return_value=DICTATED):
            do_fast_cleanup(controller)

        snapshot.restore.assert_called_once_with()

    def test_do_cleanup_skips_restore_when_clipboard_changed(self):
        snapshot = MagicMock(name="snapshot")
        _register(snapshot)
        app = _make_app()
        controller = make_quiet_cleanup_controller(app)

        with patch.object(clip_mod, "_paste_from_clipboard", return_value="newer text"):
            do_cleanup(controller)

        snapshot.restore.assert_not_called()


class TestBoundedFlush:
    def test_hanging_restore_is_bounded_and_logged(self, caplog):
        release = threading.Event()
        snapshot = MagicMock(name="snapshot")
        snapshot.restore.side_effect = lambda: release.wait(timeout=5.0)
        _register(snapshot)

        started = time.perf_counter()
        try:
            with (
                patch.object(clip_mod, "_paste_from_clipboard", return_value=DICTATED),
                caplog.at_level("WARNING", logger="voice_typer.server.shutdown_controller"),
            ):
                _restore_clipboard_before_teardown(MagicMock(), timeout=0.2, label="test")
        finally:
            release.set()
        elapsed = time.perf_counter() - started

        assert elapsed < 2.0, f"bounded flush must return long before the hang; took {elapsed:.2f}s"
        assert any("timed out" in rec.message.lower() for rec in caplog.records), (
            "a timed-out bounded restore must warn"
        )
