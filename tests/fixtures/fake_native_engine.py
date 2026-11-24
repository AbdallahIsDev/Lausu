"""Fake native-library layer for the transcribe.cpp ctypes path.

No DLL, model or GPU is involved. Tests drive the real
``GgufTranscriptionEngine`` / runner / result pipeline through a stand-in
for the shared library, so behaviour is asserted against the shipped ctypes
path rather than a parallel fake engine.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from voice_typer.worker.asr_runner import GgufRunner, GgufTranscriptionEngine

FIXED_TEXT = "hello from the fake library"
FIXED_SEGMENTS = [(0, 640, "hello from"), (640, 1210, "the fake library")]


class FakeLibrary:
    """Minimal stand-in for the C API bound in ``asr_runner.runner``."""

    def __init__(
        self,
        *,
        text: str = FIXED_TEXT,
        segments: list[tuple[int, int, str]] | None = None,
        language: bytes = b"en",
        status: int = 0,
        fail_open: bool = False,
        crash: bool = False,
        on_run: Any = None,
    ) -> None:
        self.text = text
        self.segments = FIXED_SEGMENTS if segments is None else segments
        self.language = language
        self.status = status
        self.fail_open = fail_open
        self.crash = crash
        self.on_run = on_run
        self.freed = False
        self.run_count = 0

    def transcribe_open(self, _path, _load, _session, out):
        if self.fail_open:
            return 4
        out._obj.value = 1
        return 0

    def transcribe_set_abort_callback(self, *_args):
        return None

    def transcribe_run(self, *_args):
        self.run_count += 1
        if self.on_run is not None:
            extra = self.on_run()
            if extra is not None:
                return extra
        if self.crash:
            raise OSError("simulated native crash")
        return self.status

    def transcribe_full_text(self, _session):
        return self.text.encode("utf-8")

    def transcribe_n_segments(self, _session):
        return len(self.segments)

    def transcribe_get_segment(self, _session, index, out):
        t0, t1, text = self.segments[index]
        seg = out._obj
        seg.t0_ms = t0
        seg.t1_ms = t1
        seg.text = text.encode("utf-8")
        seg.speaker_id = 0
        return 0

    def transcribe_segment_init(self, *_args):
        return None

    def transcribe_detected_language(self, _session):
        return self.language

    def transcribe_status_string(self, status):
        return f"status-{status}".encode()

    def transcribe_session_free(self, _session):
        self.freed = True


def loader_for(fake: FakeLibrary):
    return lambda: (fake, Path("."))


def install_runner(monkeypatch: Any, fake: FakeLibrary | None = None) -> FakeLibrary:
    """Bind ``GgufTranscriptionEngine.load`` to the fake shared library."""
    fake = fake or FakeLibrary()

    def _runner(path: str) -> GgufRunner:
        return GgufRunner(path, loader=loader_for(fake))

    monkeypatch.setattr("voice_typer.worker.asr_runner.engine.GgufRunner", _runner)
    return fake


def make_engine(
    monkeypatch: Any,
    *,
    config: Any = None,
    language: str | None = None,
    device: str = "cpu",
    fake: FakeLibrary | None = None,
    load: bool = True,
) -> tuple[GgufTranscriptionEngine, FakeLibrary]:
    """Return a real Gguf engine backed by the fake native library."""
    fake = install_runner(monkeypatch, fake)
    if config is None:
        config = SimpleNamespace(
            asr_backend="whisper",
            language=language,
            hallucination_filter_mode=None,
            log_transcriptions=False,
            vad_filter_enabled=False,
        )
    engine = GgufTranscriptionEngine(
        model_size="test",
        model_path="model.gguf",
        config=config,
        device=device,
        language=language,
    )
    # The worker resolves the model by language; the decode path reads the
    # engine's pinned language, so mirror that assignment in tests.
    engine.language = language
    if load:
        engine.load()
    return engine, fake
