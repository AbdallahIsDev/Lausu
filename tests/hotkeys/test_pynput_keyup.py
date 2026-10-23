"""Pynput listener strategy: a release contract rules out GlobalHotKeys.

``GlobalHotKeys`` only reports presses. Toggle-on-release and push-to-talk
both need the manual ``Listener`` (which sees key-up), so the strategy is
chosen from the flags at start time and rebuilt when they change later.
"""

from __future__ import annotations

import sys
import types

import pytest

from tests.hotkeys.test_pynput_fallback_release import (
    _FakeKey,
    _FakeKeyCode,
    _FakeListener,
)


class _FakeGlobalHotKeys:
    """Records every construction so tests can assert it was NOT used."""

    instances: list[_FakeGlobalHotKeys] = []

    def __init__(self, mapping):
        self.mapping = mapping
        self.started = False
        type(self).instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def is_alive(self):
        return self.started


class _DeadListener(_FakeListener):
    def is_alive(self):
        return False


class _DeadGlobalHotKeys(_FakeGlobalHotKeys):
    def is_alive(self):
        return False


@pytest.fixture()
def fake_pynput(monkeypatch):
    """Install a fake ``pynput.keyboard`` module for ``_start_listener``."""
    module = types.ModuleType("pynput.keyboard")
    module.GlobalHotKeys = _FakeGlobalHotKeys
    module.Listener = _FakeListener
    module.Key = _FakeKey
    module.KeyCode = _FakeKeyCode
    package = types.ModuleType("pynput")
    package.keyboard = module
    monkeypatch.setitem(sys.modules, "pynput", package)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", module)
    _FakeGlobalHotKeys.instances = []
    return module


def _backend(hotkey: str, *, ptt: bool = False, toggle_on_keyup: bool = False):
    from voice_typer.server.hotkeys.pynput_backend import PynputHotkey

    backend = PynputHotkey(hotkey)
    if ptt:
        backend.set_on_release(lambda: None)
    if toggle_on_keyup:
        backend.set_toggle_on_keyup(True)
    return backend


def test_toggle_on_keyup_never_uses_global_hotkeys(fake_pynput):
    backend = _backend("<alt>", toggle_on_keyup=True)
    backend.start(lambda: None)

    assert _FakeGlobalHotKeys.instances == [], (
        "a release contract must use the manual Listener, GlobalHotKeys is press-only"
    )
    assert backend._fallback is True
    assert backend.is_alive() is True


def test_push_to_talk_never_uses_global_hotkeys(fake_pynput):
    backend = _backend("<ctrl>+k", ptt=True)
    backend.start(lambda: None)

    assert _FakeGlobalHotKeys.instances == []
    assert backend._fallback is True


def test_toggle_fires_on_release_only(fake_pynput):
    backend = _backend("<alt>", toggle_on_keyup=True)
    fired: list[str] = []
    backend.start(lambda: fired.append("fire"))

    backend._listener.on_press(_FakeKey.alt)
    assert fired == [], "a held modifier must not fire before its release"
    backend._listener.on_release(_FakeKey.alt)
    assert fired == ["fire"]


def test_push_to_talk_stops_on_release(fake_pynput):
    from voice_typer.server.hotkeys.pynput_backend import PynputHotkey

    fired: list[str] = []
    stopped: list[str] = []
    backend = PynputHotkey("<ctrl>+k")
    backend.set_on_release(lambda: stopped.append("stop"))
    backend.start(lambda: fired.append("start"))

    backend._listener.on_press(_FakeKey.ctrl)
    backend._listener.on_press(_FakeKeyCode.from_char("k"))
    assert fired == ["start"]
    assert stopped == []
    backend._listener.on_release(_FakeKeyCode.from_char("k"))
    assert stopped == ["stop"]


def test_toggle_chord_cancel_drops_the_arm_without_firing(fake_pynput):
    backend = _backend("<alt>", toggle_on_keyup=True)
    fired: list[str] = []
    backend.start(lambda: fired.append("fire"))

    backend._listener.on_press(_FakeKey.alt)
    backend._listener.on_press(_FakeKeyCode.from_char("q"))
    backend._listener.on_release(_FakeKeyCode.from_char("q"))
    backend._listener.on_release(_FakeKey.alt)

    assert fired == [], "Alt+Q is a shortcut, not a modifier tap"


def test_late_toggle_on_keyup_restarts_the_listener(fake_pynput):
    backend = _backend("<alt>")
    backend.start(lambda: None)
    assert _FakeGlobalHotKeys.instances, "the press-only path still uses GlobalHotKeys"
    press_only_listener = backend._listener

    backend.set_toggle_on_keyup(True)

    assert backend._listener is not press_only_listener
    assert backend._fallback is True
    assert backend.is_alive() is True


def test_setting_a_release_callback_late_restarts_the_listener(fake_pynput):
    backend = _backend("<alt>")
    backend.start(lambda: None)
    press_only_listener = backend._listener

    backend.set_on_release(lambda: None)

    assert backend._listener is not press_only_listener
    assert backend._fallback is True


def test_dead_listener_raises_instead_of_reporting_success(fake_pynput):
    fake_pynput.Listener = _DeadListener
    backend = _backend("<alt>", toggle_on_keyup=True)

    with pytest.raises(RuntimeError, match="not alive"):
        backend.start(lambda: None)


def test_dead_global_hotkeys_and_dead_fallback_raise(fake_pynput):
    fake_pynput.GlobalHotKeys = _DeadGlobalHotKeys
    fake_pynput.Listener = _DeadListener
    backend = _backend("<alt>")

    with pytest.raises(RuntimeError, match="not alive"):
        backend.start(lambda: None)
