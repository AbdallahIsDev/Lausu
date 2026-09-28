"""Text-field-focused auto-paste gate (all platform branches + wiring)."""

from __future__ import annotations

import contextlib
import inspect
from unittest.mock import MagicMock, patch

import pytest
from tests.fixtures.clipboard_helpers import make_clipboard_manager
from voice_typer.server import clipboard as clip_mod
from voice_typer.server.clipboard.manager._paste import PasteMixin
from voice_typer.server.clipboard_target_safety import focused_text as focus_mod


def _ax_response(value):
    return (0, value)


def _mock_macos_ax(role: str | None, *, role_error: bool = False):
    """Build fake AppKit/ApplicationServices modules exposing ``role``."""
    appkit = MagicMock()
    workspace = MagicMock()
    appkit.NSWorkspace.sharedWorkspace.return_value = workspace
    front = MagicMock()
    workspace.frontmostApplication.return_value = front
    front.processIdentifier.return_value = 4242

    appservices = MagicMock()
    appservices.AXUIElementCreateApplication.return_value = "APP_ELEM"

    def copy_attr(_elem, attr, _out):
        if attr == "AXFocusedUIElement":
            return _ax_response("FOCUSED_ELEM")
        if attr == "AXRole":
            if role_error:
                raise RuntimeError("AXRole fetch failed")
            return _ax_response(role)
        return (-1, None)

    appservices.AXUIElementCopyAttributeValue.side_effect = copy_attr
    return appkit, appservices


def _mock_pyatspi(role, *, extra_roles: dict | None = None):
    """Build a fake pyatspi module whose focused accessible has ``role``."""
    fake = MagicMock()
    fake.STATE_FOCUSED = 1 << 10
    defaults = {
        "ROLE_ENTRY": 13,
        "ROLE_TEXT": 20,
        "ROLE_TERMINAL": 72,
        "ROLE_DOCUMENT_FRAME": 56,
        "ROLE_TEXT_LEAF": 21,
        "ROLE_PASSWORD_TEXT": 73,
        "ROLE_PUSH_BOX": 10,
        "ROLE_CHECK_BOX": 4,
        "ROLE_RADIO_BUTTON": 11,
        "ROLE_LABEL": 27,
    }
    if extra_roles:
        defaults.update(extra_roles)
    for name, value in defaults.items():
        setattr(fake, name, value)

    desktop = MagicMock()
    state = MagicMock()
    state.contains.return_value = True
    desktop.getState.return_value = state
    desktop.getRole.return_value = role
    fake.Registry.getDesktop.return_value = desktop
    return fake, desktop


