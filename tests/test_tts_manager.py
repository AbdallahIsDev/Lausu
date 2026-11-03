"""Tests for the app-facing TTS manager (no runtimes spawned)."""

from __future__ import annotations

from pathlib import Path

import pytest
from voice_typer.server.tts.engines import Audio8Engine
from voice_typer.server.tts.manager import TtsManager
from voice_typer.server.tts.types import TtsError


class _Config:
    def __init__(self, engine: str = "off") -> None:
        self.tts_engine = engine
        self.tts_voice = "Aria"
        self.tts_language = "en-US"
        self.tts_enabled = True


def test_status_reports_both_engines_and_missing_packs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_TYPER_AUDIO8_BIN", str(tmp_path / "nope-audio8.exe"))
    monkeypatch.setenv("VOICE_TYPER_NEMO_SPEECH_BIN", str(tmp_path / "nope-nemo.exe"))

    status = TtsManager(config=_Config()).status()

    assert status["engine"] == "off"
    assert status["enabled"] is True
    assert status["engines"]["audio8"]["available"] is False
    assert status["engines"]["magpie"]["available"] is False
    assert status["engines"]["audio8"]["download_bytes"] > 0
    assert "ar-MSA" in status["languages"]
    assert "hi-IN" in status["languages"]
    assert set(status["sample_cached"]) == {"audio8", "magpie"}


def test_status_normalizes_an_unadvertised_language() -> None:
    class _Junk(_Config):
        def __init__(self) -> None:
            super().__init__("magpie")
            self.tts_language = "xx-XX"
            self.tts_voice = "Klingon"

    status = TtsManager(config=_Junk()).status()

    assert status["language"] == "en-US"
    assert status["voice"] == "Aria"


def test_speak_refuses_when_engine_is_off() -> None:
    with pytest.raises(TtsError, match="turned off"):
        TtsManager(config=_Config("off")).speak("hello")


def test_speak_rejects_empty_text() -> None:
    with pytest.raises(TtsError, match="empty text"):
        TtsManager(config=_Config("audio8")).speak("   ")


def test_prepare_rejects_unknown_engine() -> None:
    with pytest.raises(TtsError, match="unknown tts engine"):
        TtsManager(config=_Config()).prepare("piper")


def test_service_rebuilds_when_a_pack_appears(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pack downloaded mid-session must not stay invisible to a cached service."""
    manager = TtsManager(config=_Config("audio8"))
    assert manager._tts_service().audio8 is None

    engine = Audio8Engine(binary=Path("audio8.exe"), model=Path("model.gguf"))
    monkeypatch.setattr(TtsManager, "_audio8_engine", lambda self: engine)

    assert manager._tts_service().audio8 is engine


def test_prepare_magpie_requires_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_TYPER_NEMO_SPEECH_BIN", str(tmp_path / "missing-nemo.exe"))

    with pytest.raises(TtsError, match="runtime missing"):
        TtsManager(config=_Config()).prepare("magpie")
