"""Fail-closed guard: the slim core must import without faster_whisper/ctranslate2.

ADR-0025 C7: those libraries live in the pack worker only. This test
runs the slim import closure in a subprocess with both names blocked at
the import system, so any new static import fails loudly instead of
surfacing as a frozen-exe ModuleNotFoundError.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_PROBE = """
import sys

class _Blocker:
    def find_module(self, name, path=None):
        if name == "faster_whisper" or name.startswith("faster_whisper."):
            return self
        if name == "ctranslate2" or name.startswith("ctranslate2."):
            return self
        return None

    def load_module(self, name):
        raise ImportError(f"slim-core probe blocks {name}")

def _is_asr_module(name: str) -> bool:
    return name == "faster_whisper" or name.startswith(
        ("faster_whisper.", "ctranslate2", "ctranslate2.")
    )


sys.meta_path.insert(0, _Blocker())
for stale in [m for m in sys.modules if _is_asr_module(m)]:
    del sys.modules[stale]

import voice_typer.server.worker_backed_asr as shim_mod
import voice_typer.server.worker_path as gate_mod
import voice_typer.server.worker_client as client_mod
import voice_typer.server.worker_pending as pending_mod
import voice_typer.server.worker_relay as relay_mod
import voice_typer.server.worker_streaming as streaming_mod
import voice_typer.server.media_ingest.engine_loop as media_mod
import voice_typer.server.dictation_pipeline.transcribe_step as step_mod
import voice_typer.server.streaming_session_coordinator as coord_mod
from voice_typer.server.asr_registry import AsrBackendRegistry

from unittest.mock import MagicMock

registry = AsrBackendRegistry(MagicMock())
backend = registry.create("whisper", whisper_kwargs={"model_size": "tiny.en"})
assert isinstance(backend, shim_mod.WorkerBackedAsr), type(backend)
assert not hasattr(backend, "transcribe_words")

leaked = sorted(m for m in sys.modules if _is_asr_module(m))
assert leaked == [], f"slim import pulled ASR libs: {leaked}"
print("SLIM-IMPORT-PROBE-OK")
"""


def test_slim_import_closure_has_no_asr_libs():
    """Subprocess probe: slim modules import clean with FW/CT2 blocked."""
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert "SLIM-IMPORT-PROBE-OK" in proc.stdout, f"stdout={proc.stdout[-2000:]}\nstderr={proc.stderr[-2000:]}"
    assert proc.returncode == 0