class TestMacosTextFieldFocus:
    def test_text_area_is_text(self):
        appkit, appservices = _mock_macos_ax("AXTextArea")
        with patch.dict("sys.modules", {"AppKit": appkit, "ApplicationServices": appservices}):
            assert focus_mod._is_text_field_focused_macos() is True

    def test_web_area_is_text(self):
        appkit, appservices = _mock_macos_ax("AXWebArea")
        with patch.dict("sys.modules", {"AppKit": appkit, "ApplicationServices": appservices}):
            assert focus_mod._is_text_field_focused_macos() is True

    def test_secure_text_field_is_not_text(self):
        appkit, appservices = _mock_macos_ax("AXSecureTextField")
        with patch.dict("sys.modules", {"AppKit": appkit, "ApplicationServices": appservices}):
            assert focus_mod._is_text_field_focused_macos() is False

    def test_button_is_not_text(self):
        appkit, appservices = _mock_macos_ax("AXButton")
        with patch.dict("sys.modules", {"AppKit": appkit, "ApplicationServices": appservices}):
            assert focus_mod._is_text_field_focused_macos() is False

    def test_unknown_role_fails_open(self):
        appkit, appservices = _mock_macos_ax("AXGroup")
        with patch.dict("sys.modules", {"AppKit": appkit, "ApplicationServices": appservices}):
            assert focus_mod._is_text_field_focused_macos() is True

    def test_pyobjc_missing_fails_open(self):
        import builtins

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name in ("AppKit", "ApplicationServices"):
                raise ImportError("pyobjc missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import), patch.object(clip_mod, "log"):
            assert focus_mod._is_text_field_focused_macos() is True

    def test_ax_error_fails_open(self):
        appkit, appservices = _mock_macos_ax(None, role_error=True)
        with patch.dict("sys.modules", {"AppKit": appkit, "ApplicationServices": appservices}):
            assert focus_mod._is_text_field_focused_macos() is True

    def test_workspace_none_fails_open(self):
        appkit, appservices = _mock_macos_ax("AXButton")
        appkit.NSWorkspace.sharedWorkspace.return_value = None
        with patch.dict("sys.modules", {"AppKit": appkit, "ApplicationServices": appservices}):
            assert focus_mod._is_text_field_focused_macos() is True


class TestLinuxTextFieldFocus:
    def test_entry_is_text(self):
        fake, _desktop = _mock_pyatspi(13)
        with patch.dict("sys.modules", {"pyatspi": fake}), patch.object(clip_mod, "log"):
            assert focus_mod._is_text_field_focused_linux() is True

    def test_terminal_is_text(self):
        fake, _desktop = _mock_pyatspi(72)
        with patch.dict("sys.modules", {"pyatspi": fake}), patch.object(clip_mod, "log"):
            assert focus_mod._is_text_field_focused_linux() is True

    def test_password_role_is_not_text(self):
        fake, _desktop = _mock_pyatspi(73)
        with patch.dict("sys.modules", {"pyatspi": fake}), patch.object(clip_mod, "log"):
            assert focus_mod._is_text_field_focused_linux() is False

    def test_push_box_is_not_text(self):
        fake, _desktop = _mock_pyatspi(10)
        with patch.dict("sys.modules", {"pyatspi": fake}), patch.object(clip_mod, "log"):
            assert focus_mod._is_text_field_focused_linux() is False

    def test_unknown_role_fails_open(self):
        fake, _desktop = _mock_pyatspi(999)
        with patch.dict("sys.modules", {"pyatspi": fake}), patch.object(clip_mod, "log"):
            assert focus_mod._is_text_field_focused_linux() is True

    def test_pyatspi_missing_fails_open(self):
        import builtins

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name == "pyatspi":
                raise ImportError("pyatspi missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import), patch.object(clip_mod, "log"):
            assert focus_mod._is_text_field_focused_linux() is True

    def test_desktop_none_fails_open(self):
        fake, _desktop = _mock_pyatspi(10)
        fake.Registry.getDesktop.return_value = None
        with patch.dict("sys.modules", {"pyatspi": fake}), patch.object(clip_mod, "log"):
            assert focus_mod._is_text_field_focused_linux() is True

    def test_role_fetch_raises_fails_open(self):
        fake, desktop = _mock_pyatspi(10)
        desktop.getRole.side_effect = RuntimeError("boom")
        with patch.dict("sys.modules", {"pyatspi": fake}), patch.object(clip_mod, "log"):
            assert focus_mod._is_text_field_focused_linux() is True


class TestWindowsTextFieldFocus:
    def _uia_element(self, control_type, has_value=False):
        focused = MagicMock()
        focused.GetCurrentPropertyValue.side_effect = lambda pid: {
            30003: control_type,
            30101: has_value,
        }.get(pid)
        return focused

    def _windows_env(self, focused, *, comtypes_available=True):
        """Context stack with UIA/platform mocks for the Windows branch."""
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(clip_mod, "is_windows", return_value=True))
        stack.enter_context(patch.object(clip_mod, "log"))
        stack.enter_context(
            patch(
                "voice_typer.server.clipboard_target_safety._get_uia_focused_element",
                return_value=focused,
            )
        )
        if comtypes_available:
            stack.enter_context(patch.dict("sys.modules", {"comtypes": MagicMock()}))
        else:
            import builtins

            real_import = builtins.__import__

            def _fake_import(name, *args, **kwargs):
                if name == "comtypes":
                    raise ImportError("comtypes missing")
                return real_import(name, *args, **kwargs)

            stack.enter_context(patch("builtins.__import__", side_effect=_fake_import))
        return stack

    def test_edit_is_text(self):
        focused = self._uia_element(50004)
        with self._windows_env(focused):
            assert focus_mod._is_text_field_focused_windows() is True

    def test_document_is_text(self):
        focused = self._uia_element(50030)
        with self._windows_env(focused):
            assert focus_mod._is_text_field_focused_windows() is True

    def test_combo_box_is_text(self):
        focused = self._uia_element(50003)
        with self._windows_env(focused):
            assert focus_mod._is_text_field_focused_windows() is True

    def test_button_is_not_text(self):
        focused = self._uia_element(50000)
        with self._windows_env(focused):
            assert focus_mod._is_text_field_focused_windows() is False

    def test_custom_fails_open(self):
        focused = self._uia_element(50025)
        with self._windows_env(focused):
            assert focus_mod._is_text_field_focused_windows() is True

    def test_content_editable_is_text(self):
        focused = self._uia_element(50025)
        with (
            self._windows_env(focused),
            patch(
                "voice_typer.server.clipboard_target_safety._is_content_editable",
                return_value=True,
            ),
        ):
            assert focus_mod._is_text_field_focused_windows() is True

    def test_comtypes_missing_fails_open(self):
        focused = self._uia_element(50000)
        with self._windows_env(focused, comtypes_available=False):
            assert focus_mod._is_text_field_focused_windows() is True

    def test_uia_error_fails_open(self):
        focused = MagicMock()
        focused.GetCurrentPropertyValue.side_effect = RuntimeError("boom")
        with self._windows_env(focused):
            assert focus_mod._is_text_field_focused_windows() is True

    def test_focused_none_fails_open(self):
        with self._windows_env(None):
            assert focus_mod._is_text_field_focused_windows() is True


class TestFocusDispatcher:
    def test_routes_to_windows(self):
        with (
            patch.object(clip_mod, "is_windows", return_value=True),
            patch.object(focus_mod, "_is_text_field_focused_windows", return_value=True) as win,
            patch.object(focus_mod, "_is_text_field_focused_macos") as mac,
        ):
            assert focus_mod._is_text_field_focused() is True
        win.assert_called_once()
        mac.assert_not_called()

    def test_routes_to_macos(self):
        with (
            patch.object(clip_mod, "is_windows", return_value=False),
            patch.object(clip_mod, "is_macos", return_value=True),
            patch.object(focus_mod, "_is_text_field_focused_macos", return_value=False) as mac,
        ):
            assert focus_mod._is_text_field_focused() is False
        mac.assert_called_once()

    def test_routes_to_linux(self):
        with (
            patch.object(clip_mod, "is_windows", return_value=False),
            patch.object(clip_mod, "is_macos", return_value=False),
            patch.object(clip_mod, "is_linux", return_value=True),
            patch.object(focus_mod, "_is_text_field_focused_linux", return_value=True) as lin,
        ):
            assert focus_mod._is_text_field_focused() is True
        lin.assert_called_once()

    def test_dispatch_exception_fails_open(self):
        with (
            patch.object(clip_mod, "is_windows", side_effect=RuntimeError("boom")),
            patch.object(clip_mod, "log"),
        ):
            assert focus_mod._is_text_field_focused() is True


class TestPasteGateWiring:
    def _run_paste(self, cm, *, is_terminal: bool = False, **paste_kwargs):
        """Drive paste() with the usual e2e mocks; return (result, dispatch)."""
        with (
            patch.object(clip_mod, "_Controller", object()),
            patch.object(clip_mod, "is_windows", return_value=False),
            patch.object(clip_mod, "is_macos", return_value=False),
            patch.object(clip_mod, "is_linux", return_value=True),
            patch.object(clip_mod, "_is_wayland_paste_session", return_value=False),
            patch.object(clip_mod, "_have_wtype", return_value=False),
            patch.object(cm, "_is_safe_paste_target", return_value=True),
            patch.object(cm, "_register_pending_restore", return_value=None),
            patch.object(cm, "_detect_focused_process", return_value="notepad"),
            patch.object(cm, "_is_terminal_process", return_value=is_terminal),
            patch.object(cm, "_capture_target_handle", return_value=(0, None)),
            patch.object(cm, "_log_rich_editor"),
            patch.object(cm, "_post_delay_recheck", return_value=True),
            patch.object(cm, "_finalize_paste", return_value=True),
            patch.object(cm, "_dispatch_keystroke", return_value=True) as dispatch,
            patch.object(clip_mod, "time") as mock_time,
        ):
            mock_time.monotonic.return_value = 100.0
            result = cm.paste(**paste_kwargs)
        return result, dispatch

    def test_text_field_focused_paste_proceeds(self):
        cm = make_clipboard_manager()
        with patch.object(clip_mod, "_is_text_field_focused", return_value=True):
            result, dispatch = self._run_paste(cm)
        assert result is True
        dispatch.assert_called_once()

    def test_no_text_field_skips_keystroke(self):
        cm = make_clipboard_manager()
        with (
            patch.object(clip_mod, "_is_text_field_focused", return_value=False),
            patch.object(clip_mod, "log") as mock_log,
            patch("voice_typer.server.event_bus.publish") as publish,
        ):
            result, dispatch = self._run_paste(cm)
        assert result is False
        dispatch.assert_not_called()
        assert any(
            "Paste skipped, no text field focused" in str(c) for c in mock_log.info.call_args_list
        )
        publish.assert_called_once()
        assert publish.call_args.args[0]["type"] == "paste_deferred"
        assert publish.call_args.args[0]["data"] == {"reason": "no_text_field"}

    def test_detection_exception_fails_open(self):
        cm = make_clipboard_manager()
        with (
            patch.object(clip_mod, "_is_text_field_focused", side_effect=RuntimeError("boom")),
            patch.object(clip_mod, "log"),
        ):
            result, dispatch = self._run_paste(cm)
        assert result is True
        dispatch.assert_called_once()

    def test_force_bypasses_text_field_gate(self):
        cm = make_clipboard_manager()
        with patch.object(clip_mod, "_is_text_field_focused", return_value=False) as gate:
            result, dispatch = self._run_paste(cm, force=True)
        assert result is True
        dispatch.assert_called_once()
        gate.assert_not_called()

    def test_terminal_bypasses_text_field_gate(self):
        cm = make_clipboard_manager()
        with patch.object(clip_mod, "_is_text_field_focused", return_value=False) as gate:
            result, dispatch = self._run_paste(cm, is_terminal=True)
        assert result is True
        dispatch.assert_called_once()
        gate.assert_not_called()

    def test_password_still_blocks_paste(self):
        """Regression: the text gate must not weaken password fail-closed."""
        cm = make_clipboard_manager()
        with (
            patch.object(clip_mod, "_Controller", object()),
            patch.object(clip_mod, "is_windows", return_value=False),
            patch.object(clip_mod, "is_macos", return_value=True),
            patch.object(clip_mod, "is_linux", return_value=False),
            patch.object(clip_mod, "_is_password_field_macos", return_value=True),
            patch.object(cm, "_register_pending_restore", return_value=None),
            patch.object(cm, "_dispatch_keystroke") as dispatch,
            patch.object(clip_mod, "time") as mock_time,
        ):
            mock_time.monotonic.return_value = 100.0
            assert cm._is_safe_paste_target() is False
            result = cm.paste()
        assert result is False
        dispatch.assert_not_called()

    def test_check_text_field_focus_direct_contract(self):
        cm = make_clipboard_manager()
        with patch.object(clip_mod, "_is_text_field_focused", return_value=True):
            assert cm._check_text_field_focus() == (True, None)
        with (
            patch.object(clip_mod, "_is_text_field_focused", return_value=False),
            patch.object(clip_mod, "log"),
            patch("voice_typer.server.event_bus.publish"),
        ):
            ok, reason = cm._check_text_field_focus()
        assert ok is False
        assert "no text field focused" in reason


class TestPasswordFailClosedUnchanged:
    """The new gate sits AFTER password checks; those contracts stay."""

    def test_macos_password_check_still_fails_closed_without_pyobjc(self):
        import builtins

        from voice_typer.server.clipboard_target_safety import validation

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name in ("AppKit", "ApplicationServices"):
                raise ImportError("pyobjc missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import), patch.object(clip_mod, "log"):
            assert validation._is_password_field_macos() is True

    def test_linux_password_check_still_fails_closed_without_pyatspi(self):
        import builtins

        from voice_typer.server.clipboard_target_safety import validation

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name == "pyatspi":
                raise ImportError("pyatspi missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import), patch.object(clip_mod, "log"):
            assert validation._is_password_field_linux() is True


class TestPasteMixinGatePlacement:
    def test_gate_runs_after_terminal_detection(self):
        """force/terminal bypass depends on is_terminal being known first."""
        src = inspect.getsource(PasteMixin._attempt_paste_dispatch)
        assert src.index("_is_terminal_process") < src.index("_check_text_field_focus")
        assert "not force and not is_terminal" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
