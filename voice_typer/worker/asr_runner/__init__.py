"""GGUF ASR runner.

Drives ``transcribe-cli`` (transcribe.cpp) as a sibling executable. This is
the only ASR runner used after the Phase 1 cutover; the sidecar keeps the
worker boundary and never loads a speech model in-process.
"""

from voice_typer.worker.asr_runner.engine import GgufTranscriptionEngine
from voice_typer.worker.asr_runner.families import (
    LanguageNotSupportedError,
    gguf_model_path_for,
    gguf_model_path_for_key,
)
from voice_typer.worker.asr_runner.runner import GgufRunner, RunnerError

__all__ = [
    "GgufRunner",
    "GgufTranscriptionEngine",
    "LanguageNotSupportedError",
    "RunnerError",
    "gguf_model_path_for",
    "gguf_model_path_for_key",
]
