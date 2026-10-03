"""Guard: a superseded split module must not creep back in.

The Recorder god-class decomposition produced intermediate modules that were
fully re-implemented elsewhere; one of them (`_recorder_split.py`) was left
tracked with zero importers, polluting every line-count, comment-ratio and
coverage metric. This pins the specific module that was removed so the
same half-finished split cannot silently reappear.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RECORDING_PKG = Path(__file__).resolve().parents[1] / "voice_typer" / "server" / "recording"

# Intermediate modules from past god-class splits, each superseded by the
# live modules in the same package. Reintroducing any of them means a
# create-first split was abandoned half-done.
SUPERSEDED_MODULES = [
    "_recorder_split.py",
]


@pytest.mark.parametrize("module_name", SUPERSEDED_MODULES)
def test_superseded_split_module_is_not_reintroduced(module_name: str) -> None:
    assert not (RECORDING_PKG / module_name).exists(), (
        f"{module_name} was removed as dead code (zero importers, fully "
        f"superseded by recording_buffer.py / recording_lifecycle.py / "
        f"recording_snapshot.py). Its return means an abandoned create-first "
        f"split was left behind again."
    )


def test_recording_package_modules_all_parse() -> None:
    """Every module in the package must be valid Python.

    A truncated or half-written module fails to parse; this catches that even
    when nothing imports the file yet.
    """
    for path in sorted(RECORDING_PKG.rglob("*.py")):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
