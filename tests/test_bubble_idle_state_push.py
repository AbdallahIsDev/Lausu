"""Bubble shows idle UI when not recording, recording UI only while recording."""

from __future__ import annotations

import contextlib
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from voice_typer.server import event_bus, sidecar_ws  # noqa: E402
from voice_typer.server.ipc_server import IPCServer  # noqa: E402
from voice_typer.server.waveform import WaveformBubble  # noqa: E402

from tests.fixtures.ipc_test_helpers import make_fake_app, make_fake_service  # noqa: E402


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_recording_start_pushes_recording_state() -> None:
    src = (_repo_root() / "voice_typer" / "server" / "recording_lifecycle.py").read_text()
    show_idx = src.find("app._waveform_bubble.show()")
    assert show_idx != -1
    tail = src[show_idx : show_idx + 500]
    assert 'set_state("recording")' in tail


def test_startup_always_visible_pushes_idle() -> None:
    src = (
        _repo_root() / "voice_typer" / "server" / "startup_sequence" / "_phases_late.py"
    ).read_text()
    show_idx = src.find("app._waveform_bubble.show()")
    assert show_idx != -1
    tail = src[show_idx : show_idx + 500]
    assert 'set_state("idle")' in tail


def _behavior_ctx(app: MagicMock, behavior: str = "always_visible") -> MagicMock:
    from voice_typer.server.config_applier import SideEffectContext, SideEffectStatus

    return SideEffectContext(
        app=app,
        config=MagicMock(),
        updates={"bubble_behavior": behavior},
        status=SideEffectStatus(),
    )


def test_behavior_switch_to_always_visible_pushes_idle_when_not_recording() -> None:
    from voice_typer.server.config_applier import _BubbleBehaviorHandler

    bubble = MagicMock()
    recorder = MagicMock()
    recorder.recording = False
    app = MagicMock()
    app._waveform_bubble = bubble
    app.recorder = recorder
    _BubbleBehaviorHandler().apply(_behavior_ctx(app))
    bubble.show.assert_called_once()
    bubble.set_state.assert_called_once_with("idle")


def test_behavior_switch_to_always_visible_pushes_recording_when_recording() -> None:
    from voice_typer.server.config_applier import _BubbleBehaviorHandler

    bubble = MagicMock()
    recorder = MagicMock()
    recorder.recording = True
    app = MagicMock()
    app._waveform_bubble = bubble
    app.recorder = recorder
    _BubbleBehaviorHandler().apply(_behavior_ctx(app))
    bubble.show.assert_called_once()
    bubble.set_state.assert_called_once_with("recording")


def test_behavior_switch_to_hidden_hides_visible_bubble() -> None:
    from voice_typer.server.config_applier import _BubbleBehaviorHandler

    bubble = MagicMock()
    bubble.visible = True
    app = MagicMock()
    app._waveform_bubble = bubble
    _BubbleBehaviorHandler().apply(_behavior_ctx(app, "hidden"))
    bubble.hide.assert_called_once()
    bubble.show.assert_not_called()
    bubble.set_state.assert_not_called()


def test_recording_start_skips_bubble_when_hidden() -> None:
    src = (_repo_root() / "voice_typer" / "server" / "recording_lifecycle.py").read_text()
    gate_idx = src.find('bubble_behavior", "show_on_record") != "hidden"')
    assert gate_idx != -1, "recording start must gate bubble show on hidden behavior"
    tail = src[gate_idx : gate_idx + 400]
    assert "app._waveform_bubble.show()" in tail
    assert 'set_state("recording")' in tail


def test_bubble_config_push_carries_timer_flag() -> None:
    src = (_repo_root() / "voice_typer" / "server" / "waveform_bubble_wiring.py").read_text()
    assert '"bubble_show_recording_timer"' in src


