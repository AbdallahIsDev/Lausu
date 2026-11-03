"""Local ONNX text provider: no network, no key, chunked polish.

The model graph, chat template and KV-cache contract are documented in
``docs/code-notes/local-onnx-llm.md``; the loop keeps the cache on the device
(``session.io_binding()`` + device ``OrtValue``) because a numpy round-trip
collapses decoding to ~3 tok/s at a 3k context.
"""

from __future__ import annotations

from voice_typer.server.model_providers.local_onnx.chunked import polish_chunked
from voice_typer.server.model_providers.local_onnx.chunker import (
    MAX_CHUNK_WORDS,
    MIN_CHUNK_WORDS,
    chunk_sentences,
)
from voice_typer.server.model_providers.local_onnx.client import LocalOnnxLlmClient
from voice_typer.server.model_providers.local_onnx.models import (
    LocalOnnxModel,
    list_installed_models,
    load_model,
    verify_manifest,
)

__all__ = [
    "MAX_CHUNK_WORDS",
    "MIN_CHUNK_WORDS",
    "LocalOnnxLlmClient",
    "LocalOnnxModel",
    "chunk_sentences",
    "list_installed_models",
    "load_model",
    "polish_chunked",
    "verify_manifest",
]
