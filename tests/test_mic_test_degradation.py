"""
Phase 2d degradation matrix (§8.10): mic-test auto-transcription.
WHY instead. These tests pin the ``transcription_unavailable`` +
"""

from __future__ import annotations

import io
import struct
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock

from voice_typer.server.service.microphone_test import MicrophoneTestMixin


def _tiny_wav_result(tmp_path, duration_s: float = 0.05, sample_rate: int = 16000) -> dict:
    """Persist a tiny valid mono WAV under tmp_path and return a"""
    import os

    n = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n}h", *([0] * n)))
    wav_file = tmp_path / "test-filtered.wav"
    wav_file.write_bytes(buf.getvalue())
    if os.name != "nt":
        os.chmod(wav_file, 0o600)
    return {
        "success": True,
        "audio_file": {"path": str(wav_file), "bytes": wav_file.stat().st_size},
    }


def _mixin(app) -> MicrophoneTestMixin:
    mixin = MicrophoneTestMixin()
    mixin._app = app  # type: ignore[attr-defined], ServiceMixinBase._app
    return mixin


class _ContractOnlyEngine:
    """Ready backend shaped like the worker proxies: contract method only.

    ``transcribe_with_fallback`` is the one method ``AsrBackend``
    guarantees; a backend is not required to expose ``transcribe``.
    """

    is_loaded = True

    def __init__(self, text: str) -> None:
        self._text = text
        self.received: list = []

    def transcribe_with_fallback(self, audio, *args, **kwargs) -> str:
        self.received.append(audio)
        return self._text


class TestMicTestDegradation:
    def test_no_engine_loaded_marks_transcription_unavailable(self, monkeypatch, tmp_path):
        """Engine absent → marker set so the UI can explain the gap."""
        from voice_typer.server import level_monitor

        monkeypatch.setattr(
            level_monitor,
            "stop_test_recording",
            lambda: _tiny_wav_result(tmp_path),
        )
        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=lambda: None))
        result = _mixin(app).microphone_test_stop()
        assert result["success"] is True
        assert result["transcription_unavailable"] is True
        assert result["transcription_reason"] == "no_engine_loaded"
        assert "transcription" not in result

    def test_unloaded_engine_marks_transcription_unavailable(self, monkeypatch, tmp_path):
        """Engine exists but not loaded → same marker (still warming / no pack)."""
        from voice_typer.server import level_monitor

        monkeypatch.setattr(
            level_monitor,
            "stop_test_recording",
            lambda: _tiny_wav_result(tmp_path),
        )
        engine = MagicMock()
        engine.is_loaded = False
        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=lambda: engine))
        result = _mixin(app).microphone_test_stop()
        assert result["transcription_unavailable"] is True
        assert result["transcription_reason"] == "no_engine_loaded"

    def test_loaded_engine_transcribes_without_marker(self, monkeypatch, tmp_path):
        """Engine loaded → transcription present, no degradation marker.

        The engine exposes only ``transcribe`` (legacy duck-typed backend),
        so this pins the compatibility branch of the gate.
        """
        from voice_typer.server import level_monitor

        monkeypatch.setattr(
            level_monitor,
            "stop_test_recording",
            lambda: _tiny_wav_result(tmp_path),
        )
        engine = SimpleNamespace(is_loaded=True, transcribe=lambda _audio: "hello world")
        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=lambda: engine))
        result = _mixin(app).microphone_test_stop()
        assert result["transcription"] == "hello world"
        assert "transcription_unavailable" not in result

    def test_worker_backed_engine_transcribes_via_shim(self, monkeypatch, tmp_path):
        """C7: mic-test calls ``transcribe`` on the worker-backed shim."""
        import concurrent.futures

        import voice_typer.server.worker_backed_asr as shim_mod
        from voice_typer.server import level_monitor
        from voice_typer.server.worker_backed_asr import WorkerBackedAsr

        monkeypatch.setattr(
            level_monitor,
            "stop_test_recording",
            lambda: _tiny_wav_result(tmp_path),
        )

        class _FakeClient:
            port = 5123

            def request_samples(self, raw, rate, language, timeout=None):
                future: concurrent.futures.Future[dict] = concurrent.futures.Future()
                future.set_result({"text": "worker mic", "latency_ms": 3})
                return future

        monkeypatch.setattr(shim_mod, "get_shared_client", lambda: _FakeClient())
        engine = WorkerBackedAsr(model_size="small.en")
        engine._loaded = True
        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=lambda: engine))
        result = _mixin(app).microphone_test_stop()
        assert result["transcription"] == "worker mic"
        assert "transcription_unavailable" not in result

    def test_contract_only_backend_transcribes(self, monkeypatch, tmp_path):
        """A ready backend exposing only ``transcribe_with_fallback`` yields text.

        The gate used to call ``transcribe``, which worker proxies do not
        define, so a ready model silently reported no transcription.
        """
        from voice_typer.server import level_monitor

        monkeypatch.setattr(
            level_monitor,
            "stop_test_recording",
            lambda: _tiny_wav_result(tmp_path),
        )
        engine = _ContractOnlyEngine("ready model text")
        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=lambda: engine))
        result = _mixin(app).microphone_test_stop()
        assert result["transcription"] == "ready model text"
        assert "transcription_unavailable" not in result
        assert engine.received, "engine must receive the decoded test audio"

    def test_loaded_backend_without_speech_reports_no_text(self, monkeypatch, tmp_path):
        """Empty engine output IS no speech, not an unavailable-model marker."""
        from voice_typer.server import level_monitor

        monkeypatch.setattr(
            level_monitor,
            "stop_test_recording",
            lambda: _tiny_wav_result(tmp_path),
        )
        engine = _ContractOnlyEngine("   ")
        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=lambda: engine))
        result = _mixin(app).microphone_test_stop()
        assert "transcription" not in result
        assert "transcription_unavailable" not in result

    def test_no_recording_audio_skips_marker(self, monkeypatch):
        """stop_test_recording failure → no marker (nothing to transcribe)."""
        from voice_typer.server import level_monitor

        monkeypatch.setattr(level_monitor, "stop_test_recording", lambda: {"success": False})
        app = SimpleNamespace(models=SimpleNamespace(active_transcriber=lambda: None))
        result = _mixin(app).microphone_test_stop()
        assert result["success"] is False
        assert "transcription_unavailable" not in result
