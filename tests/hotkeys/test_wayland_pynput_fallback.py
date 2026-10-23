"""Wayland fallback must carry the release contract to its pynput child.

The Wayland backend delegates to ``PynputHotkey`` whenever the socket path
is unavailable or the bind fails. Without forwarding the flags the child
would silently register a press-only GlobalHotKeys listener, and without
aliveness both paths could be dead while the dispatcher reports success.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _wayland(monkeypatch, *, socket_path: str | None = None):
    from voice_typer.server.hotkeys.wayland import WaylandHotkey

    backend = WaylandHotkey("<alt>", role="dictation")
    monkeypatch.setattr(backend, "_socket_path", staticmethod(lambda role=None: socket_path))
    return backend


@pytest.fixture()
def fake_pynput(monkeypatch):
    created: list[MagicMock] = []

    def _factory(_hotkey: str):
        instance = MagicMock()
        instance.is_alive.return_value = True
        created.append(instance)
        return instance

    monkeypatch.setattr(
        "voice_typer.server.hotkeys.wayland.PynputHotkey",
        _factory,
    )
    return created


def test_fallback_receives_the_release_contract_before_start(monkeypatch, fake_pynput):
    backend = _wayland(monkeypatch, socket_path=None)
    backend.set_on_release(lambda: None)
    backend.set_toggle_on_keyup(True)

    backend.start(lambda: None)

    assert len(fake_pynput) == 1
    child = fake_pynput[0]
    calls = [name for name, _args, _kwargs in child.mock_calls]
    assert "set_on_release" in calls
    assert "set_toggle_on_keyup" in calls
    assert calls.index("set_on_release") < calls.index("start")
    assert calls.index("set_toggle_on_keyup") < calls.index("start")


def test_start_raises_when_neither_socket_nor_pynput_is_alive(monkeypatch, fake_pynput):
    backend = _wayland(monkeypatch, socket_path=None)
    backend._start_pynput_fallback = lambda: None  # simulate a silent pynput failure

    with pytest.raises(RuntimeError, match="neither a socket nor a pynput listener"):
        backend.start(lambda: None)


def test_socket_failure_raises_when_pynput_is_dead_too(monkeypatch, fake_pynput):
    backend = _wayland(monkeypatch, socket_path="/tmp/lausu-test.sock")

    def _broken_socket():
        raise OSError("bind failed")

    backend._start_socket_server = _broken_socket
    backend._start_pynput_fallback = lambda: None

    with pytest.raises(RuntimeError, match="socket error"):
        backend.start(lambda: None)


def test_is_alive_reports_the_pynput_fallback(monkeypatch, fake_pynput):
    backend = _wayland(monkeypatch, socket_path=None)
    backend.start(lambda: None)

    assert backend.is_alive() is True
