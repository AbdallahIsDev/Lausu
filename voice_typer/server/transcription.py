"""Transcription facade over ASR engines.

C7: the faster-whisper ``TranscriptionEngine`` moved to
``voice_typer.worker.whisper`` (the slim core must not import
``faster_whisper``/``ctranslate2``). What stays here are the
engine-agnostic helpers (download gate, beam default, re-exports) that
other slim modules import.
"""

from __future__ import annotations

import logging
import threading

from voice_typer.server._lazy_import import lazy_module
from voice_typer.server.asr_errors import (
    ConsentRequiredError,  # noqa: F401  # re-exported for backward compat
    ModelIntegrityError,  # noqa: F401  # re-exported for backward compat
)

# PERF-COLDSTART-001: defer numpy (~250-335ms) to first use via lazy proxy.
from voice_typer.server.asr_utils import (  # noqa: F401
    _check_disk_space_for_download,
    _download_with_retry,
    _require_huggingface_consent,
    cleanup_hf_cache_dir,
    is_oom_error,
    release_gpu_memory,
)

np = lazy_module("numpy")

# Shared ASR helpers live in ``asr_utils``; re-exported here for compat.

# ``TranscriberProtocol`` lives in ``transcription_load.py``; re-exported for identity parity.
from voice_typer.server.transcription_load import TranscriberProtocol  # noqa: F401, E402

# Segment-decode body lives in ``transcription_result``; historical alias kept.

log = logging.getLogger(__name__)


# re-exported from ``voice_typer.server._audio_constants`` for
_nvidia_dll_path_handles: list[object] = []


# ``_MODEL_SIZE_MB`` + ``_DISK_SPACE_MARGIN_MB``,


# NVIDIA CUDA DLL path setup (Windows-only, gated by ``is_windows()``
from voice_typer.server.nvidia_dll_paths import (  # noqa: E402, F401
    _configure_nvidia_dll_paths,
    _configure_nvidia_dll_paths_locked,
    _cuda_runtime_available,
    _free_nvidia_dll_path_handles,
    _NvidiaDllPathManager,
)

_nvidia_dll_paths_configured = False
# RACE-029: module-level lock to serialize _configure_nvidia_dll_paths()
_nvidia_config_lock = threading.Lock()

# Singleton manager that encapsulates operations on the three
_nvidia_dll_paths = _NvidiaDllPathManager()


# Wide-beam default applied automatically on CUDA for non-tiny models.
AUTO_CUDA_BEAM_SIZE = 5


def _auto_beam_size(model_size: str, device: str) -> int:
    """Beam width used when the user left it on auto.

    Returns the wide accuracy-biased beam only for non-tiny models on a
    """
    if device != "cuda":
        return 1
    if str(model_size).lower().startswith("tiny"):
        return 1
    return AUTO_CUDA_BEAM_SIZE


# Back-compat re-export: the canonical body lives in
from voice_typer.server.transcription_result import (  # noqa: E402, F401
    build_quality_summary,
)
