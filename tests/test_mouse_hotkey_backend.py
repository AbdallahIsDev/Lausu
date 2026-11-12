"""Tests for the middle-mouse-button hotkey backend."""

from __future__ import annotations

import pytest
from voice_typer.server.hotkeys import create_hotkey_backend, mouse_backend
from voice_typer.server.hotkeys.mouse_backend import MouseHotkey


class _FakeListener:
    def __init__(self, on_click, alive_after_start: bool = True):
        self._on_click = on_click
        self._alive_after_start = alive_after_start
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def is_alive(self) -> bool:
        if not self.started:
            return False
        return self._alive_after_start and not self.stopped

    def click(self, button: object = "middle", pressed: bool = True) -> None:
        self._on_click(0, 0, button, pressed)


class _FakeMouse:
    class Button:
        middle = "middle"

    def __init__(self, alive_after_start: bool = True):
        self._alive_after_start = alive_after_start
        self.listener: _FakeListener | None = None

    def Listener(self, on_click):  # noqa: N802 - pynput's name
        self.listener = _FakeListener(on_click, self._alive_after_start)
        return self.listener


@pytest.fixture
def fake_mouse(monkeypatch: pytest.MonkeyPatch) -> _FakeMouse:
    mouse = _FakeMouse()
    monkeypatch.setattr(mouse_backend, "_load_mouse", lambda: mouse)
    return mouse


def _started_backend(fake_mouse: _FakeMouse) -> tuple[MouseHotkey, list[str]]:
    backend = MouseHotkey("<mouse_middle>")
    fired: list[str] = []
    backend.start(lambda: fired.append("press"))
    assert fake_mouse.listener is not None
    return backend, fired


def test_middle_press_fires_callback(fake_mouse: _FakeMouse) -> None:
    backend, fired = _started_backend(fake_mouse)
    assert fake_mouse.listener is not None
    fake_mouse.listener.click(pressed=True)
    assert fired == ["press"]
    backend.stop()


def test_toggle_mode_fires_on_press_only(fake_mouse: _FakeMouse) -> None:
    backend, fired = _started_backend(fake_mouse)
    assert fake_mouse.listener is not None
    fake_mouse.listener.click(pressed=True)
    fake_mouse.listener.click(pressed=False)
    assert fired == ["press"]
    backend.stop()


def test_toggle_on_keyup_fires_on_release(fake_mouse: _FakeMouse) -> None:
    backend = MouseHotkey("<mouse_middle>")
    fired: list[str] = []
    backend.set_toggle_on_keyup(True)
    backend.start(lambda: fired.append("press"))
    assert fake_mouse.listener is not None
    fake_mouse.listener.click(pressed=True)
    assert fired == []
    fake_mouse.listener.click(pressed=False)
    assert fired == ["press"]
    backend.stop()


def test_push_to_talk_fires_press_and_release(fake_mouse: _FakeMouse) -> None:
    backend = MouseHotkey("<mouse_middle>")
    fired: list[str] = []
    backend.set_on_release(lambda: fired.append("release"))
    backend.start(lambda: fired.append("press"))
    assert fake_mouse.listener is not None
    fake_mouse.listener.click(pressed=True)
    fake_mouse.listener.click(pressed=False)
    assert fired == ["press", "release"]
    backend.stop()


def test_other_buttons_are_ignored(fake_mouse: _FakeMouse) -> None:
    backend, fired = _started_backend(fake_mouse)
    assert fake_mouse.listener is not None
    fake_mouse.listener.click(button="left", pressed=True)
    fake_mouse.listener.click(button="right", pressed=True)
    assert fired == []
    backend.stop()


def test_stop_releases_the_listener(fake_mouse: _FakeMouse) -> None:
    backend, _ = _started_backend(fake_mouse)
    backend.stop()
    assert fake_mouse.listener is not None
    assert fake_mouse.listener.stopped is True
    assert backend.is_alive() is False


def test_start_raises_when_listener_dies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mouse_backend, "_load_mouse", lambda: _FakeMouse(alive_after_start=False))
    with pytest.raises(RuntimeError, match="not alive"):
        MouseHotkey("<mouse_middle>").start(lambda: None)


def test_factory_routes_mouse_specs_to_the_mouse_backend() -> None:
    assert isinstance(create_hotkey_backend("<mouse_middle>"), MouseHotkey)
