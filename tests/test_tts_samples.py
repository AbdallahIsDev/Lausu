"""Voice samples are rendered once and reused (bundled -> cache -> render)."""

from __future__ import annotations

from pathlib import Path

import pytest
from voice_typer.server.tts import manager as manager_module
from voice_typer.server.tts.manager import TtsManager
from voice_typer.server.tts.samples import sample_cache_path, sample_key
from voice_typer.server.tts.types import TtsError


class _Config:
    def __init__(self, engine: str = "magpie", voice: str = "Aria") -> None:
        self.tts_engine = engine
        self.tts_voice = voice
        self.tts_language = "en-US"
        self.tts_enabled = True


class _FakeService:
    """Writes a tiny WAV and records how many renders happened."""

    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, request, engine: str, output: Path) -> object:
        self.calls += 1
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"RIFF-fake-wav")
        return type("Result", (), {"wav_path": output})()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _FakeService:
    """Point the cache at tmp, never the real HF folder."""
    service = _FakeService()

    def cache_path(engine: str, voice: str, language: str) -> Path:
        return tmp_path / f"{sample_key(engine, voice, language)}.wav"

    monkeypatch.setattr(manager_module, "sample_cache_path", cache_path)
    monkeypatch.setattr(manager_module, "bundled_sample_path", lambda *_: None)
    monkeypatch.setattr(manager_module, "play_wav", lambda *_: 0.5)
    # Playback is asynchronous: Test starts the clip and returns immediately.
    monkeypatch.setattr(manager_module, "start_playback", lambda *a, **kw: 0.5)
    monkeypatch.setattr(manager_module, "shutdown_playback", lambda *a, **kw: None)
    monkeypatch.setattr(manager_module, "probe_wav", lambda *_: (0.5, 24_000))
    monkeypatch.setattr(TtsManager, "_installed", lambda self, engine: True)
    monkeypatch.setattr(TtsManager, "_tts_service", lambda self: service)
    return service


def test_a_sample_is_rendered_once_then_reused(_isolate: _FakeService) -> None:
    manager = TtsManager(config=_Config())

    first = manager.speak_sample("magpie", "Jason")
    second = manager.speak_sample("magpie", "Jason")

    assert first["cached"] is False
    assert first["playing"] is True
    assert second["cached"] is True
    assert _isolate.calls == 1
    assert first["wav_path"] == second["wav_path"]


def test_each_voice_gets_its_own_sample(_isolate: _FakeService) -> None:
    manager = TtsManager(config=_Config())

    aria = manager.speak_sample("magpie", "Aria")
    jason = manager.speak_sample("magpie", "Jason")

    assert aria["wav_path"] != jason["wav_path"]
    assert _isolate.calls == 2


def test_a_foreign_voice_falls_back_to_the_engine_default(_isolate: _FakeService) -> None:
    manager = TtsManager(config=_Config())

    result = manager.speak_sample("magpie", "not-a-voice")

    assert result["voice"] == "Aria"


def test_a_bundled_sample_wins_over_rendering(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bundled = tmp_path / "shipped.wav"
    bundled.write_bytes(b"RIFF-shipped")
    monkeypatch.setattr(manager_module, "bundled_sample_path", lambda *_: bundled)

    result = TtsManager(config=_Config()).speak_sample("magpie", "Sofia")

    assert result["bundled"] is True
    assert result["cached"] is True
    assert result["wav_path"] == str(bundled)


def test_speak_sample_refuses_when_tts_is_off() -> None:
    with pytest.raises(TtsError, match="turned off"):
        TtsManager(config=_Config(engine="off")).speak_sample("off", None)


def test_cache_path_is_voice_specific() -> None:
    aria = sample_cache_path("magpie", "Aria", "en-US")
    jason = sample_cache_path("magpie", "Jason", "en-US")
    assert aria != jason
    assert aria.name.endswith(".wav")
