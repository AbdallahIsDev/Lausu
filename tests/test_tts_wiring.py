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


def test_tts_delete_is_registered_in_both_allowlists_and_priced() -> None:
    assert _COMMAND_REGISTRY["tts_delete"] == "_handle_tts_delete"
    assert COMMAND_COSTS["tts_delete"] == 20
    repo = Path(__file__).resolve().parent.parent
    source = (repo / "src-tauri/src/commands/sidecar_cmds/allowlist.rs").read_text(encoding="utf-8")
    assert '"tts_delete"' in source


def test_tts_prepare_progress_event_is_registered_everywhere() -> None:
    from voice_typer.server import event_bus

    repo = Path(__file__).resolve().parent.parent
    rust = (repo / "src-tauri" / "src" / "sidecar" / "ws" / "event_protocol.rs").read_text(encoding="utf-8")
    ts = (repo / "voice_typer" / "client" / "src" / "renderer" / "src" / "types" / "ipc" / "push_events.ts").read_text(
        encoding="utf-8"
    )
    known = (
        repo / "voice_typer" / "client" / "src" / "renderer" / "src" / "lib" / "python-bridge" / "known-event-types.ts"
    ).read_text(encoding="utf-8")

    assert "tts_prepare_progress" in event_bus.EVENT_TYPES
    assert '"tts_prepare_progress"' in rust
    assert 'type: "tts_prepare_progress"' in ts
    assert '"tts_prepare_progress"' in known


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


def test_tts_delete_removes_only_the_named_engine_pack(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Config:
        tts_engine = "audio8"

    def fake_model_dir(engine: str) -> Path:
        return tmp_path / engine

    monkeypatch.setattr(manager_module, "model_dir", fake_model_dir)
    monkeypatch.setattr(manager_module.TtsManager, "_installed", lambda self, engine: True)
    stopped: list[str] = []
    monkeypatch.setattr(
        manager_module.TtsManager,
        "stop_playback",
        lambda self: stopped.append("audio8") or True,
    )
    audio8_dir = tmp_path / "audio8"
    audio8_dir.mkdir()
    (audio8_dir / "pack.gguf").write_bytes(b"GGUF")
    magpie_dir = tmp_path / "magpie"
    magpie_dir.mkdir()

    manager = manager_module.TtsManager(config=_Config())
    result = manager.delete("audio8")

    assert result == {
        "engine": "audio8",
        "deleted": True,
        "was_active": True,
        "models_dir": str(audio8_dir),
    }
    assert stopped == ["audio8"]
    assert not audio8_dir.exists()
    assert magpie_dir.exists()
    with pytest.raises(TtsError, match="unknown tts engine"):
        manager.delete("not-an-engine")


def test_tts_delete_service_clears_the_active_selection() -> None:
    applied: list[dict] = []
    deletion_result = {"engine": "audio8", "was_active": True}

    class _Manager:
        def delete(self, engine: str) -> dict:
            return deletion_result

    mixin = object.__new__(TtsMixin)
    mixin._app = SimpleNamespace(config=SimpleNamespace())
    mixin._tts_manager = _Manager()
    mixin.apply_config = lambda values: applied.append(values)  # type: ignore[method-assign]

    assert mixin.tts_delete("audio8") == deletion_result
    assert applied == [{"tts_engine": "off"}]


def test_prepare_progress_payload_is_throttled_and_finite(monkeypatch: pytest.MonkeyPatch) -> None:
    published: list[dict] = []

    def fake_publish(message: dict) -> bool:
        published.append(message)
        return True

    monkeypatch.setattr("voice_typer.server.event_bus.publish", fake_publish)
    manager = manager_module.TtsManager(config=SimpleNamespace(tts_engine="off"))
    for done in (1, 2, 3, 4, 5):
        manager._publish_prepare_progress("audio8", "pack.gguf", 1, 1, done, 10)
    manager._publish_prepare_progress("audio8", "pack.gguf", 1, 1, 10, 10)

    assert len(published) >= 2
    assert published[0]["type"] == "tts_prepare_progress"
    assert published[0]["data"]["bytes_total"] == 10
    assert published[-1]["data"]["percent"] == 100


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
