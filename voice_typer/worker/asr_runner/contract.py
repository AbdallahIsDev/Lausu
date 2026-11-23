"""Parse the ``transcribe-cli`` JSONL result contract.

UPSTREAM DOCUMENTATION (not a guess):
https://github.com/handy-computer/transcribe.cpp/blob/main/examples/cli/asr.cpp

The CLI prints one JSON object per input file when ``--batch-jsonl`` is set::

    {"file":"...","text":"...","segments":[{"t0_ms":0,"t1_ms":1200,"text":"..."}],
     "mel_ms":1.0,"encode_ms":2.0,"decode_ms":3.0}

Segment rows optionally carry ``speaker_id``. An ``error`` key is present when
the decode returned a non-OK status. transcribe.cpp does NOT publish a
calibrated per-segment confidence: neither ``avg_logprob`` nor
``no_speech_prob`` is emitted, so the hallucination gate keeps its existing
fail-open path (hallucination._decoder_confirms_silence). Do not fabricate
those numbers here.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

log = logging.getLogger("voice_typer.worker.asr_runner")


@dataclass(frozen=True)
class RunnerSegment:
    """One transcript segment. Timestamps are milliseconds upstream."""

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
    """Decoded JSONL row from the runner."""

    text: str
    segments: tuple[RunnerSegment, ...] = ()
    error: str | None = None
    language: str | None = None


def parse_runner_line(line: str) -> RunnerResult:
    """Parse one JSONL output line. Raises ValueError on an invalid payload."""
    stripped = line.strip()
    if not stripped:
        raise ValueError("empty runner output")
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("runner output is not a JSON object")

    raw_text = payload.get("text")
    if not isinstance(raw_text, str):
        raise ValueError("runner output has no string 'text'")

    segments: list[RunnerSegment] = []
    raw_segments = payload.get("segments", [])
    if not isinstance(raw_segments, list):
        raise ValueError("runner 'segments' is not a list")
    for row in raw_segments:
        if not isinstance(row, dict):
            continue
        t0, t1 = row.get("t0_ms"), row.get("t1_ms")
        if not isinstance(t0, int) or not isinstance(t1, int):
            continue
        text = row.get("text")
        segments.append(
            RunnerSegment(
                t0_ms=t0,
                t1_ms=t1,
                text=text if isinstance(text, str) else "",
                speaker_id=row.get("speaker_id") if isinstance(row.get("speaker_id"), int) else None,
            )
        )

    error = payload.get("error")
    return RunnerResult(
        text=raw_text,
        segments=tuple(segments),
        error=error if isinstance(error, str) else None,
        language=None,
    )


def parse_runner_output(stdout: str) -> RunnerResult:
    """Parse stdout, taking the last non-empty JSON line (one file per run)."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("runner produced no output")
    result = parse_runner_line(lines[-1])
    if result.error:
        log.warning("[GGUF] runner reported decode status: %s", result.error)
    return result
