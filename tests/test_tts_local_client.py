"""Tests for the OpenAI-compatible local speech client."""

from __future__ import annotations

import io
import json
import sys
import threading
import wave
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from voice_typer.server.tts.local_client import LocalSpeechClient
from voice_typer.server.tts.types import TtsError, TtsRequest


def _wav_bytes(sample_rate: int = 24_000, seconds: float = 0.25) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * int(sample_rate * seconds))
    return buffer.getvalue()


class _SpeechHandler(BaseHTTPRequestHandler):
    """Minimal /v1/audio/speech double with switchable failure modes."""

    mode = "ok"
    last_payload: dict[str, object] = {}

    def do_POST(self) -> None:  # noqa: N802 - http.server contract
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_payload = json.loads(self.rfile.read(length) or b"{}")
        if type(self).mode == "http_error":
            body = b'{"error": {"message": "voice not found"}}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if type(self).mode == "json_200":
            # The exact trap the audio.cpp docs warn about: 200 + JSON body.
            body = b'{"error": "model failed to load"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = _wav_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Silence the default stderr access log in tests."""


@pytest.fixture()
def speech_server() -> Iterator[tuple[str, type[_SpeechHandler]]]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SpeechHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", _SpeechHandler
    finally:
        server.shutdown()
        server.server_close()


def test_speech_writes_wav_and_reports_timing(speech_server, tmp_path: Path) -> None:
    base_url, handler = speech_server
    handler.mode = "ok"
    client = LocalSpeechClient(base_url, "audio8")
    out = tmp_path / "out.wav"

    result = client.speech(TtsRequest(text="hello"), out, model="audio8", voice="Aria")

    assert out.is_file()
    assert result.engine == "audio8"
    assert result.duration_s == pytest.approx(0.25, abs=0.02)
    assert result.sample_rate == 24_000
    assert result.wall_s > 0
    assert handler.last_payload["input"] == "hello"
    assert handler.last_payload["voice"] == "Aria"
    assert handler.last_payload["response_format"] == "wav"


def test_json_body_with_200_is_rejected(speech_server, tmp_path: Path) -> None:
    base_url, handler = speech_server
    handler.mode = "json_200"
    client = LocalSpeechClient(base_url, "magpie")

    with pytest.raises(TtsError, match="not audio"):
        client.speech(TtsRequest(text="hello"), tmp_path / "x.wav", model="magpie")


def test_http_error_surfaces_runtime_detail(speech_server, tmp_path: Path) -> None:
    base_url, handler = speech_server
    handler.mode = "http_error"
    client = LocalSpeechClient(base_url, "magpie")

    with pytest.raises(TtsError, match="404"):
        client.speech(TtsRequest(text="hello"), tmp_path / "x.wav", model="magpie")


def test_probe_wav_reads_valid_wav_without_soundfile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A PCM WAV probes via stdlib wave when soundfile is unavailable."""
    monkeypatch.setitem(sys.modules, "soundfile", None)

    from voice_typer.server.tts.wav import probe_wav

    wav_file = tmp_path / "speech.wav"
    wav_file.write_bytes(_wav_bytes(sample_rate=16_000, seconds=0.1))
    duration, sample_rate = probe_wav(wav_file)

    assert sample_rate == 16_000
    assert duration == pytest.approx(0.1)


def test_probe_wav_rejects_bad_files_without_soundfile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Missing, zero-byte and malformed WAVs keep their TtsError contract."""
    monkeypatch.setitem(sys.modules, "soundfile", None)

    from voice_typer.server.tts.wav import probe_wav

    with pytest.raises(TtsError, match="engine produced no audio"):
        probe_wav(tmp_path / "missing.wav")
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(TtsError, match="engine produced no audio"):
        probe_wav(empty)
    malformed = tmp_path / "malformed.wav"
    malformed.write_bytes(b"RIFF\x00\x00\x00\x00WAVEnot-a-real-wav")
    with pytest.raises(TtsError, match="unreadable WAV"):
        probe_wav(malformed)
