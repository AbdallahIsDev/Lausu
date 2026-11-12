# ruff: noqa: A001, A002, N802, N803, N816
# RW-6 (pyrefly): stub for the `onnx_asr` package (ONNX ASR engine).
#
# `onnx_asr` is an optional pip dependency used by
# `voice_typer/server/parakeet_engine.py`. It is NOT installed on the
# CI runner (or in most dev environments, only users who want the
# ONNX Parakeet backend install it). The runtime code wraps every
# `import onnx_asr` in a lazy `_ensure_imports()` call guarded by
# `try/except ImportError`, so this stub only needs to declare the
# small import surface actually used:
#
#   - `onnx_asr.load_model(model, path=None, *, quantization=None,
#     providers=None, ...)` -> TextResultsAsrAdapter
#   - `adapter.recognize(audio, sample_rate=16000)` -> str
#
# NOTE (verified against the onnx-asr 0.12.0 wheel AND the `main`
# branch on 2026-08-15): onnx-asr exports ONLY `load_model` and
# `load_vad` (`__init__.py: __all__ = ["load_model", "load_vad"]`).
# There is NO `onnx_asr.Model` class in any release. Earlier drafts
# of this stub (and parakeet_engine.py) referenced a class-based
# `Model(...)` API that does not exist; calling it raises
# AttributeError at runtime. `load_model` is the canonical entry
# point.
#
# `load_model(model, ...)` accepts either a short model name (e.g.
# `nemo-parakeet-tdt-0.6b-v3`), a full HuggingFace repo id (a string
# containing "/"), or a TYPE name (`nemo-conformer-tdt` etc.) when a
# local `path` is given. `path` points at a directory containing the
# model files; when set, the resolver loads entirely from disk
# (offline) and requires config.json plus the exact
# `encoder-model.<quant>.onnx` / `decoder_joint-model.<quant>.onnx`
# filenames `_get_model_files` builds from `quantization` (glob with
# the literal suffix, not a wildcard class). The Ultra int8 export
# ships those exact files.
#
# All symbols are typed `Any` because the surrounding code is wrapped
# in `try/except ImportError` and we do not need pyrefly to verify the
# onnx_asr call sites.
from typing import Any

def load_model(
    model: str,
    path: str | None = None,
    *,
    quantization: str | None = ...,
    sess_options: Any = ...,
    providers: list[str] | None = ...,
    provider_options: list[dict[Any, Any]] | None = ...,
    cpu_preprocessing: bool | None = ...,
    asr_config: dict[Any, Any] | None = ...,
    preprocessor_config: dict[Any, Any] | None = ...,
    resampler_config: dict[Any, Any] | None = ...,
) -> Any: ...
def load_vad(
    model: str = ...,
    path: str | None = ...,
    *,
    quantization: str | None = ...,
    sess_options: Any = ...,
    providers: list[str] | None = ...,
    provider_options: list[dict[Any, Any]] | None = ...,
) -> Any: ...

__all__: list[str] = ["load_model", "load_vad"]
