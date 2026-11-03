"""TTS IPC wiring: the stop command, error codes, cache keys and status payload."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from voice_typer.server.handlers.tts_handlers import (
    TTS_ERR_GENERIC,
    TTS_ERR_NO_OUTPUT,
    TTS_ERR_NOT_INSTALLED,
    tts_error_code,
)
from voice_typer.server.ipc.rate_limiter import COMMAND_COSTS
from voice_typer.server.ipc.registry import _COMMAND_REGISTRY
from voice_typer.server.service.tts import TtsMixin
from voice_typer.server.tts import manager as manager_module
from voice_typer.server.tts.playback import PlaybackError
from voice_typer.server.tts.samples import SAMPLE_CACHE_VERSION, sample_key
from voice_typer.server.tts.types import TtsError


def test_tts_stop_is_registered_and_cheap() -> None:
    assert _COMMAND_REGISTRY["tts_stop"] == "_handle_tts_stop"
    assert COMMAND_COSTS["tts_stop"] == 1


def test_tts_speak_and_stop_are_in_the_rust_allowlist() -> None:
    repo = Path(__file__).resolve().parent.parent
    source = (repo / "src-tauri/src/commands/sidecar_cmds/allowlist.rs").read_text(encoding="utf-8")
    assert '"tts_stop"' in source
    assert '"tts_speak"' in source


def test_playback_state_event_is_registered_everywhere() -> None:
    from voice_typer.server import event_bus

    repo = Path(__file__).resolve().parent.parent
    rust = (repo / "src-tauri" / "src" / "sidecar" / "ws" / "event_protocol.rs").read_text(encoding="utf-8")
    ts = (repo / "voice_typer" / "client" / "src" / "renderer" / "src" / "types" / "ipc" / "push_events.ts").read_text(
        encoding="utf-8"
    )
    known = (
        repo / "voice_typer" / "client" / "src" / "renderer" / "src" / "lib" / "python-bridge" / "known-event-types.ts"
    ).read_text(encoding="utf-8")

    assert "tts_playback_state" in event_bus.EVENT_TYPES
    assert '"tts_playback_state"' in rust
    assert 'type: "tts_playback_state"' in ts
    assert '"tts_playback_state"' in known


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("magpie is not installed: no runtime", TTS_ERR_NOT_INSTALLED),
        ("tts is turned off; pick Audio8 or Magpie first", TTS_ERR_NOT_INSTALLED),
        ("could not play synthesized speech: PortAudio error opening device", TTS_ERR_NO_OUTPUT),
        ("magpie: HTTP 500 from /v1/audio/speech", TTS_ERR_GENERIC),
        ("response is not audio", TTS_ERR_GENERIC),
    ],
)
def test_error_codes_are_plain_language_codes(message: str, code: str) -> None:
    assert tts_error_code(TtsError(message)) == code


def test_playback_error_maps_without_leaking_text() -> None:
    assert tts_error_code(PlaybackError("unreadable audio at /tmp/x.wav")) == TTS_ERR_GENERIC
    assert tts_error_code(PlaybackError("no output device found")) == TTS_ERR_NO_OUTPUT
    for code in (TTS_ERR_GENERIC, TTS_ERR_NO_OUTPUT, TTS_ERR_NOT_INSTALLED):
        assert "/" not in code and " " not in code


def test_sample_cache_is_versioned_and_voice_specific() -> None:
    assert SAMPLE_CACHE_VERSION >= 3, "clips rendered with the old selector must be discarded"
    sofia = sample_key("magpie", "Sofia", "en-US")
    jason = sample_key("magpie", "Jason", "en-US")
    assert sofia != jason
    # The key carries the SPEAKER INDEX, never the display name: a clip stored
    # under the name was rendered through the runtime's scrambled name table.
    assert "-4-" in sofia
    assert "Sofia" not in sofia
    assert f"v{SAMPLE_CACHE_VERSION}" in sofia


def test_tts_service_stop_reports_the_playback_state() -> None:
    class _Manager:
        def __init__(self, stopped: bool) -> None:
            self.stopped = stopped

        def stop_playback(self) -> bool:
            return self.stopped

    mixin = object.__new__(TtsMixin)
    mixin._app = SimpleNamespace(config=SimpleNamespace())
    mixin._tts_manager = _Manager(True)

    assert mixin.tts_stop() == {"stopped": True}
    mixin._tts_manager = _Manager(False)
    assert mixin.tts_stop() == {"stopped": False}


def test_sample_cached_map_never_renders(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Config:
        tts_engine = "magpie"
        tts_voice = "Sofia"
        tts_language = "en-US"
        tts_enabled = True

    def fake_cache_path(engine: str, voice: str, language: str) -> Path:
        return tmp_path / f"{engine}-{voice}-{language}.wav"

    monkeypatch.setattr(manager_module, "sample_cache_path", fake_cache_path)
    monkeypatch.setattr(manager_module, "bundled_sample_path", lambda *_: None)
    fake_cache_path("magpie", "Sofia", "en-US").write_bytes(b"RIFF")

    manager = manager_module.TtsManager(config=_Config())
    status = manager.status()

    assert status["enabled"] is True
    assert status["language"] == "en-US"
    assert status["sample_cached"]["magpie"]["Sofia"]["en-US"] is True
    assert status["sample_cached"]["magpie"]["Jason"]["en-US"] is False


def test_prewarm_is_a_no_op_when_the_pack_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Config:
        tts_engine = "magpie"
        tts_voice = "Aria"
        tts_language = "en-US"
        tts_enabled = True

    manager = manager_module.TtsManager(config=_Config())
    monkeypatch.setattr(manager_module.TtsManager, "_installed", lambda self, engine: False)
    monkeypatch.setattr(
        manager_module.TtsManager,
        "_tts_service",
        lambda self: (_ for _ in ()).throw(AssertionError("must not start a runtime")),
    )

    assert manager.prewarm("magpie") is False