def _ready_show_server(
    *,
    behavior: str = "always_visible",
    show_on_startup: bool = True,
    wired: bool = True,
) -> SimpleNamespace:
    """Fake WS server whose app carries a real bubble coordinator."""
    bubble = WaveformBubble()
    fired: list = []
    if wired:
        bubble.on_show = lambda: fired.append("show")
        bubble.on_set_state = lambda state: fired.append(("state", state))
        bubble.on_config = lambda cfg: fired.append(("config", cfg))
    config = SimpleNamespace(
        bubble_behavior=behavior,
        bubble_show_on_startup=show_on_startup,
    )
    app = SimpleNamespace(config=config, _waveform_bubble=bubble)
    server = SimpleNamespace(_lock=threading.RLock(), app=app)
    server.fired = fired  # type: ignore[attr-defined]
    server.bubble = bubble  # type: ignore[attr-defined]
    return server


def test_backend_ready_show_fires_once_for_always_visible() -> None:
    from voice_typer.server.sidecar_ws_internals import connection as conn

    server = _ready_show_server()
    assert conn._emit_bubble_startup_show(server) is True
    # Config BEFORE show: the host places the hidden pill from this
    # frame, so the first paint is the configured edge.
    assert server.fired[0][0] == "config"  # type: ignore[attr-defined]
    assert server.fired[1] == "show"  # type: ignore[attr-defined]
    assert server.fired[2] == ("state", "idle")  # type: ignore[attr-defined]
    assert server.bubble.visible is True  # type: ignore[attr-defined]
    assert server.bubble.state == "idle"  # type: ignore[attr-defined]
    # Second call (reconnect) never re-fires: no state clobber.
    assert conn._emit_bubble_startup_show(server) is False
    assert len(server.fired) == 3  # type: ignore[attr-defined]


def test_backend_ready_show_skipped_unless_always_visible() -> None:
    from voice_typer.server.sidecar_ws_internals import connection as conn

    for behavior, show_on_startup in [
        ("hidden", True),
        ("show_on_record", True),
        ("always_visible", False),
    ]:
        server = _ready_show_server(behavior=behavior, show_on_startup=show_on_startup)
        assert conn._emit_bubble_startup_show(server) is False
        assert server.bubble.visible is False  # type: ignore[attr-defined]
        assert server.fired == []  # type: ignore[attr-defined]


def test_backend_ready_show_skipped_when_unwired_or_busy() -> None:
    from voice_typer.server.sidecar_ws_internals import connection as conn

    unwired = _ready_show_server(wired=False)
    assert conn._emit_bubble_startup_show(unwired) is False
    assert unwired.bubble.visible is False  # type: ignore[attr-defined]

    busy = _ready_show_server()
    busy.bubble.show()  # type: ignore[attr-defined]
    busy.bubble.set_state("recording")  # type: ignore[attr-defined]
    busy.fired.clear()  # type: ignore[attr-defined]
    assert conn._emit_bubble_startup_show(busy) is False
    assert busy.bubble.state == "recording"  # type: ignore[attr-defined]
    assert busy.fired == []  # type: ignore[attr-defined]


def test_phase_8_skips_show_when_already_visible(monkeypatch) -> None:
    """Backend-ready show makes phase 8 a config-only backstop, never a reset."""
    import time

    from voice_typer.server.startup_sequence import StartupSequence

    monkeypatch.delenv("VOICE_TYPER_RESTART", raising=False)
    bubble = WaveformBubble()
    pushed: list = []
    bubble.on_show = lambda: pushed.append("show")
    bubble.on_set_state = lambda state: pushed.append(("state", state))
    bubble.on_config = lambda cfg: pushed.append("config")
    bubble.show()
    pushed.clear()
    config = SimpleNamespace(
        bubble_x=None,
        bubble_y=None,
        bubble_behavior="always_visible",
        bubble_show_on_startup=True,
        model_size="tiny",
        save=MagicMock(),
    )
    app = MagicMock()
    app.config = config
    app._waveform_bubble = bubble
    app.models = SimpleNamespace(_model_load_thread=SimpleNamespace(is_alive=lambda: False))
    app._shutting_down = False
    seq = StartupSequence(app)
    seq._t0 = time.perf_counter()
    seq._phase_8_finalize_and_signal()
    assert pushed == ["config"]
    assert bubble.state == "idle"


