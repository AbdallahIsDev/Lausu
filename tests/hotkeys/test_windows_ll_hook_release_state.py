"""LL-hook state machine: release order, autorepeat, and single fire."""

from __future__ import annotations

from collections.abc import Callable

from voice_typer.server.hotkeys.win32_vk import (
    _WM_KEYDOWN,
    _WM_KEYUP,
    _WM_SYSKEYDOWN,
    _WM_SYSKEYUP,
)
from voice_typer.server.hotkeys.windows.ll_hook_strategy import handle_ll_key_event


class _FakeBackend:
    def __init__(
        self,
        *,
        vk: int | None = 0x56,
        modifiers_pressed: bool = True,
        ptt: bool = True,
        toggle_on_keyup: bool = False,
        caps: bool = False,
        modifier_vks: list[int] | None = None,
    ) -> None:
        self._vk = vk
        self._modifiers_pressed = lambda: modifiers_pressed
        self._on_release_callback: Callable[[], None] | None = (lambda: None) if ptt else None
        self._toggle_on_keyup = toggle_on_keyup
        self._is_caps_lock_hotkey = caps
        self._modifier_vks_for_hook = modifier_vks or []
        self._ll_armed = False
        self._ll_held_modifiers: set[int] = set()
        self.hotkey_str = "<ctrl>+<alt>+v"
        self.fired: list[str] = []

    def _enqueue_hook_callback(self, fn: Callable[[], None] | None) -> None:
        if fn is None:
            return
        self.fired.append("release" if fn is self._on_release_callback else "press")


def _callback(backend: _FakeBackend) -> Callable[[], None]:
    return lambda: backend.fired.append("press")


def test_ptt_release_after_modifiers_let_go_fires_once() -> None:
    backend = _FakeBackend(ptt=True)
    callback = _callback(backend)

    handle_ll_key_event(backend, _WM_KEYDOWN, 0x56, callback)
    assert backend.fired == ["press"]

    handle_ll_key_event(backend, _WM_KEYDOWN, 0x56, callback)
    assert backend.fired == ["press"]

    backend._modifiers_pressed = lambda: False
    handle_ll_key_event(backend, _WM_KEYUP, 0x56, callback)
    assert backend.fired == ["press", "release"]

    handle_ll_key_event(backend, _WM_KEYUP, 0x56, callback)
    assert backend.fired == ["press", "release"]


def test_ptt_keydown_without_modifiers_does_not_arm() -> None:
    backend = _FakeBackend(ptt=True, modifiers_pressed=False)
    callback = _callback(backend)

    handle_ll_key_event(backend, _WM_KEYDOWN, 0x56, callback)
    handle_ll_key_event(backend, _WM_KEYUP, 0x56, callback)
    assert backend.fired == []


def test_toggle_on_keyup_release_order_does_not_matter() -> None:
    backend = _FakeBackend(ptt=False, toggle_on_keyup=True, modifiers_pressed=False)
    callback = _callback(backend)

    backend._modifiers_pressed = lambda: True
    handle_ll_key_event(backend, _WM_KEYDOWN, 0x56, callback)
    assert backend.fired == []

    backend._modifiers_pressed = lambda: False
    handle_ll_key_event(backend, _WM_KEYUP, 0x56, callback)
    assert backend.fired == ["press"]
    handle_ll_key_event(backend, _WM_KEYUP, 0x56, callback)
    assert backend.fired == ["press"]


def test_legacy_toggle_fires_on_press_and_rearms_after_release() -> None:
    backend = _FakeBackend(ptt=False, toggle_on_keyup=False)
    callback = _callback(backend)

    handle_ll_key_event(backend, _WM_KEYDOWN, 0x56, callback)
    handle_ll_key_event(backend, _WM_KEYDOWN, 0x56, callback)
    handle_ll_key_event(backend, _WM_KEYUP, 0x56, callback)
    assert backend.fired == ["press"]

    handle_ll_key_event(backend, _WM_SYSKEYDOWN, 0x56, callback)
    handle_ll_key_event(backend, _WM_SYSKEYUP, 0x56, callback)
    assert backend.fired == ["press", "press"]


def test_caps_lock_swallows_keydown_and_fires_once_on_keyup() -> None:
    backend = _FakeBackend(vk=0x14, ptt=False, toggle_on_keyup=True, caps=True)
    callback = _callback(backend)

    assert handle_ll_key_event(backend, _WM_KEYDOWN, 0x14, callback) is True
    assert handle_ll_key_event(backend, _WM_KEYDOWN, 0x14, callback) is True
    assert backend.fired == []
    assert handle_ll_key_event(backend, _WM_KEYUP, 0x14, callback) is True
    assert backend.fired == ["press"]
    assert handle_ll_key_event(backend, _WM_KEYUP, 0x14, callback) is False
    assert backend.fired == ["press"]


def test_modifier_chord_fires_once_on_release_ending_chord() -> None:
    backend = _FakeBackend(vk=None, ptt=False, toggle_on_keyup=True, modifier_vks=[0x11, 0x12])
    callback = _callback(backend)

    handle_ll_key_event(backend, _WM_KEYDOWN, 0x11, callback)
    handle_ll_key_event(backend, _WM_KEYDOWN, 0x12, callback)
    assert backend.fired == []

    handle_ll_key_event(backend, _WM_KEYUP, 0x11, callback)
    assert backend.fired == ["press"]
    handle_ll_key_event(backend, _WM_KEYUP, 0x12, callback)
    assert backend.fired == ["press"]

    handle_ll_key_event(backend, _WM_KEYDOWN, 0x11, callback)
    handle_ll_key_event(backend, _WM_KEYDOWN, 0x12, callback)
    handle_ll_key_event(backend, _WM_KEYUP, 0x12, callback)
    assert backend.fired == ["press", "press"]


def test_modifier_chord_ignores_unrelated_keys() -> None:
    backend = _FakeBackend(vk=None, ptt=False, toggle_on_keyup=True, modifier_vks=[0x11, 0x12])
    callback = _callback(backend)

    handle_ll_key_event(backend, _WM_KEYDOWN, 0x43, callback)
    handle_ll_key_event(backend, _WM_KEYUP, 0x43, callback)
    assert backend.fired == []
