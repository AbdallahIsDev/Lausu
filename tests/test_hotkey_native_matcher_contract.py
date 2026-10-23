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


# ── modifier-only taps must never hijack a real shortcut ────────────


def test_alt_then_tab_never_fires_the_alt_toggle(linux_backend):
    """Holding <alt> to switch windows must not toggle dictation."""
    backend = linux_backend("<alt>")
    fired = []
    backend._callback = lambda: fired.append("toggle")
    backend.set_toggle_on_keyup(True)

    backend._handle_line("MOD_DOWN:Alt")
    backend._handle_line("KEY_DOWN:Tab")
    backend._handle_line("KEY_UP:Tab")
    backend._handle_line("MOD_UP:Alt")

    assert fired == []


def test_ctrl_then_c_never_fires_the_ctrl_toggle(linux_backend):
    backend = linux_backend("<ctrl>")
    fired = []
    backend._callback = lambda: fired.append("toggle")
    backend.set_toggle_on_keyup(True)

    backend._handle_line("MOD_DOWN:Ctrl")
    backend._handle_line("KEY_DOWN:C")
    backend._handle_line("KEY_UP:C")
    backend._handle_line("MOD_UP:Ctrl")

    assert fired == []


def test_ctrl_alt_then_altgr_e_never_fires_the_chord_toggle(linux_backend):
    """AltGr+E is a plain character on many layouts, not a hotkey tap."""
    backend = linux_backend("<ctrl>+<alt>")
    fired = []
    backend._callback = lambda: fired.append("toggle")
    backend.set_toggle_on_keyup(True)

    backend._handle_line("MOD_DOWN:Ctrl")
    backend._handle_line("MOD_DOWN:Alt")
    backend._handle_line("KEY_DOWN:E")
    backend._handle_line("KEY_UP:E")
    backend._handle_line("MOD_UP:Alt")
    backend._handle_line("MOD_UP:Ctrl")

    assert fired == []


def test_clean_modifier_tap_fires_exactly_once(linux_backend):
    backend = linux_backend("<alt>")
    fired = []
    backend._callback = lambda: fired.append("toggle")
    backend.set_toggle_on_keyup(True)

    backend._handle_line("MOD_DOWN:Alt")
    backend._handle_line("MOD_UP:Alt")

    assert fired == ["toggle"]


def test_cross_role_chord_cancel_does_not_skip_the_other_role(linux_backend):
    """Dictation <ctrl>+<alt> must not fire when repaste <ctrl>+<alt>+r does.

    The chord-cancel runs BEFORE the matcher loop, so the earlier
    (dictation) role's early return cannot leave its toggle arm armed.
    """
    backend = linux_backend("<ctrl>+<alt>")
    backend.set_toggle_on_keyup(True)
    dictation: list[str] = []
    repaste: list[str] = []
    backend._callback = lambda: dictation.append("toggle")
    backend.add_extra_matcher("repaste", "<ctrl>+<alt>+r")
    backend.set_role_callback("repaste", lambda: repaste.append("repaste"))
    backend.set_role_toggle_on_keyup("repaste", True)

    backend._handle_line("MOD_DOWN:Ctrl")
    backend._handle_line("MOD_DOWN:Alt")
    assert repaste == []
    backend._handle_line("KEY_DOWN:R")
    backend._handle_line("KEY_UP:R")
    assert repaste == ["repaste"]
    backend._handle_line("MOD_UP:Alt")
    backend._handle_line("MOD_UP:Ctrl")

    assert dictation == [], f"dictation must never fire, got {dictation}"
    assert repaste == ["repaste"], f"repaste must fire exactly once, got {repaste}"
