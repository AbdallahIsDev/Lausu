"""Voice identity: we send a speaker INDEX and the runtime selects that speaker.

Three things are pinned, because the first two alone let the original bug through:

1. the payload we send (a fake runtime echoes it back);
2. what the runtime RESOLVES it to (its own ``--verbose`` log line
   ``with speaker=N``) — the runtime's name table is out of order, so
   ``voice="Sofia"`` resolves to ``speaker=1``, which the model's ``speaker_map``
   makes Jason (a male voice). That resolution is the defect;
3. that different selectors produce different audio.

The real-runtime tests are skipped only when no runtime/pack is installed; a
runtime that is present but misbehaving fails the test instead of hiding.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pytest
import soundfile as sf
from voice_typer.server.tts.local_client import LocalSpeechClient
from voice_typer.server.tts.samples import SAMPLE_TEXT
from voice_typer.server.tts.types import TtsError, TtsRequest
from voice_typer.server.tts.voices import MAGPIE_VOICES, wire_voice

#: The model's own ``*.nemo.speakers.json``, which the runtime's name table
#: contradicts. Anything else in this file is derived work; this is the source.
MODEL_SPEAKER_INDEX: dict[str, int] = {
    "Aria": 0,
    "Jason": 1,
    "John": 2,
    "Leo": 3,
    "Sofia": 4,
}

# ── fake runtime: echo what we send ───────────────────────────────────────


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(2_400, dtype=np.float32), 24_000, format="WAV")
    return buffer.getvalue()


class _EchoHandler(BaseHTTPRequestHandler):
    payloads: list[dict[str, object]] = []

    def do_POST(self) -> None:  # noqa: N802 - http.server contract
        length = int(self.headers.get("Content-Length", "0"))
        type(self).payloads.append(json.loads(self.rfile.read(length) or b"{}"))
        body = _wav_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Silence the default access log."""


@pytest.fixture()
def echo_server() -> Iterator[tuple[str, type[_EchoHandler]]]:
    _EchoHandler.payloads = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", _EchoHandler
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("voice", ["Sofia", "Jason"])
def test_render_payload_carries_the_speaker_index(echo_server, tmp_path: Path, voice: str) -> None:
    base_url, handler = echo_server
    client = LocalSpeechClient(base_url, "magpie")

    client.speech(
        TtsRequest(text="hello", voice=wire_voice("magpie", voice), language="en-US"),
        tmp_path / f"{voice}.wav",
        model="magpie",
    )

    sent = handler.payloads[-1]["voice"]
    assert sent == str(MODEL_SPEAKER_INDEX[voice])
    # The regression that shipped: a bare name resolves through the runtime's
    # scrambled table and plays a different speaker.
    assert sent != voice
    assert handler.payloads[-1]["language"] == "en-US"


def test_every_magpie_voice_sends_its_own_index() -> None:
    sent = {voice.id: voice.wire for voice in MAGPIE_VOICES}
    assert sent == {name: str(index) for name, index in MODEL_SPEAKER_INDEX.items()}
    assert len(set(sent.values())) == len(sent)


# ── real runtime: the runtime's own resolution + differing audio ──────────


def _runtime_paths() -> tuple[Path, Path, Path, Path] | None:
    """Return (binary, magpie_gguf, codec_gguf, tokenizer_dir) when installed."""
    from voice_typer.server.tts.paths import magpie_binary, model_dir

    binary = magpie_binary()
    root = model_dir("magpie")
    magpie = next(iter(sorted(root.glob("**/magpie_tts_multilingual_357m*.gguf"))), None)
    codec = next(iter(sorted(root.glob("**/*nano*codec*.gguf"))), None)
    tokenizer = next(iter(sorted(root.glob("**/model_config.yaml"))), None)
    if not (binary.is_file() and magpie and codec and tokenizer):
        return None
    return binary, magpie, codec, tokenizer.parent


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _start_runtime(paths: tuple[Path, Path, Path, Path], log_path: Path) -> tuple[subprocess.Popen, str]:
    """Start the runtime with --verbose; return the process and its base URL."""
    binary, magpie, codec, tokenizer = paths
    from voice_typer.server.tts.runtime_server import free_port

    port = free_port()
    log_file = log_path.open("wb")
    proc = subprocess.Popen(  # noqa: S603 - fixed argv
        [
            str(binary),
            "serve",
            "--tts-model",
            str(magpie),
            "--codec-model",
            str(codec),
            "--tokenizer-dir",
            str(tokenizer),
            "--no-ui",
            "--verbose",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    log_file.close()
    return proc, f"http://127.0.0.1:{port}"


@pytest.mark.real_shared_hub  # READ-ONLY: locates the installed pack, writes only into tmp_path
@pytest.mark.skipif(
    os.environ.get("VOICE_TYPER_SKIP_REAL_TTS_TESTS") == "1",
    reason="real-runtime TTS probe disabled by VOICE_TYPER_SKIP_REAL_TTS_TESTS",
)
def test_real_runtime_selects_the_picked_speaker(tmp_path: Path) -> None:
    paths = _runtime_paths()
    if paths is None:
        pytest.skip("NeMo-Speech.cpp runtime/pack not installed")

    log_path = tmp_path / "runtime.log"
    proc, base_url = _start_runtime(paths, log_path)
    digests: dict[str, str] = {}
    refused: dict[str, bool] = {}
    try:
        deadline = time.monotonic() + 300.0
        healthy = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"runtime exited during startup (rc={proc.returncode}):\n{_tail(log_path)}")
            try:
                with urlopen(f"{base_url}/health", timeout=2.0) as response:  # noqa: S310 - loopback
                    if response.status == 200:
                        healthy = True
                        break
            except Exception:
                time.sleep(0.5)
        if not healthy:
            pytest.fail(f"runtime did not become healthy in 300s:\n{_tail(log_path)}")

        client = LocalSpeechClient(base_url, "magpie")
        for voice in ("Sofia", "Jason", "Aria"):
            out = tmp_path / f"{voice}.wav"
            client.speech(
                TtsRequest(text=SAMPLE_TEXT, voice=wire_voice("magpie", voice), language="en-US"),
                out,
                model="magpie",
            )
            digests[voice] = _digest(out)

        # The runtime rejects what it does not know, so a wrong selector cannot
        # degrade into "the default spoke either way" unnoticed.
        for label, request in (
            ("unknown name", TtsRequest(text=SAMPLE_TEXT, voice="__no_such_speaker__", language="en-US")),
            ("unadvertised language", TtsRequest(text=SAMPLE_TEXT, voice="4", language="ja-JP")),
        ):
            try:
                client.speech(request, tmp_path / "refused.wav", model="magpie")
            except TtsError:
                refused[label] = True
            else:
                refused[label] = False
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()

    # Audio: three speakers, three clips. Identical bytes would mean the
    # selector was ignored and one default voice spoke every time.
    assert len(set(digests.values())) == 3, digests

    # Resolution: the runtime's own log says which speaker each request used.
    resolved = [int(match) for match in re.findall(r"with speaker=(\d+)", log_path.read_text("utf-8", "replace"))]
    assert resolved[-3:] == [4, 1, 0], f"resolved speakers {resolved} (expected ...4, 1, 0)\n{_tail(log_path)}"

    assert refused == {"unknown name": True, "unadvertised language": True}


def _tail(path: Path, limit: int = 20) -> str:
    try:
        lines = path.read_text("utf-8", "replace").splitlines()
    except OSError:
        return "<no log>"
    return "\n".join(lines[-limit:])
