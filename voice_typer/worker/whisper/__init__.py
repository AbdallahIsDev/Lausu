"""Whisper (faster-whisper) engine, worker-only (ADR-0025 C7).

This package owns every ``faster_whisper``/``ctranslate2`` import in the
tree, so the slim-core sidecar (scanned by
``scripts/slim_core_ml_ratchet_check.py`` over ``voice_typer/server``
only) stays free of both libraries and the Nuitka sidecar build can
exclude them. The slim core reaches whisper exclusively through
``voice_typer.server.worker_backed_asr.WorkerBackedAsr``.
"""

from voice_typer.worker.whisper.engine import TranscriptionEngine

__all__ = ["TranscriptionEngine"]
