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
    ) -> None:
        self._vk = vk
        self._modifiers_pressed = lambda: modifiers_pressed
        self._on_release_callback: Callable[[], None] | None = (lambda: None) if ptt else None
        self._toggle_on_keyup = toggle_on_keyup
        self._is_caps_lock_hotkey = caps
        self._ll_armed = False
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


def test_caps_lock_push_to_talk_uses_press_release_edges() -> None:
    """Caps Lock PTT is a Windows/Linux-valid trigger (D11).

    Press starts the recording and the release stops it; the toggle
    callback must not fire on either edge.
    """
    backend = _FakeBackend(vk=0x14, ptt=True, caps=True)
    callback = _callback(backend)

    assert handle_ll_key_event(backend, _WM_KEYDOWN, 0x14, callback) is True
    assert backend.fired == ["press"]
    # Autorepeat while held must not start a second recording.
    assert handle_ll_key_event(backend, _WM_KEYDOWN, 0x14, callback) is True
    assert backend.fired == ["press"]

    assert handle_ll_key_event(backend, _WM_KEYUP, 0x14, callback) is True
    assert backend.fired == ["press", "release"]


class TestNoModifierChordBranch:
    """The LL hook owns main-key/caps chords only.

    Modifier-only specs are routed to the modifier-only polling loop by
    ``WindowsNativeHotkey.start()`` because the hook cannot cancel a chord
    (Alt+Tab / Ctrl+C would fire the hotkey).
    """

    def test_modifier_key_events_are_ignored(self) -> None:
        backend = _FakeBackend(vk=None, ptt=False, toggle_on_keyup=True)
        callback = _callback(backend)

        handle_ll_key_event(backend, _WM_KEYDOWN, 0x12, callback)
        handle_ll_key_event(backend, _WM_KEYUP, 0x12, callback)
        assert backend.fired == []
        assert backend._ll_armed is False
