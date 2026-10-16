"""Service-level tests for the mic-guard / output-level surface (S1 + S5).

These cover :class:`StatusMixin`'s three new methods as they are actually
composed into ``LausuService`` — the handlers in
``tests/handlers/test_mic_volume_handlers.py`` mock the service, so this file
is where the delegation to ``app._mic_guard`` / ``app._volume_ducker`` is
pinned.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from voice_typer.server.service.status import StatusMixin


def _mixin_with_guard(guard: object | None) -> StatusMixin:
    mixin = StatusMixin.__new__(StatusMixin)
    mixin._volume_backend_status_cache = None
    app = MagicMock()
    if guard is None:
        del app._mic_guard
    else:
        app._mic_guard = guard
    mixin._app = app
    return mixin


@pytest.fixture
def guard() -> MagicMock:
    g = MagicMock()
    g.is_available = True
    g.supports_set = True
    g.backend_name = "pycaw (WASAPI capture)"
    g.get_level.return_value = 0.92
    g.set_level.return_value = True
    return g


class TestGetMicrophoneVolume:
    def test_reports_the_guard_snapshot(self, guard) -> None:
        mixin = _mixin_with_guard(guard)
        assert mixin.get_microphone_volume() == {
            "available": True,
            "level": 0.92,
            "supports_set": True,
            "name": "pycaw (WASAPI capture)",
        }

    def test_missing_guard_is_a_disabled_sentinel(self) -> None:
        """The guard is lazy; an unresolved one must read as unavailable, not 0%."""
        mixin = _mixin_with_guard(None)
        assert mixin.get_microphone_volume() == {
            "available": False,
            "level": None,
            "supports_set": False,
            "name": "disabled",
        }

    def test_macos_no_gain_device_reports_supports_set_false(self, guard) -> None:
        guard.supports_set = False
        guard.get_level.return_value = 0.6
        mixin = _mixin_with_guard(guard)
        result = mixin.get_microphone_volume()
        assert result["supports_set"] is False
        assert result["level"] == 0.6


class TestSetMicrophoneVolume:
    def test_writes_the_real_device_value(self, guard) -> None:
        mixin = _mixin_with_guard(guard)
        assert mixin.set_microphone_volume(1.0) == {"ok": True, "level": 1.0}
        guard.set_level.assert_called_once_with(1.0)

    def test_missing_guard_reports_not_ok(self) -> None:
        mixin = _mixin_with_guard(None)
        assert mixin.set_microphone_volume(1.0) == {"ok": False, "level": None}

    def test_clamps_and_reports_the_written_value(self, guard) -> None:
        mixin = _mixin_with_guard(guard)
        assert mixin.set_microphone_volume(1.4) == {"ok": True, "level": 1.0}
        guard.set_level.assert_called_once_with(1.0)

    def test_non_numeric_input_is_rejected_without_touching_the_device(self, guard) -> None:
        mixin = _mixin_with_guard(guard)
        assert mixin.set_microphone_volume("loud") == {"ok": False, "level": None}
        guard.set_level.assert_not_called()

    def test_device_refusal_is_surfaced_as_not_ok(self, guard) -> None:
        guard.set_level.return_value = False
        mixin = _mixin_with_guard(guard)
        assert mixin.set_microphone_volume(1.0)["ok"] is False


class TestSetOutputVolume:
    @staticmethod
    def _mixin(ducker: object | None) -> StatusMixin:
        mixin = StatusMixin.__new__(StatusMixin)
        mixin._volume_backend_status_cache = None
        app = MagicMock()
        if ducker is None:
            del app._volume_ducker
        else:
            app._volume_ducker = ducker
        mixin._app = app
        return mixin

    def test_initializes_then_writes(self) -> None:
        ducker = MagicMock()
        ducker.initialize.return_value = True
        ducker.set_level.return_value = True
        mixin = self._mixin(ducker)

        assert mixin.set_output_volume(0.75) == {"ok": True, "level": 0.75}
        ducker.initialize.assert_called_once_with()
        ducker.set_level.assert_called_once_with(0.75)

    def test_uninitializable_backend_reports_not_ok(self) -> None:
        ducker = MagicMock()
        ducker.initialize.return_value = False
        mixin = self._mixin(ducker)

        assert mixin.set_output_volume(0.75) == {"ok": False, "level": None}
        ducker.set_level.assert_not_called()

    def test_missing_ducker_reports_not_ok(self) -> None:
        mixin = self._mixin(None)
        assert mixin.set_output_volume(0.75) == {"ok": False, "level": None}

    def test_backend_exception_is_swallowed(self) -> None:
        ducker = MagicMock()
        ducker.initialize.side_effect = RuntimeError("no audio device")
        mixin = self._mixin(ducker)
        assert mixin.set_output_volume(0.75) == {"ok": False, "level": None}

    def test_clamps_the_target(self) -> None:
        ducker = MagicMock()
        ducker.initialize.return_value = True
        ducker.set_level.return_value = True
        mixin = self._mixin(ducker)

        assert mixin.set_output_volume(3.0)["level"] == 1.0
        ducker.set_level.assert_called_once_with(1.0)
