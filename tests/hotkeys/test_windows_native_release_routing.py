"""Windows fallback routing: release-aware hotkeys must never use WM_HOTKEY."""

from __future__ import annotations

import ctypes
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def mock_win32(monkeypatch):
    mock_user32 = MagicMock()
    mock_kernel32 = MagicMock()
    mock_winmm = MagicMock()
    mock_user32.RegisterHotKey.return_value = 1
    mock_user32.UnregisterHotKey.return_value = 1
    mock_user32.PostThreadMessageW.return_value = 1
    mock_user32.GetAsyncKeyState.return_value = 0
    mock_user32.SetWindowsHookExW.return_value = 0xDEADBEEF
    mock_user32.UnhookWindowsHookEx.return_value = 1
    mock_user32.CallNextHookEx.return_value = 0
    mock_user32.GetMessageW.return_value = 0
    mock_user32.TranslateMessage.return_value = 0
    mock_user32.DispatchMessageW.return_value = 0
    mock_kernel32.GetLastError.return_value = 0
    mock_kernel32.Sleep = MagicMock()
    mock_windll = MagicMock()
    mock_windll.user32 = mock_user32
    mock_windll.kernel32 = mock_kernel32
    mock_windll.winmm = mock_winmm
    monkeypatch.setattr(ctypes, "windll", mock_windll, raising=False)
    return mock_user32


def _route(mock_win32, *, hotkey="<f2>", ptt=False, toggle_on_keyup=False, prefer_message_loop=False, hook_ok=True):
    from voice_typer.server.hotkeys import WindowsNativeHotkey

    if not hook_ok:
        mock_win32.SetWindowsHookExW.return_value = 0
    backend = WindowsNativeHotkey(hotkey)
    backend._prefer_message_loop_first = prefer_message_loop
    if ptt:
        backend.set_on_release(lambda: None)
    if toggle_on_keyup:
        backend.set_toggle_on_keyup(True)

    calls: list[str] = []
    backend._install_low_level_hook = lambda _cb: calls.append("hook") or hook_ok
    backend._run_message_loop = lambda _cb, low_level_hook=False: calls.append(
        "hook-message-loop" if low_level_hook else "wm-hotkey"
    )
    backend._run_polling_loop = lambda _cb: calls.append("polling")

    try:
        backend.start(MagicMock())
        if backend._thread is not None:
            backend._thread.join(timeout=2.0)
    finally:
        backend.stop()
    return calls


def test_ptt_prefers_ll_hook(mock_win32):
    assert _route(mock_win32, ptt=True) == ["hook", "hook-message-loop"]


def test_ptt_without_hook_falls_to_polling_not_wm_hotkey(mock_win32):
    assert _route(mock_win32, ptt=True, hook_ok=False) == ["hook", "polling"]


def test_toggle_on_keyup_without_hook_falls_to_polling(mock_win32):
    assert _route(mock_win32, toggle_on_keyup=True, hook_ok=False) == ["hook", "polling"]


def test_press_only_toggle_still_allows_wm_hotkey(mock_win32):
    assert _route(mock_win32, hook_ok=False) == ["hook", "wm-hotkey"]


def test_prefer_message_loop_ignored_for_release_aware_hotkey(mock_win32):
    assert _route(mock_win32, ptt=True, prefer_message_loop=True) == ["hook", "hook-message-loop"]
