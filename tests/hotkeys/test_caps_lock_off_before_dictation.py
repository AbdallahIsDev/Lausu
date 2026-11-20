"""Caps Lock is forced OFF before a dictation starts.

Caps Lock doubles as the dictation hotkey on Windows, so its OS toggle is
unreachable by hand once the native listener swallows the physical key. A
leftover ON state capitalizes everything the user types around a dictation
(and the transcript itself is pasted in CAPS by some apps), so every dictation
start clears it first -- through the same seam for the local model and for an
internal plugin, because both presses reach ``_dictation_callback``.
"""

from __future__ import annotations

import ctypes
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from voice_typer.server import hotkeys as hotkeys_pkg
from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher
from voice_typer.server.hotkeys.windows import caps_lock_suppressor
from voice_typer.server.keyboard_ownership import keyboard_ownership

_REPO_ROOT = Path(__file__).resolve().parents[2]
_C_SOURCE = _REPO_ROOT / "voice_typer" / "server" / "native" / "windows-key-listener.c"


def _make_app(*, hotkey: str = "<caps_lock>", recording_mode: str = "toggle") -> SimpleNamespace:
    app = SimpleNamespace()
    app.config = SimpleNamespace(
        hotkey=hotkey,
        recording_mode=recording_mode,
        esc_cancel_enabled=False,
        repaste_hotkey=None,
    )
    app.tray = MagicMock()
    app.toggle_dictation = MagicMock()
    app._stop_dictation = MagicMock()
    app._cancel_dictation = MagicMock()
    app.repaste_last = MagicMock()
    app._esc_cancel_paused = False
    app._shutting_down = False
    return app


@pytest.fixture(autouse=True)
def _reset_keyboard_ownership():
    keyboard_ownership().reset()
    yield
    keyboard_ownership().reset()


@pytest.fixture()
def clear_caps(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Fake the toggle itself + a Windows platform + a user32 handle."""
    fake = MagicMock(name="force_caps_lock_off")
    monkeypatch.setattr(caps_lock_suppressor, "force_caps_lock_off", fake)
    monkeypatch.setattr(hotkeys_pkg, "is_windows", lambda: True)
    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(user32=MagicMock(name="user32")),
        raising=False,
    )
    return fake


class TestForceCapsBeforeDictation:
    def test_caps_hotkey_clears_a_leftover_on_state(self, clear_caps):
        app = _make_app(hotkey="<caps_lock>")
        HotkeyDispatcher(app)._force_caps_lock_off_before_dictation()

        clear_caps.assert_called_once()
        assert clear_caps.call_args.args[0] is ctypes.windll.user32

    def test_other_hotkey_leaves_caps_alone(self, clear_caps):
        app = _make_app(hotkey="<f2>")
        HotkeyDispatcher(app)._force_caps_lock_off_before_dictation()

        clear_caps.assert_not_called()

    def test_non_windows_platform_is_skipped(self, clear_caps, monkeypatch):
        monkeypatch.setattr(hotkeys_pkg, "is_windows", lambda: False)
        app = _make_app(hotkey="<caps_lock>")
        HotkeyDispatcher(app)._force_caps_lock_off_before_dictation()

        clear_caps.assert_not_called()

    def test_caps_clear_is_non_fatal(self, monkeypatch):
        def _boom(_user32):
            raise RuntimeError("SendInput unavailable")

        monkeypatch.setattr(caps_lock_suppressor, "force_caps_lock_off", _boom)
        monkeypatch.setattr(hotkeys_pkg, "is_windows", lambda: True)
        monkeypatch.setattr(
            ctypes,
            "windll",
            SimpleNamespace(user32=MagicMock(name="user32")),
            raising=False,
        )
        app = _make_app(hotkey="<caps_lock>")
        HotkeyDispatcher(app)._force_caps_lock_off_before_dictation()  # must not raise


class TestDictationCallbackOrder:
    def test_caps_cleared_before_toggle_dictation(self, clear_caps):
        app = _make_app(hotkey="<caps_lock>")
        order: list[str] = []
        clear_caps.side_effect = lambda _user32: order.append("caps")
        app.toggle_dictation.side_effect = lambda: order.append("toggle")

        HotkeyDispatcher(app)._make_dictation_callback()()

        assert order == ["caps", "toggle"]

    def test_caps_cleared_for_plugin_dictation_too(self, clear_caps):
        """A plugin press goes through the same dispatcher seam."""
        app = _make_app(hotkey="<caps_lock>")
        app.toggle_dictation = MagicMock()

        HotkeyDispatcher(app)._make_dictation_callback()()

        clear_caps.assert_called_once()
        app.toggle_dictation.assert_called_once()

    def test_capture_active_skips_both_caps_and_dictation(self, clear_caps):
        app = _make_app(hotkey="<caps_lock>")
        keyboard_ownership().set_owner("hotkey_capture", reason="test")

        HotkeyDispatcher(app)._make_dictation_callback()()

        clear_caps.assert_not_called()
        app.toggle_dictation.assert_not_called()


class TestNativeListenerIgnoresInjectedInput:
    """The synthetic Caps Lock toggle must reach the OS through our own hook.

    ``force_caps_lock_off`` injects Caps Lock keydown/keyup. If the native
    listener swallowed that synthetic event the toggle would never land (caps
    stuck ON) or fire a second dictation (it emits wire events before the
    suppression decision). ``LLKHF_INJECTED`` is the only signal that
    separates an injected event from a physical one.
    """

    def test_hook_bypasses_injected_events_before_any_emit(self):
        source = _C_SOURCE.read_text(encoding="utf-8")
        proc_start = source.index("static LRESULT CALLBACK LowLevelKeyboardProc")
        proc_end = source.index("static BOOL WINAPI console_handler")
        proc = source[proc_start:proc_end]

        guard = "if (flags & LLKHF_INJECTED)"
        assert guard in proc
        guard_at = proc.index(guard)
        assert "CallNextHookEx" in proc[guard_at:]
        # No wire event may be emitted for injected input: every emit call in
        # the hook proc must come AFTER the injected-event bypass.
        first_emit = proc.index("emit(")
        assert first_emit > guard_at

    def test_bypass_returns_to_hook_chain(self):
        source = _C_SOURCE.read_text(encoding="utf-8")
        proc_start = source.index("static LRESULT CALLBACK LowLevelKeyboardProc")
        proc = source[proc_start:]
        guard_at = proc.index("if (flags & LLKHF_INJECTED)")
        guarded = proc[guard_at : guard_at + 200]
        assert "return CallNextHookEx(NULL, nCode, wParam, lParam);" in guarded
