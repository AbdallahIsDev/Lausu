"""Locate and drive the sibling ``transcribe-cli`` executable.

Frozen-path rule (same authority as ffmpeg/llama-server): resolve through
``bundled_bin_dir()`` / ``_shipped_dirs()`` from ``ffmpeg_binaries.py``. A
Nuitka onefile's ``sys.executable`` points INSIDE the extraction dir, so it is
never used as the sibling base. There is no PATH fallback in a frozen build.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import wave
from array import array
from pathlib import Path

from voice_typer.server.media_ingest.ffmpeg_binaries import (
    _names,
    _shipped_dirs,
    bundled_bin_dir,
    is_frozen_build,
)
from voice_typer.worker.asr_runner.contract import RunnerResult, parse_runner_output

log = logging.getLogger("voice_typer.worker.asr_runner")

ENV_TRANSCRIBE_CLI = "LAUSU_TRANSCRIBE_CLI"
RUNNER_PROGRAM = "transcribe-cli"
DEFAULT_TIMEOUT_S = 180.0


class RunnerError(RuntimeError):
    """Runner invocation failed. Detail stays in the log, not in UI copy."""


def resolve_runner_path(
    *,
    module_globals: dict[str, object] | None = None,
    sys_module: object | None = None,
) -> str | None:
    """Return the runner path, or None when it is not installed."""
    override = os.environ.get(ENV_TRANSCRIBE_CLI)
    if override:
        candidate = Path(override).expanduser()
        try:
            if candidate.is_file():
                return str(candidate.resolve())
        except OSError:
            pass

    # Reuse the shipped-binary authority; do not invent a third resolver.
    for directory in _shipped_dirs():
        for name in _names(RUNNER_PROGRAM):
            candidate = directory / name
            try:
                if candidate.is_file():
                    return str(candidate.resolve())
            except OSError:
                continue

    if not is_frozen_build(module_globals=module_globals, sys_module=sys_module):
        found = shutil.which(RUNNER_PROGRAM)
        if found:
            return found
    return None


def bundled_runner_dir() -> Path:
    """Expose the same frozen-safe base used by the sibling resolver."""
    return bundled_bin_dir()


def _write_wav(audio: object, path: Path) -> None:
    """Write 16 kHz mono float32 PCM, the runner's required input format."""
    samples = array("f", audio.tolist() if hasattr(audio, "tolist") else audio)
    if hasattr(samples, "byteswap") and _is_big_endian():
        samples.byteswap()
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(4)
        handle.setframerate(16000)
        handle.writeframes(samples.tobytes())


def _is_big_endian() -> bool:
    import sys

    return sys.byteorder == "big"


class GgufRunner:
    """Run one 16 kHz mono WAV through the sibling transcribe.cpp CLI."""

    def __init__(self, model_path: str, *, executable: str | None = None, timeout: float = DEFAULT_TIMEOUT_S):
        self.model_path = model_path
        self._executable = executable
        self._timeout = timeout
        self._lock = threading.Lock()

    @property
    def executable(self) -> str:
        exe = self._executable or resolve_runner_path()
        if not exe:
            raise RunnerError("The speech runner is not installed. Reinstall the app or contact support.")
        return exe

    def transcribe(
        self,
        audio: object,
        *,
        language: str | None = None,
        backend: str | None = None,
        abort_event: threading.Event | None = None,
    ) -> RunnerResult:
        """Decode audio and return the parsed result. Never downloads."""
        with self._lock:
            with tempfile.TemporaryDirectory(prefix="lausu-gguf-") as workdir:
                wav_path = Path(workdir) / "input.wav"
                _write_wav(audio, wav_path)
                argv = [
                    self.executable,
                    "--batch-jsonl",
                    "-q",
                    "-m",
                    self.model_path,
                    "--threads",
                    str(min(8, os.cpu_count() or 4)),
                ]
                if backend:
                    argv += ["--backend", backend]
                if language:
                    argv += ["--language", language]
                argv.append(str(wav_path))

                log.info("[GGUF] runner start: model=%s backend=%s", Path(self.model_path).name, backend or "auto")
                process = subprocess.Popen(
                    argv,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                try:
                    stdout, stderr = process.communicate(timeout=self._timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    raise RunnerError("Speech recognition took too long and was stopped.") from None
                except Exception:
                    process.kill()
                    process.communicate()
                    raise

                if abort_event is not None and abort_event.is_set():
                    raise RunnerError("Transcription was stopped.")

                if process.returncode != 0:
                    # Detail goes to the durable log; the user gets plain copy.
                    log.error(
                        "[GGUF] runner failed: exit=%d stdout=%r stderr=%r",
                        process.returncode,
                        stdout[-1000:],
                        stderr[-2000:],
                    )
                    raise RunnerError("Speech recognition could not read the audio.")
                try:
                    return parse_runner_output(stdout)
                except (ValueError, json.JSONDecodeError) as exc:
                    log.error("[GGUF] invalid runner output: %r", stdout[-1000:], exc_info=exc)
                    raise RunnerError("Speech recognition returned an unreadable result.") from None