def test_phase_8_shows_when_not_yet_visible(monkeypatch) -> None:
    """Phase 8 stays the backstop when the ready-time show skipped."""
    import time

    from voice_typer.server.startup_sequence import StartupSequence

    monkeypatch.delenv("VOICE_TYPER_RESTART", raising=False)
    bubble = WaveformBubble()
    pushed: list = []
    bubble.on_show = lambda: pushed.append("show")
    bubble.on_set_state = lambda state: pushed.append(("state", state))
    bubble.on_config = lambda cfg: pushed.append("config")
    config = SimpleNamespace(
        bubble_x=None,
        bubble_y=None,
        bubble_behavior="always_visible",
        bubble_show_on_startup=True,
        model_size="tiny",
        save=MagicMock(),
    )
    app = MagicMock()
    app.config = config
    app._waveform_bubble = bubble
    app.models = SimpleNamespace(_model_load_thread=SimpleNamespace(is_alive=lambda: False))
    app._shutting_down = False
    seq = StartupSequence(app)
    seq._t0 = time.perf_counter()
    seq._phase_8_finalize_and_signal()
    # Config first, then show: the host places from the config frame.
    assert pushed[0] == "config"
    assert pushed[1] == "show"
    assert pushed[2] == ("state", "idle")
    assert bubble.visible is True


@pytest.fixture
def isolated_event_bus_subscribers():
    original = set(event_bus._subscribers)
    event_bus._subscribers.clear()
    try:
        yield
    finally:
        event_bus._subscribers.clear()
        event_bus._subscribers.update(original)


@pytest.mark.asyncio
async def test_ws_bubble_show_follows_ready_on_first_auth(
    monkeypatch, isolated_event_bus_subscribers
) -> None:
    """Backend-ready trigger: `ready` stays first, bubble frames follow it."""
    pytest.importorskip("websockets")
    from tests.fixtures.sidecar_ws_test_helpers import (
        make_fake_websocket_parked_after_auth,
    )

    app = make_fake_app()
    app.config.bubble_behavior = "always_visible"
    app.config.bubble_show_on_startup = True
    bubble = WaveformBubble()
    bubble.on_show = lambda: event_bus.publish({"type": "bubble_show"})
    bubble.on_set_state = lambda state: event_bus.publish(
        {"type": "bubble_set_state", "data": {"state": state}}
    )
    bubble.on_config = lambda cfg: event_bus.publish(
        {"type": "bubble_config", "data": {"bubble_behavior": "always_visible"}}
    )
    app._waveform_bubble = bubble
    service = make_fake_service()
    server = IPCServer(app, service=service)
    server._running = True
    server.push = MagicMock()

    received: list = []
    original_install = sidecar_ws._install_subscriber

    def _spy_install(s, loop, outbound):
        push_to_ws = original_install(s, loop, outbound)
        event_bus.unsubscribe(push_to_ws)

        def _wrapped(event: dict) -> None:
            received.append(event)
            return push_to_ws(event)

        event_bus.subscribe(_wrapped)
        return _wrapped

    monkeypatch.setattr(sidecar_ws, "_install_subscriber", _spy_install)
    monkeypatch.setenv("VOICE_TYPER_IPC_TOKEN", "test-token")
    ws = make_fake_websocket_parked_after_auth("test-token", park_dispatch=False)

    dispatch = sidecar_ws._make_dispatch(server)
    with contextlib.suppress(Exception):
        await sidecar_ws._handle_connection(ws, server, dispatch)

    kinds = [e.get("type") for e in received]
    assert "ready" in kinds
    assert "bubble_show" in kinds
    assert kinds.index("ready") < kinds.index("bubble_show")
    assert kinds.index("bubble_show") < kinds.index("bubble_set_state")
    idle = [e for e in received if e.get("type") == "bubble_set_state"]
    assert idle and idle[0]["data"]["state"] == "idle"
    assert bubble.visible is True
