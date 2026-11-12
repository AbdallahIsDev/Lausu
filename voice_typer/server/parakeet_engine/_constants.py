"""Parakeet engine constants (verbatim from the original module)."""

from __future__ import annotations

from voice_typer.server.asr_utils import (
    MAX_BOUNDARY_SKIP_WORDS as _MAX_BOUNDARY_SKIP_WORDS,  # noqa: F401, re-exported alias
    NON_LATIN_RATIO_LIMIT as _NON_LATIN_RATIO_LIMIT,  # noqa: F401, re-exported alias
    OVERLAP_DEDUP_WINDOW as _OVERLAP_DEDUP_WINDOW,  # noqa: F401, re-exported alias
)

# The three imports above are the backward-compat re-export surface of


# (``_NON_LATIN_RATIO_LIMIT``: the maximum allowed ratio of non-Latin-

# ONNX export of the Moondream Parakeet Ultra post-train (base: NVIDIA
# parakeet-tdt-0.6b-v3). int8 = ORT quantize_dynamic, per-tensor QUInt8;
# graphs are the istupakov v3 export with Ultra weights substituted.
_PARAKERT_ONNX_REPO_ID = "Masterx/parakeet-tdt-0.6b-ultra-onnx"
_PARAKERT_ONNX_CACHE_DIR = f"models--{_PARAKERT_ONNX_REPO_ID.replace('/', '--')}"

# onnx-asr TYPE name (NOT a repo name). ``nemo-conformer-tdt`` selects
_PARAKERT_ONNX_MODEL_NAME = "nemo-conformer-tdt"

# Selects the ``.int8.`` variant files inside the repo (onnx-asr 0.12.0
_PARAKERT_QUANTIZATION = "int8"

# int8 encoder (652 MB) + decoder_joint (18 MB), for MB/s read-speed logging.
_PARAKERT_WEIGHTS_MB = 670

# Parakeet's Conformer encoder has a practical limit of ~30s of audio.
_CHUNK_SECONDS = 25
_CHUNK_OVERLAP_SECONDS = 3

# Backward-compat re-exports of the merge-chunk constants. The canonical
