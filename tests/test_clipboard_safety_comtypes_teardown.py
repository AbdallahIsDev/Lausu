"""TK-35: Win32 comtypes teardown coverage for ``_is_safe_paste_target_impl``."""

from __future__ import annotations

import ctypes
import logging
import sys
from unittest.mock import MagicMock, patch

import pytest
from voice_typer.server import (
    _com,  # noqa: E402
    clipboard as clip_mod,  # noqa: E402
)
from voice_typer.server.clipboard.safety import _is_safe_paste_target_impl  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_com_ready():
    """Forget the per-thread "COM is up" flag between tests.

    ``ensure_com_initialized`` deliberately initialises once per *thread* and
    never tears down, so the flag outlives a single test on the shared pytest
    thread. Clearing it keeps each test's ``CoInitialize`` accounting honest.
    """
    if hasattr(_com._READY, "initialized"):
        del _com._READY.initialized
    yield
    if hasattr(_com._READY, "initialized"):
        del _com._READY.initialized


@pytest.fixture()
def fake_win32(monkeypatch):
    """Mock ``ctypes.windll`` + the clipboard package so the Win32"""
    mock_user32 = MagicMock(name="user32")
    mock_user32.GetForegroundWindow.return_value = 0x1234  # non-zero hwnd
    mock_windll = MagicMock(name="windll")
    mock_windll.user32 = mock_user32

    # ``_get_uia_focused_element`` is patched to a mock so the real
    monkeypatch.setattr(clip_mod, "is_windows", lambda: True)
    monkeypatch.setattr(clip_mod, "is_macos", lambda: False)
    monkeypatch.setattr(clip_mod, "is_linux", lambda: False)
    monkeypatch.setattr(clip_mod, "_is_elevated_target", lambda hwnd: False)
    monkeypatch.setattr(clip_mod, "_get_uia_focused_element", MagicMock(name="focused"))
    monkeypatch.setattr(clip_mod, "log", MagicMock(name="log"))

    with patch("ctypes.windll", mock_windll, create=True):
        yield {"user32": mock_user32, "windll": mock_windll}


def _install_fake_comtypes() -> tuple[MagicMock, MagicMock]:
    """Inject a fake ``comtypes`` module into ``sys.modules`` and return"""
    fake_comtypes = MagicMock(name="comtypes")
    fake_client = MagicMock(name="comtypes.client")
    fake_comtypes.client = fake_client
    return fake_comtypes, fake_client


class TestComtypesTeardown:
    """COM is entered once per thread and never torn down."""

    def test_password_field_blocks_paste_and_still_tears_down_com(self, fake_win32):
        """
        the early ``return`` must not skip the per-thread COM init, and
        nothing may uninitialise the apartment afterwards.
        """
        fake_comtypes, _fake_client = _install_fake_comtypes()
        password_field = MagicMock(return_value=True)
        content_editable = MagicMock(return_value=False)

        with (
            patch.dict(sys.modules, {"comtypes": fake_comtypes, "comtypes.client": _fake_client}),
            patch.object(clip_mod, "_is_password_field", password_field),
            patch.object(clip_mod, "_is_content_editable", content_editable),
        ):
            result = _is_safe_paste_target_impl()

        assert result is False, "password field must block paste"
        fake_comtypes.CoInitialize.assert_called_once_with()
        fake_comtypes.CoUninitialize.assert_not_called()
        # Early return means the contentEditable probe never ran.
        content_editable.assert_not_called()

    def test_safe_target_tears_down_com(self, fake_win32):
        """Safe target (no password field, no contentEditable) → True,"""
        fake_comtypes, _fake_client = _install_fake_comtypes()

        with (
            patch.dict(sys.modules, {"comtypes": fake_comtypes, "comtypes.client": _fake_client}),
            patch.object(clip_mod, "_is_password_field", lambda focused, hwnd: False),
            patch.object(clip_mod, "_is_content_editable", lambda focused: False),
        ):
            result = _is_safe_paste_target_impl()

        assert result is True
        fake_comtypes.CoInitialize.assert_called_once_with()
        fake_comtypes.CoUninitialize.assert_not_called()

    def test_content_editable_probe_raising_still_tears_down_com(self, fake_win32):
        """The contentEditable probe is fail-open (logs, continues) and"""
        fake_comtypes, _fake_client = _install_fake_comtypes()

        def _boom(_focused):
            raise RuntimeError("UIA contentEditable probe failed")

        with (
            patch.dict(sys.modules, {"comtypes": fake_comtypes, "comtypes.client": _fake_client}),
            patch.object(clip_mod, "_is_password_field", lambda focused, hwnd: False),
            patch.object(clip_mod, "_is_content_editable", _boom),
        ):
            result = _is_safe_paste_target_impl()

        assert result is True, "contentEditable failure must fail open"
        fake_comtypes.CoInitialize.assert_called_once_with()
        fake_comtypes.CoUninitialize.assert_not_called()

    def test_comtypes_import_error_skips_teardown(self, fake_win32):
        """comtypes unavailable (ImportError) → no CoInitialize, no"""
        with (
            patch.dict(sys.modules, {"comtypes": None, "comtypes.client": None}),
            patch.object(clip_mod, "_is_password_field", lambda focused, hwnd: False),
            patch.object(clip_mod, "_is_content_editable", lambda focused: False),
        ):
            result = _is_safe_paste_target_impl()

        assert result is True, "no comtypes → heuristic path must still allow paste"

    def test_coinitialize_raising_skips_teardown_but_proceeds(self, fake_win32):
        """A failing ``CoInitialize`` is tolerated: paste still goes through."""
        fake_comtypes, _fake_client = _install_fake_comtypes()
        fake_comtypes.CoInitialize.side_effect = OSError("COM init failed")

        with (
            patch.dict(sys.modules, {"comtypes": fake_comtypes, "comtypes.client": _fake_client}),
            patch.object(clip_mod, "_is_password_field", lambda focused, hwnd: False),
            patch.object(clip_mod, "_is_content_editable", lambda focused: False),
        ):
            result = _is_safe_paste_target_impl()

        assert result is True
        fake_comtypes.CoInitialize.assert_called_once_with()
        fake_comtypes.CoUninitialize.assert_not_called()
        # The failed init must not be recorded as success: a later call retries.
        assert not hasattr(_com._READY, "initialized")


