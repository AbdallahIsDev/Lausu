"""Bubble shows idle UI when not recording, recording UI only while recording."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


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
