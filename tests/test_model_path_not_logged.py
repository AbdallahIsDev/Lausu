"""The system-whisper INFO lines must not carry the weights path.

The full HF cache path (repo slug + snapshot hash) is user-machine
detail: it does not belong on INFO lines. Model identity already rides
in the adjacent ``whisper <size> running on <device>`` line.
"""

from __future__ import annotations

from pathlib import Path

_SOURCE = (
    Path(__file__).resolve().parent.parent
    / "voice_typer"
    / "server"
    / "system_whisper.py"
).read_text(encoding="utf-8")


def test_serving_line_has_no_path_placeholder():
    assert "from system libraries (%s)" not in _SOURCE


def test_ready_line_has_no_path_placeholder():
    assert "model ready (%s)" not in _SOURCE
