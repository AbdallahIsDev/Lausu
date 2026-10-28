"""Patching a proxied level-monitor name must survive ``monkeypatch.undo``.

pytest >= 9.2 records undo state from ``target.__dict__``, so a name that only
exists virtually (routed to the ``_state`` singleton) used to be undone with
``delattr``: that raised, which aborted the undo stack and leaked every patch
the undo had not reached yet (one abort poisoned 8000+ later tests in CI).
"""

from __future__ import annotations

import threading

import pytest
from voice_typer.server.level_monitor._state import _State, _state


class TestMonkeypatchUndo:
    def test_undo_restores_the_state_value_when_patching_the_owner(self):
        patcher = pytest.MonkeyPatch()
        original = _state._monitor_lock
        replacement = threading.Lock()
        try:
            patcher.setattr(_state, "_monitor_lock", replacement)
            assert _state._monitor_lock is replacement
        finally:
            patcher.undo()
        assert _state._monitor_lock is original

    def test_undo_of_a_proxied_patch_leaves_a_usable_value(self):
        import voice_typer.server.level_monitor as lm

        patcher = pytest.MonkeyPatch()
        try:
            patcher.setattr(lm, "_monitor_lock", threading.Lock())
        finally:
            patcher.undo()
        # Undo cannot know the pre-patch value, but it must never leave the
        # attribute missing: every ``with _state._monitor_lock`` would break.
        assert isinstance(_state._monitor_lock, type(_State()._monitor_lock))

    def test_delete_resets_a_proxied_name_to_its_default(self):
        import voice_typer.server.level_monitor as lm

        del lm._test_mode
        assert _state._test_mode is False

    def test_delete_of_an_unproxied_name_still_raises(self):
        import voice_typer.server.level_monitor as lm

        with pytest.raises(AttributeError):
            del lm.not_a_real_attribute
