"""Result contract for the transcribe.cpp C API.

UPSTREAM DOCUMENTATION (not a guess):
https://github.com/handy-computer/transcribe.cpp/blob/v0.4.2/include/transcribe.h

``struct transcribe_segment`` carries ``t0_ms``, ``t1_ms``, ``text`` and
``speaker_id``. There are no calibrated confidence fields: the runner does not
publish ``avg_logprob`` / ``no_speech_prob``. The hallucination gate therefore
keeps its existing fail-open path; do not invent a proxy value here.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("voice_typer.worker.asr_runner")

OK = 0
ERR_ABORTED = 13
ERR_OUTPUT_TRUNCATED = 18
ERR_OUTPUT_REPETITION = 19


@dataclass(frozen=True)
class RunnerSegment:
    """One transcript segment (milliseconds upstream, seconds for the pipeline)."""

    t0_ms: int
    t1_ms: int
    text: str
    speaker_id: int | None = None

    @property
    def start(self) -> float:
        return self.t0_ms / 1000.0

    @property
    def end(self) -> float:
        return self.t1_ms / 1000.0


@dataclass(frozen=True)
class RunnerResult:
    text: str
    segments: tuple[RunnerSegment, ...] = ()
    language: str | None = None
    status: int = OK


EXPECTED_VERSION = "0.4.2"
EXPECTED_HEADER_HASH = "f99ad4169374b8f3"


def check_contract(directory: Path, expected_version: str = EXPECTED_VERSION) -> None:
    """Validate the artifact contract before loading the DLL (upstream binding rule)."""
    contract = directory / "contract.json"
    if not contract.is_file():
        raise RuntimeError("The speech runtime contract file is missing.")
    try:
        data = json.loads(contract.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise RuntimeError("The speech runtime contract file is unreadable.") from exc
    version = str(data.get("version", ""))
    if version != expected_version:
        log.error("[GGUF] runtime contract version mismatch: %r != %r", version, expected_version)
        raise RuntimeError("The installed speech runtime is the wrong version.")
    header_hash = str(data.get("header_hash", ""))
    if header_hash != EXPECTED_HEADER_HASH:
        log.error("[GGUF] runtime ABI mismatch: %r != %r", header_hash, EXPECTED_HEADER_HASH)
        raise RuntimeError("The installed speech runtime has an incompatible API.")
