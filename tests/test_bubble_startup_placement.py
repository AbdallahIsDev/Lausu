"""Bubble startup placement contract: config (edge) reaches the host first.

The Tauri host owns the pill's startup geometry: it places the (hidden)
window from ``bubble_config.bubble_position`` before showing it. These
tests pin the Python half of that contract — the payload carries the
edge, and every authenticated connection pushes it ahead of any show.
"""

from __future__ import annotations

import contextlib
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from voice_typer.server import event_bus, sidecar_ws
from voice_typer.server.waveform import WaveformBubble

from tests.fixtures.ipc_test_helpers import make_fake_app, make_fake_service


@pytest.fixture
def isolated_event_bus_subscribers():
    original = set(event_bus._subscribers)
    event_bus._subscribers.clear()
    try:
        yield
    finally:
        event_bus._subscribers.clear()
        event_bus._subscribers.update(original)


def _wire_real_bubble(app: MagicMock):
    from voice_typer.server.waveform_bubble_wiring import WaveformBubbleWiring

    bubble = WaveformBubble()
    app._waveform_bubble = bubble
    wirer = WaveformBubbleWiring(app)
    wirer._wire_waveform_bubble()
    return bubble, wirer


def test_bubble_config_payload_carries_configured_edge() -> None:
    """The host can only place from this key; it was missing entirely."""
    captured: dict = {}
    event_bus.subscribe(lambda msg: captured.setdefault(msg.get("type"), msg))
    app = MagicMock(name="app")
    bubble, wirer = _wire_real_bubble(app)
    try:
        cfg = SimpleNamespace(
            bubble_position="top",
            bubble_behavior="show_on_record",
            bubble_click_to_toggle=True,
            bubble_mic_button=True,
            bubble_show_recording_timer=False,
            screenshot_beta_enabled=False,
            screenshot_consent=None,
            theme_mode="system",
            theme_preset="default",
            custom_theme=None,
            text_size=14,
            bubble_x=None,
            bubble_y=None,
        )
        bubble.on_config(cfg)
        data = captured["bubble_config"]["data"]
        assert data["bubble_position"] == "top"
        # The rest of the subset is unchanged.
        assert data["bubble_behavior"] == "show_on_record"
        assert "bubble_x" in data
    finally:
        wirer.stop()


def test_bubble_config_payload_defaults_to_bottom_edge() -> None:
    captured: dict = {}
    event_bus.subscribe(lambda msg: captured.setdefault(msg.get("type"), msg))
    app = MagicMock(name="app")
    bubble, wirer = _wire_real_bubble(app)
    try:
        bubble.on_config(SimpleNamespace())
        assert captured["bubble_config"]["data"]["bubble_position"] == "bottom"
    finally:
        wirer.stop()


def _server_with_bubble(behavior: str = "always_visible") -> SimpleNamespace:
    bubble = WaveformBubble()
    fired: list = []
    bubble.on_config = lambda cfg: fired.append(("config", cfg))
    bubble.on_show = lambda: fired.append("show")
    bubble.on_set_state = lambda state: fired.append(("state", state))
    config = SimpleNamespace(
        bubble_behavior=behavior,
        bubble_show_on_startup=True,
        bubble_position="bottom",
    )
    app = SimpleNamespace(config=config, _waveform_bubble=bubble)
    return SimpleNamespace(_lock=threading.RLock(), app=app, fired=fired, bubble=bubble)


def test_connect_config_push_fires_without_the_startup_show() -> None:
    """show_on_record still needs the edge: the first show is a recording."""
    from voice_typer.server.sidecar_ws_internals import connection as conn

    server = _server_with_bubble("show_on_record")
    conn._emit_bubble_config_snapshot(server)
    assert [entry[0] for entry in server.fired] == ["config"]
    assert server.bubble.visible is False


def test_connect_config_push_is_safe_before_the_app_exists() -> None:
    from voice_typer.server.sidecar_ws_internals import connection as conn

    conn._emit_bubble_config_snapshot(SimpleNamespace(_lock=threading.RLock(), app=None))
    conn._emit_bubble_config_snapshot(
        SimpleNamespace(
            _lock=threading.RLock(),
            app=SimpleNamespace(config=None, _waveform_bubble=None),
        )
    )


@pytest.mark.asyncio
async def test_authenticated_connection_pushes_config_before_any_show(monkeypatch) -> None:
    """Ordering guard: config → startup show on the same connection."""
    pytest.importorskip("websockets")
    from voice_typer.server.ipc_server import IPCServer

    from tests.fixtures.sidecar_ws_test_helpers import (
        make_fake_websocket_parked_after_auth,
    )

    app = make_fake_app()
    server = IPCServer(app, service=make_fake_service())
    server._running = True
    server._ready_emitted = False

    call_log: list[str] = []
    monkeypatch.setattr(
        sidecar_ws,
        "_emit_ready_if_first",
        lambda s: call_log.append("ready"),
    )
    monkeypatch.setattr(
        sidecar_ws,
        "_emit_initial_state_snapshot",
        lambda s: call_log.append("state_snapshot"),
    )
    monkeypatch.setattr(
        sidecar_ws,
        "_emit_bubble_config_snapshot",
        lambda s: call_log.append("bubble_config"),
    )
    monkeypatch.setattr(
        sidecar_ws,
        "_emit_bubble_startup_show",
        lambda s: call_log.append("bubble_show"),
    )

    monkeypatch.setenv("VOICE_TYPER_IPC_TOKEN", "test-token")
    ws = make_fake_websocket_parked_after_auth("test-token", park_dispatch=False)
    dispatch = sidecar_ws._make_dispatch(server)
    with contextlib.suppress(Exception):
        await sidecar_ws._handle_connection(ws, server, dispatch)

    assert call_log.count("bubble_config") == 1, call_log
    assert call_log.index("bubble_config") < call_log.index("bubble_show"), call_log
    assert call_log.index("ready") < call_log.index("bubble_config"), call_log
