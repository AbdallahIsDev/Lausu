"""Legacy model ids written by older builds, migrated to current GGUF keys.

This module has NO imports on purpose: the security manifest loader needs
these mappings during package initialisation, where importing the full model
registry would close a circular import through media_ingest/ipc/config
sanitizer. Keep the data here and import from here in low-level modules.
"""

from __future__ import annotations

# Old ``config.model_size`` values -> current registry keys.
LEGACY_MODEL_ALIASES: dict[str, str] = {"qwen": "qwen3-1.7b", "qwen-0.6b": "qwen3-0.6b"}

# Old Hugging Face repo ids -> current registry keys (migration only).
LEGACY_REPO_ID_KEYS: dict[str, str] = {
    "Systran/faster-whisper-tiny": "tiny",
    "Systran/faster-whisper-large-v3": "large-v3",
    "dropbox-dash/faster-whisper-large-v3-turbo": "large-v3-turbo",
    "Masterx/parakeet-tdt-0.6b-ultra-onnx": "parakeet",
    "andrewleech/qwen3-asr-1.7b-onnx": "qwen3-1.7b",
    "andrewleech/qwen3-asr-0.6b-onnx": "qwen3-0.6b",
}

__all__ = ["LEGACY_MODEL_ALIASES", "LEGACY_REPO_ID_KEYS"]
