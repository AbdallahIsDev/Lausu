"""Tests-only stand-in for the sibling ``transcribe-cli`` executable.

Mimics the upstream JSONL contract documented in
``voice_typer/worker/asr_runner/contract.py``. No model, GPU or network is
involved: the launcher prints a fixed JSON line derived from the WAV path.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

FIXED_TEXT = "hello from the fake runner"
FIXED_SEGMENTS = [
    {"t0_ms": 0, "t1_ms": 640, "text": "hello from"},
    {"t0_ms": 640, "t1_ms": 1210, "text": "the fake runner"},
]


def main() -> int:
    args = sys.argv[1:]
    if "--emit-invalid" in args:
        print("not json")
        return 0
    if "--fail" in args:
        print("simulated runner failure", file=sys.stderr)
        return 3
    if "--emit-error" in args:
        payload = {"file": "input.wav", "text": "", "segments": [], "error": "TRANSCRIBE_ERR_GGUF"}
        print(json.dumps(payload))
        return 0
    wav = args[-1] if args else "input.wav"
    payload = {
        "file": os.path.basename(wav),
        "text": FIXED_TEXT,
        "segments": FIXED_SEGMENTS,
        "mel_ms": 1.0,
        "encode_ms": 2.0,
        "decode_ms": 3.0,
    }
    print(json.dumps(payload))
    return 0


def write_fake_runner(directory: Path) -> Path:
    """Write a launcher plus script; return the launcher path."""
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "fake_runner_body.py"
    script.write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
    if os.name == "nt":
        launcher = directory / "transcribe-cli.cmd"
        launcher.write_text(
            f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n',
            encoding="utf-8",
        )
    else:
        launcher = directory / "transcribe-cli"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return launcher


if __name__ == "__main__":
    sys.exit(main())
