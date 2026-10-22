from __future__ import annotations

import sys

import pytest


@pytest.fixture
def linux_backend(monkeypatch):
    from voice_typer.server import native_hotkeys
    from voice_typer.server.native_hotkeys import LinuxEvdevHotkey

    monkeypatch.setattr(native_hotkeys, "is_linux", lambda: True)
    monkeypatch.setattr(native_hotkeys, "is_macos", lambda: False)
    monkeypatch.setattr(native_hotkeys, "is_windows", lambda: False)
    monkeypatch.setattr(sys, "platform", "linux")
    return LinuxEvdevHotkey


def test_toggle_combo_fires_once_when_key_released_before_modifier(linux_backend):
    backend = linux_backend("<ctrl>+<alt>+v")
    fired = []
    backend._callback = lambda: fired.append("toggle")
    backend.set_toggle_on_keyup(True)

    backend._handle_line("MOD_DOWN:Ctrl")
    backend._handle_line("MOD_DOWN:Alt")
    backend._handle_line("KEY_DOWN:V")
    assert fired == []
    backend._handle_line("KEY_UP:V")
    assert fired == ["toggle"]
    backend._handle_line("MOD_UP:Alt")
    backend._handle_line("MOD_UP:Ctrl")
    assert fired == ["toggle"]


def test_toggle_combo_fires_once_when_modifier_released_before_key(linux_backend):
    backend = linux_backend("<ctrl>+<alt>+v")
    fired = []
    backend._callback = lambda: fired.append("toggle")
    backend.set_toggle_on_keyup(True)

    backend._handle_line("MOD_DOWN:Ctrl")
    backend._handle_line("MOD_DOWN:Alt")
    backend._handle_line("KEY_DOWN:V")
    backend._handle_line("MOD_UP:Alt")
    backend._handle_line("KEY_UP:V")
    assert fired == ["toggle"]
    backend._handle_line("MOD_UP:Ctrl")
    assert fired == ["toggle"]


def test_extra_modifier_blocks_combo_even_when_released_before_key(linux_backend):
    backend = linux_backend("<ctrl>+v")
    fired = []
    backend._callback = lambda: fired.append("toggle")
    backend.set_toggle_on_keyup(True)

    backend._handle_line("MOD_DOWN:Ctrl")
    backend._handle_line("MOD_DOWN:Shift")
    backend._handle_line("KEY_DOWN:V")
    backend._handle_line("MOD_UP:Shift")
    backend._handle_line("KEY_UP:V")
    assert fired == []


def test_typing_another_key_stops_armed_modifier_only_ptt(linux_backend):
    backend = linux_backend("<alt>")
    started = []
    stopped = []
    backend._callback = lambda: started.append("start")
    backend.set_on_release(lambda: stopped.append("stop"))

    backend._handle_line("MOD_DOWN:Alt")
    assert started == ["start"]
    backend._handle_line("KEY_DOWN:C")
    assert stopped == ["stop"]
    backend._handle_line("KEY_UP:C")
    backend._handle_line("MOD_UP:Alt")
    assert stopped == ["stop"]


def test_reset_match_state_drops_held_chord_before_respawn(linux_backend):
    backend = linux_backend("<ctrl>+v")
    fired = []
    backend._callback = lambda: fired.append("toggle")
    backend.set_toggle_on_keyup(True)

    backend._handle_line("MOD_DOWN:Ctrl")
    backend._handle_line("KEY_DOWN:V")
    backend._reset_match_state()
    backend._handle_line("KEY_UP:V")
    backend._handle_line("MOD_UP:Ctrl")
    assert fired == []
