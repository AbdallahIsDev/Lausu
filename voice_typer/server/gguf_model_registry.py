"""GGUF model catalogue for the transcribe.cpp runner.

Five production models plus one dev-only tiny test model. Hashes and byte
sizes were read from Hugging Face (API tree + each file's page) on 2026-11-24:
``https://huggingface.co/api/models/<repo>/tree/main`` where ``lfs.oid`` is the
SHA-256 of the file content (https://huggingface.co/docs/hub/git-lfs). No
value here is a placeholder and no model is downloaded by this module.

``tiny`` is DEV ONLY: it must never reach a frozen/production build. Use
``production_models()`` for every user-facing surface and ``available_models()``
for developer tooling; never read ``GGUF_MODELS`` directly outside this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GgufModelSpec:
    """One downloadable GGUF ASR model."""

    model_key: str
    repo_id: str
    filename: str
    sha256: str
    size_bytes: int
    license: str
    family: str  # "whisper", "parakeet", "qwen"
    quantization: str
    dev_only: bool = False


GGUF_MODELS: dict[str, GgufModelSpec] = {
    spec.model_key: spec
    for spec in (
        GgufModelSpec(
            model_key="parakeet",
            repo_id="handy-computer/parakeet-ultra-gguf",
            filename="parakeet-ultra-Q8_0.gguf",
            sha256="007a59761e9258779f189df396b50d12b83bb5b79e66df4b955c230d2f2a0a59",
            size_bytes=740_363_168,
            license="CC-BY-4.0",
            family="parakeet",
            quantization="Q8_0",
        ),
        GgufModelSpec(
            model_key="large-v3-turbo",
            repo_id="handy-computer/whisper-large-v3-turbo-gguf",
            filename="whisper-large-v3-turbo-Q8_0.gguf",
            sha256="257aa7ec9121c22c167d5e2c49e3e76b4ba0e6e27ebc13074eba0a80f8190220",
            size_bytes=886_381_728,
            license="MIT (OpenAI whisper-large-v3-turbo weights)",
            family="whisper",
            quantization="Q8_0",
        ),
        GgufModelSpec(
            model_key="qwen3-1.7b",
            repo_id="handy-computer/Qwen3-ASR-1.7B-gguf",
            filename="Qwen3-ASR-1.7B-Q4_K_M.gguf",
            sha256="b7afe3674f653fa84f712ed2440353c6e7cf7f93697fef76b05a26538b24844e",
            size_bytes=1_319_830_496,
            license="Apache-2.0",
            family="qwen",
            quantization="Q4_K_M",
        ),
        GgufModelSpec(
            model_key="qwen3-0.6b",
            repo_id="handy-computer/Qwen3-ASR-0.6B-gguf",
            filename="Qwen3-ASR-0.6B-Q8_0.gguf",
            sha256="f081b2d5e23bd669d92cc331d722a8a0681943b8e6f34b48996fd5c319b5acd8",
            size_bytes=850_423_456,
            license="Apache-2.0",
            family="qwen",
            quantization="Q8_0",
        ),
        GgufModelSpec(
            model_key="large-v3",
            repo_id="handy-computer/whisper-large-v3-gguf",
            filename="whisper-large-v3-Q6_K.gguf",
            sha256="88e6dc60bd0538da145a50c19f4778e4a106fe28713adeeca43163215ee02805",
            size_bytes=1_297_130_208,
            license="MIT (OpenAI whisper-large-v3 weights)",
            family="whisper",
            quantization="Q6_K",
        ),
        GgufModelSpec(
            model_key="tiny",
            repo_id="handy-computer/whisper-tiny-gguf",
            filename="whisper-tiny-Q8_0.gguf",
            sha256="325b9c7997cd1eff81ef709d55766565e71be696130cc3a3d444713798706834",
            size_bytes=45_981_088,
            license="MIT (OpenAI whisper-tiny weights)",
            family="whisper",
            quantization="Q8_0",
            dev_only=True,
        ),
    )
}

PRODUCTION_MODEL_KEYS = frozenset({"parakeet", "large-v3-turbo", "qwen3-1.7b", "qwen3-0.6b", "large-v3"})
DEFAULT_MODEL_KEY = "large-v3-turbo"


def is_frozen() -> bool:
    from voice_typer.server.media_ingest.ffmpeg_binaries import is_frozen_build

    return is_frozen_build()


def production_models() -> dict[str, GgufModelSpec]:
    """Exactly the five owner models, in every build."""
    return {key: spec for key, spec in GGUF_MODELS.items() if not spec.dev_only}


def available_models() -> dict[str, GgufModelSpec]:
    """Production models plus dev-only models when running from source."""
    if is_frozen():
        return production_models()
    return dict(GGUF_MODELS)


def is_placeholder_hash(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return True
    return any(char not in "0123456789abcdefABCDEF" for char in value)


def is_placeholder_size(value: int | None) -> bool:
    return not isinstance(value, int) or value <= 0


def require_complete_spec(spec: GgufModelSpec) -> None:
    """Fail loudly if an unverified value reaches a real download/build path."""
    if is_placeholder_hash(spec.sha256):
        raise RuntimeError(f"GGUF model {spec.model_key} has an invalid SHA-256.")
    if is_placeholder_size(spec.size_bytes):
        raise RuntimeError(f"GGUF model {spec.model_key} has an invalid size.")
    if spec.dev_only and is_frozen():
        raise RuntimeError(f"GGUF model {spec.model_key} is dev-only.")


def resolve_gguf_spec(model_key: str, *, allow_dev: bool | None = None) -> GgufModelSpec:
    catalogue = available_models() if allow_dev is None else (
        dict(GGUF_MODELS) if allow_dev else production_models()
    )
    spec = catalogue.get(model_key)
    if spec is None:
        raise KeyError(f"No GGUF model registered under {model_key!r}")
    return spec


def all_placeholders() -> tuple[str, ...]:
    """Return any remaining placeholder fields (empty in a complete catalogue)."""
    fields: list[str] = []
    for spec in GGUF_MODELS.values():
        if is_placeholder_hash(spec.sha256):
            fields.append(f"{spec.model_key}:sha256")
        if is_placeholder_size(spec.size_bytes):
            fields.append(f"{spec.model_key}:size_bytes")
    return tuple(fields)
