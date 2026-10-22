"""Pynput fallback matcher: exact modifiers and PTT chord-cancel."""

from __future__ import annotations

import pytest


class _FakeKeyCode:
    def __init__(self, kind: str, value):
        self.kind = kind
        self.value = value

    def __eq__(self, other):
        return isinstance(other, _FakeKeyCode) and (self.kind, self.value) == (other.kind, other.value)

    def __hash__(self):
        return hash((self.kind, self.value))

    def __repr__(self):
        return f"_FakeKeyCode({self.kind!r}, {self.value!r})"

    @classmethod
    def from_char(cls, char):
        return cls("char", char)

    @classmethod
    def from_vk(cls, vk):
        return cls("vk", vk)


class _FakeKey:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"_FakeKey({self.name!r})"


for _name in (
    "ctrl",
    "ctrl_l",
    "ctrl_r",
    "shift",
    "shift_l",
    "shift_r",
    "alt",
    "alt_l",
    "alt_r",
    "alt_gr",
    "cmd",
    "cmd_l",
    "cmd_r",
    "fn",
):
    setattr(_FakeKey, _name, _FakeKey(_name))


class _FakeListener:
    def __init__(self, *, on_press, on_release):
        self.on_press = on_press
        self.on_release = on_release

    def start(self):
        pass

    def stop(self):
        pass

    def is_alive(self):
        return True


@pytest.fixture()
def handlers():
    from voice_typer.server.hotkeys.pynput_backend import PynputHotkey

    def _build(hotkey: str, *, ptt: bool = False, toggle_on_keyup: bool = False):
        backend = PynputHotkey(hotkey)
        fired: list[str] = []
        stopped: list[str] = []
        backend.set_on_release(lambda: stopped.append("stop")) if ptt else None
        if toggle_on_keyup:
            backend.set_toggle_on_keyup(True)
        backend._start_fallback(
            lambda: fired.append("fire"),
            _FakeListener,
            _FakeKey,
            _FakeKeyCode,
        )
        return backend, backend._listener, fired, stopped

    return _build


def test_ptt_combo_starts_on_press_and_stops_on_release(handlers):
    _, listener, fired, stopped = handlers("<ctrl>+k", ptt=True)
    listener.on_press(_FakeKey.ctrl)
    listener.on_press(_FakeKeyCode.from_char("k"))
    assert fired == ["fire"]
    assert stopped == []
    listener.on_release(_FakeKeyCode.from_char("k"))
    assert stopped == ["stop"]


def test_left_ctrl_variant_satisfies_ctrl_modifier(handlers):
    _, listener, fired, stopped = handlers("<ctrl>+k", ptt=True)
    listener.on_press(_FakeKey.ctrl_l)
    listener.on_press(_FakeKeyCode.from_char("k"))
    assert fired == ["fire"]
    listener.on_release(_FakeKeyCode.from_char("k"))
    assert stopped == ["stop"]


def test_extra_held_modifier_blocks_combo(handlers):
    _, listener, fired, _ = handlers("<ctrl>+k", ptt=True)
    listener.on_press(_FakeKey.ctrl)
    listener.on_press(_FakeKey.alt)
    listener.on_press(_FakeKeyCode.from_char("k"))
    assert fired == []


def test_chord_cancel_stops_ptt_once(handlers):
    _, listener, fired, stopped = handlers("<ctrl>+k", ptt=True)
    listener.on_press(_FakeKey.ctrl)
    listener.on_press(_FakeKeyCode.from_char("k"))
    assert fired == ["fire"]
    listener.on_press(_FakeKeyCode.from_char("x"))
    assert stopped == ["stop"]
    listener.on_release(_FakeKeyCode.from_char("k"))
    assert stopped == ["stop"]


def test_toggle_on_keyup_fires_only_on_release(handlers):
    _, listener, fired, _ = handlers("<alt>", toggle_on_keyup=True)
    listener.on_press(_FakeKey.alt)
    assert fired == []
    listener.on_release(_FakeKey.alt)
    assert fired == ["fire"]


def test_toggle_on_keyup_blocks_extra_modifier(handlers):
    _, listener, fired, _ = handlers("<alt>", toggle_on_keyup=True)
    listener.on_press(_FakeKey.ctrl)
    listener.on_press(_FakeKey.alt)
    listener.on_release(_FakeKey.alt)
    assert fired == []


def test_legacy_toggle_fires_on_press(handlers):
    _, listener, fired, _ = handlers("<alt>")
    listener.on_press(_FakeKey.alt)
    assert fired == ["fire"]
    listener.on_release(_FakeKey.alt)
    assert fired == ["fire"]