class _ComPointerProbe(ctypes.c_void_p):
    """Stand-in for a comtypes interface pointer.

    Mirrors ``comtypes._post_coinit.unknwn._compointer_base``: the COM refcount
    is released from ``__del__``, guarded by truthiness of the raw pointer. So
    ``Release()`` followed by clearing the pointer means exactly one release —
    which is what the ordering assertions below count.
    """

    def __get_value(self):
        return self

    value = property(__get_value)

    def __init__(self, events: list[str]) -> None:
        super().__init__(0x1)
        self._events = events

    def GetCurrentPropertyValue(self, _property_id: int) -> bool:  # noqa: N802 - UIA API name
        return False

    def Release(self) -> None:  # noqa: N802 - COM interface method name
        self._events.append("release")

    def __del__(self) -> None:
        if self:
            self._events.append("release")


class TestElementReleasedExactlyOnce:
    """The UIA element must be released exactly once, and COM must stay up.

    The Windows CI workers used to die with "Windows fatal exception: access
    violation" inside ``comtypes._compointer_base.__del__ -> Release()`` while
    pytest dropped a test's captured ``LogRecord``s. A record's ``exc_info``
    traceback pins the frame that holds the element, so the wrapper is
    finalised at an arbitrary later point — and if the apartment has been
    torn down in the meantime, ``Release()`` calls through a dead vtable and
    takes the whole worker with it.

    Both halves are pinned here: the element is released while COM is up (so
    the late finaliser is a no-op), and nothing ever calls ``CoUninitialize``
    (so the apartment is never torn down under a live wrapper).
    """

    @staticmethod
    def _fake_comtypes(events: list[str]) -> tuple[MagicMock, MagicMock]:
        fake_comtypes, fake_client = _install_fake_comtypes()
        fake_comtypes.CoUninitialize.side_effect = lambda: events.append("couninitialize")
        return fake_comtypes, fake_client

    def test_safe_target_releases_element_once(self, fake_win32):
        """Plain path: no password field, no contentEditable."""
        events: list[str] = []
        fake_comtypes, fake_client = self._fake_comtypes(events)

        with (
            patch.dict(sys.modules, {"comtypes": fake_comtypes, "comtypes.client": fake_client}),
            # A fresh probe per call, referenced only by the local under test.
            patch.object(clip_mod, "_get_uia_focused_element", lambda: _ComPointerProbe(events)),
            patch.object(clip_mod, "_is_password_field", lambda focused, hwnd: False),
            patch.object(clip_mod, "_is_content_editable", lambda focused: False),
        ):
            result = _is_safe_paste_target_impl()

        assert result is True
        assert events == ["release"], (
            "the UIA element must be released exactly once and the apartment must "
            f"stay initialised; observed: {events}"
        )

    def test_fail_closed_path_releases_element_once(self, fake_win32, caplog, monkeypatch):
        """The fail-closed path is the one that crashed CI.

        ``exc_info=True`` stores the traceback on the ``LogRecord``, and that
        traceback pins this frame — so merely dropping the local is not enough.
        The explicit release must happen, and it must be the only one: a
        second ``Release()`` from ``__del__`` is the access violation.
        """
        events: list[str] = []
        fake_comtypes, fake_client = self._fake_comtypes(events)
        monkeypatch.setattr(clip_mod, "log", logging.getLogger("voice_typer.server.clipboard"))

        def _uia_raised(_focused, _hwnd):
            raise RuntimeError("UIA password probe failed")

        with (
            caplog.at_level(logging.DEBUG, logger="voice_typer.server.clipboard"),
            patch.dict(sys.modules, {"comtypes": fake_comtypes, "comtypes.client": fake_client}),
            patch.object(clip_mod, "_get_uia_focused_element", lambda: _ComPointerProbe(events)),
            patch.object(clip_mod, "_is_password_field", _uia_raised),
            patch.object(clip_mod, "_is_content_editable", lambda focused: False),
        ):
            result = _is_safe_paste_target_impl()

        assert result is False, "a raising password probe must fail closed"
        assert any(record.exc_info for record in caplog.records), "the traceback must be captured on the record"
        assert events == ["release"], (
            "the pinned traceback must not cause a second release, and COM must "
            f"never be uninitialised; observed: {events}"
        )


class TestComInitialisedOncePerThread:
    """``_ensure_com_initialized`` enters the apartment once and stays."""

    def test_second_call_on_same_thread_does_not_reinit(self, fake_win32):
        fake_comtypes, fake_client = _install_fake_comtypes()

        with (
            patch.dict(sys.modules, {"comtypes": fake_comtypes, "comtypes.client": fake_client}),
            patch.object(clip_mod, "_is_password_field", lambda focused, hwnd: False),
            patch.object(clip_mod, "_is_content_editable", lambda focused: False),
        ):
            assert _is_safe_paste_target_impl() is True
            assert _is_safe_paste_target_impl() is True

        fake_comtypes.CoInitialize.assert_called_once_with()
        fake_comtypes.CoUninitialize.assert_not_called()
