"""The single model registry: GGUF weights, metadata and build rules.

Five production models plus one dev-only tiny test model. Hashes and byte
sizes were read from Hugging Face (API tree + each file's page) on 2026-11-24:
``https://huggingface.co/api/models/<repo>/tree/main`` where ``lfs.oid`` is the
SHA-256 of the file content (https://huggingface.co/docs/hub/git-lfs). No
value here is a placeholder and no model is downloaded by this module.

``tiny`` is DEV ONLY: it must never reach a frozen/production build. Use
``production_models()`` for every user-facing surface and ``available_models()``
for developer tooling. No other module reads ``GGUF_MODELS`` directly.

The legacy ``ModelMetadata`` shape (sizes, VRAM, WER, display names, language
support) lives here too, derived from the same catalogue, so there is exactly
one authority for what a model is and whether it may be offered.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from types import MappingProxyType

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
NO_MODEL_SIZE: str = ""

# Keys and repo ids from older builds. Legacy repo ids are model ids that were
# once written to ``config.model_size`` by older code paths; a frozen build
# maps all of them to the production default, never to a dev-only model.
LEGACY_MODEL_ALIASES: dict[str, str] = {"qwen": "qwen3-1.7b", "qwen-0.6b": "qwen3-0.6b"}
LEGACY_REPO_ID_KEYS: dict[str, str] = {
    "Systran/faster-whisper-tiny": "tiny",
    "Systran/faster-whisper-large-v3": "large-v3",
    "dropbox-dash/faster-whisper-large-v3-turbo": "large-v3-turbo",
    "Masterx/parakeet-tdt-0.6b-ultra-onnx": "parakeet",
    "andrewleech/qwen3-asr-1.7b-onnx": "qwen3-1.7b",
    "andrewleech/qwen3-asr-0.6b-onnx": "qwen3-0.6b",
}


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


def default_model_size_for_build(*, frozen: bool | None = None) -> str:
    """Frozen builds always default to a shipped model; source keeps no-model."""
    frozen = is_frozen() if frozen is None else frozen
    return DEFAULT_MODEL_KEY if frozen else NO_MODEL_SIZE


# Canonical config default. Source builds keep the "no model selected"
# sentinel; frozen builds can only start with a production model.
DEFAULT_MODEL_SIZE: str = default_model_size_for_build()


def normalize_model_key(value: object, *, frozen: bool | None = None) -> str:
    """Resolve a stored/requested model id against the build's catalogue."""
    frozen = is_frozen() if frozen is None else frozen
    key = value if isinstance(value, str) else ""
    key = LEGACY_MODEL_ALIASES.get(key, key)
    key = LEGACY_REPO_ID_KEYS.get(key, key)
    catalogue = production_models() if frozen else available_models()
    if key in catalogue:
        return key
    if not frozen and key == NO_MODEL_SIZE:
        return NO_MODEL_SIZE
    return DEFAULT_MODEL_KEY if frozen else NO_MODEL_SIZE


def is_dev_only_model_key(model_key: str) -> bool:
    spec = GGUF_MODELS.get(model_key)
    return bool(spec and spec.dev_only)


def require_allowed_model_key(model_key: str) -> str:
    """Raise for unknown/dev-only keys instead of letting them reach a download."""
    key = normalize_model_key(model_key)
    if key != model_key:
        raise KeyError(f"Model {model_key!r} is not selectable in this build")
    if key == NO_MODEL_SIZE:
        raise KeyError("No model is selected")
    return key


