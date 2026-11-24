"""GGUF model catalogue for the transcribe.cpp runner.

Models are NOT bundled: each spec names a Hugging Face repo, an exact file and
an expected size/hash. Hashes that cannot be known without downloading the
weights are marked with :data:`PLACEHOLDER_SHA256`; the guard below makes them
fail loudly instead of silently shipping an unverified model. The LOCAL agent
fills them after downloading (ADR-0031 LOCAL AGENT CHECKLIST step 2).

Repos and file names were read from the upstream Hugging Face API with
Firecrawl (https://huggingface.co/handy-computer). Sizes are recorded only when
measured upstream or in the repository; nothing is invented.
"""

from __future__ import annotations

from dataclasses import dataclass

PLACEHOLDER_SHA256 = "FILL_ME_AFTER_DOWNLOADING_THE_REAL_GGUF"
PLACEHOLDER_SIZE = None


@dataclass(frozen=True)
class GgufModelSpec:
    """One downloadable GGUF ASR model."""

    model_key: str
    repo_id: str
    filename: str
    sha256: str
    size_bytes: int | None
    license: str
    quantization: str = "Q8_0"


GGUF_MODELS: dict[str, GgufModelSpec] = {
    spec.model_key: spec
    for spec in (
        GgufModelSpec(
            model_key="tiny",
            repo_id="handy-computer/whisper-tiny-gguf",
            filename="whisper-tiny-Q8_0.gguf",
            sha256=PLACEHOLDER_SHA256,
            size_bytes=45_981_128,
            license="MIT (OpenAI whisper-tiny weights)",
        ),
        GgufModelSpec(
            model_key="large-v3",
            repo_id="handy-computer/whisper-large-v3-gguf",
            filename="whisper-large-v3-Q8_0.gguf",
            sha256=PLACEHOLDER_SHA256,
            size_bytes=PLACEHOLDER_SIZE,
            license="MIT (OpenAI whisper-large-v3 weights)",
        ),
        GgufModelSpec(
            model_key="large-v3-turbo",
            repo_id="handy-computer/whisper-large-v3-turbo-gguf",
            filename="whisper-large-v3-turbo-Q8_0.gguf",
            sha256=PLACEHOLDER_SHA256,
            size_bytes=PLACEHOLDER_SIZE,
            license="MIT (OpenAI whisper-large-v3-turbo weights)",
        ),
        GgufModelSpec(
            model_key="parakeet",
            repo_id="handy-computer/parakeet-ultra-gguf",
            filename="parakeet-ultra-Q8_0.gguf",
            sha256=PLACEHOLDER_SHA256,
            size_bytes=740_363_168,
            license="CC-BY-4.0",
        ),
        GgufModelSpec(
            model_key="qwen3-0.6b",
            repo_id="handy-computer/Qwen3-ASR-0.6B-gguf",
            filename="Qwen3-ASR-0.6B-Q8_0.gguf",
            sha256=PLACEHOLDER_SHA256,
            size_bytes=PLACEHOLDER_SIZE,
            license="Apache-2.0",
        ),
        GgufModelSpec(
            model_key="qwen3-1.7b",
            repo_id="handy-computer/Qwen3-ASR-1.7B-gguf",
            filename="Qwen3-ASR-1.7B-Q8_0.gguf",
            sha256=PLACEHOLDER_SHA256,
            size_bytes=PLACEHOLDER_SIZE,
            license="Apache-2.0",
        ),
    )
}


def is_placeholder_hash(value: str) -> bool:
    """True when the value is not a real 64-hex SHA-256 digest."""
    if not isinstance(value, str) or len(value) != 64:
        return True
    return any(char not in "0123456789abcdefABCDEF" for char in value)


def is_placeholder_size(value: int | None) -> bool:
    return not isinstance(value, int) or value <= 0


def require_complete_spec(spec: GgufModelSpec) -> None:
    """Fail loudly if a placeholder reaches a real download/build path."""
    if is_placeholder_hash(spec.sha256):
        raise RuntimeError(
            f"GGUF model {spec.model_key} still has a placeholder SHA-256. "
            "Download the real file and fill the value before shipping."
        )
    if is_placeholder_size(spec.size_bytes):
        raise RuntimeError(
            f"GGUF model {spec.model_key} still has a placeholder size. "
            "Download the real file and fill the value before shipping."
        )


def resolve_gguf_spec(model_key: str) -> GgufModelSpec:
    spec = GGUF_MODELS.get(model_key)
    if spec is None:
        raise KeyError(f"No GGUF model registered under {model_key!r}")
    return spec


def all_placeholders() -> tuple[str, ...]:
    """Return every placeholder field for the final report."""
    fields: list[str] = []
    for spec in GGUF_MODELS.values():
        if is_placeholder_hash(spec.sha256):
            fields.append(f"{spec.model_key}:sha256")
        if is_placeholder_size(spec.size_bytes):
            fields.append(f"{spec.model_key}:size_bytes")
    return tuple(fields)