@dataclass(frozen=True)
class ModelMetadata:
    """Rich metadata for a single ASR model variant (IPC payload shape)."""

    name: str
    download_size_mb: int
    required_vram_mb: int
    backend: str
    multilingual: bool
    supported_languages: list[str] | None  # None = all languages
    description: str
    repo_id: str
    is_distilled: bool = False
    speed_rating: str = "medium"  # "fast", "medium", "slow"
    accuracy_rating: str = "high"  # "low", "medium", "high"
    wer: float | None = None
    network_behavior: str = "local-only"
    display_name: str | None = None
    accepts_language_hint: bool = True
    supports_language_detection: bool = True

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict for IPC transport."""
        return asdict(self)


def _model_languages(family: str) -> list[str] | None:
    if family == "parakeet":
        from voice_typer.server.model_language_support import PARAKEET_LANGUAGES

        return list(PARAKEET_LANGUAGES)
    if family == "qwen":
        from voice_typer.server.model_language_support import QWEN3_LANGUAGES

        return list(QWEN3_LANGUAGES)
    return None


_METADATA_BY_KEY: dict[str, ModelMetadata] = {
    meta.name: meta
    for meta in (
        ModelMetadata(
            name="tiny",
            download_size_mb=75,
            required_vram_mb=512,
            backend="whisper",
            multilingual=True,
            supported_languages=None,
            accepts_language_hint=True,
            supports_language_detection=True,
            description="Fastest multilingual model. Low accuracy, good for testing.",
            network_behavior="downloads-on-first-use-consent-gated",
            repo_id="Systran/faster-whisper-tiny",
            speed_rating="fast",
            accuracy_rating="low",
            wer=12.3,
        ),
        ModelMetadata(
            name="large-v3",
            download_size_mb=3000,
            required_vram_mb=3072,
            backend="whisper",
            multilingual=True,
            supported_languages=None,
            accepts_language_hint=True,
            supports_language_detection=True,
            description="Highest-accuracy Whisper model. Slow on CPU; GPU strongly recommended.",
            network_behavior="downloads-on-first-use-consent-gated",
            repo_id="Systran/faster-whisper-large-v3",
            speed_rating="slow",
            accuracy_rating="high",
            wer=5.0,
        ),
        ModelMetadata(
            name="large-v3-turbo",
            download_size_mb=1618,
            required_vram_mb=2000,
            backend="whisper",
            multilingual=True,
            supported_languages=None,
            accepts_language_hint=True,
            supports_language_detection=True,
            description="Turbo model, near-large-v3 accuracy at 8x speed. Recommended for most users.",
            network_behavior="downloads-on-first-use-consent-gated",
            repo_id="dropbox-dash/faster-whisper-large-v3-turbo",
            speed_rating="fast",
            accuracy_rating="high",
            wer=5.5,
        ),
        ModelMetadata(
            name="parakeet",
            display_name="Parakeet Ultra",
            download_size_mb=670,
            required_vram_mb=2048,
            backend="parakeet",
            multilingual=True,
            supported_languages=_model_languages("parakeet"),
            accepts_language_hint=False,
            supports_language_detection=True,
            description=(
                "Parakeet Ultra (NVIDIA Parakeet TDT 0.6b, post-trained by Moondream). "
                "ONNX int8, 25 languages."
            ),
            network_behavior="downloads-on-first-use-consent-gated",
            repo_id="Masterx/parakeet-tdt-0.6b-ultra-onnx",
            speed_rating="fast",
            accuracy_rating="high",
            wer=5.8,
        ),
        ModelMetadata(
            name="qwen3-1.7b",
            display_name="qwen3 1.7B",
            download_size_mb=3943,
            required_vram_mb=4096,
            backend="qwen",
            multilingual=True,
            supported_languages=_model_languages("qwen"),
            accepts_language_hint=False,
            supports_language_detection=True,
            description="Qwen3-ASR 1.7B (ONNX int4). Multilingual ASR without PyTorch.",
            network_behavior="downloads-on-first-use-consent-gated",
            repo_id="andrewleech/qwen3-asr-1.7b-onnx",
            speed_rating="medium",
            accuracy_rating="high",
            wer=5.76,
        ),
        ModelMetadata(
            name="qwen3-0.6b",
            display_name="qwen3 0.6B",
            download_size_mb=1940,
            required_vram_mb=2048,
            backend="qwen",
            multilingual=True,
            supported_languages=_model_languages("qwen"),
            accepts_language_hint=False,
            supports_language_detection=True,
            description="Qwen3-ASR 0.6B (ONNX int4). Smaller, faster multilingual ASR without PyTorch.",
            network_behavior="downloads-on-first-use-consent-gated",
            repo_id="andrewleech/qwen3-asr-0.6b-onnx",
            speed_rating="fast",
            accuracy_rating="high",
        ),
    )
}


def available_model_metadata() -> dict[str, ModelMetadata]:
    """Metadata for exactly the models this build may offer."""
    return {key: _METADATA_BY_KEY[key] for key in available_models() if key in _METADATA_BY_KEY}


MODEL_REGISTRY = MappingProxyType(available_model_metadata())


def get_model_metadata(model_size: str) -> ModelMetadata | None:
    """Return metadata for ``model_size`` or ``None`` if unknown/not selectable."""
    key = LEGACY_MODEL_ALIASES.get(model_size, model_size)
    if key not in available_models():
        return None
    return _METADATA_BY_KEY.get(key)


def get_all_models() -> list[ModelMetadata]:
    """All selectable models, in catalogue order."""
    return list(available_model_metadata().values())


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


__all__ = [
    "DEFAULT_MODEL_KEY",
    "DEFAULT_MODEL_SIZE",
    "GGUF_MODELS",
    "LEGACY_MODEL_ALIASES",
    "LEGACY_REPO_ID_KEYS",
    "MODEL_REGISTRY",
    "NO_MODEL_SIZE",
    "PRODUCTION_MODEL_KEYS",
    "GgufModelSpec",
    "ModelMetadata",
    "all_placeholders",
    "available_model_metadata",
    "available_models",
    "default_model_size_for_build",
    "get_all_models",
    "get_model_metadata",
    "is_dev_only_model_key",
    "is_frozen",
    "is_placeholder_hash",
    "is_placeholder_size",
    "normalize_model_key",
    "production_models",
    "require_allowed_model_key",
    "require_complete_spec",
    "resolve_gguf_spec",
]
