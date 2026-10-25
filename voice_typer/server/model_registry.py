"""Metadata registry for all supported ASR models."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelMetadata:
    """Rich metadata for a single ASR model variant."""

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
    # WER (%) per entry (lower is better). Every entry carries a
    # real-world representative average — see each entry's source note.
    wer: float | None = None
    # declares what network activity the model requires, so the
    network_behavior: str = "local-only"
    # User-facing display name shown on the model card. ``None`` means
    display_name: str | None = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict for IPC transport."""
        return asdict(self)


# Order matters for the Models page: entries appear in this order in

# Sentinel for "no model selected": the config's ``model_size`` can be
NO_MODEL_SIZE: str = ""

# The canonical DEFAULT model size. THIS IS DELIBERATELY "no model
DEFAULT_MODEL_SIZE: str = NO_MODEL_SIZE

MODEL_REGISTRY: dict[str, ModelMetadata] = {
    "tiny": ModelMetadata(
        name="tiny",
        download_size_mb=75,
        required_vram_mb=512,
        backend="whisper",
        multilingual=True,
        supported_languages=None,
        description="Fastest multilingual model. Low accuracy, good for testing.",
        network_behavior="downloads-on-first-use-consent-gated",
        repo_id="Systran/faster-whisper-tiny",
        speed_rating="fast",
        accuracy_rating="low",
        # WER 12.3% real-world representative: official HF model-index
        # eval (openai/whisper-tiny) averages clean 7.54% + other 17.15%.
        wer=12.3,
    ),
    # ``large-v3``: highest-accuracy multilingual Whisper. Restored
    "large-v3": ModelMetadata(
        name="large-v3",
        download_size_mb=3000,
        # Measured 2.88 GB weights + runtime ≈3 GB on an 8 GB card.
        required_vram_mb=3072,
        backend="whisper",
        multilingual=True,
        supported_languages=None,
        description="Highest-accuracy Whisper model. Slow on CPU; GPU strongly recommended.",
        network_behavior="downloads-on-first-use-consent-gated",
        repo_id="Systran/faster-whisper-large-v3",
        speed_rating="slow",
        accuracy_rating="high",
        # WER 5.0% real-world representative (test-clean lab ~2% understates
        # everyday errors 2-3x): Coval live-STT 4.8% (Sep 2026), clean/noisy
        # 2.1%/5.2%, OpenASR leaderboard mean ~6%.
        wer=5.0,
    ),
    # ``large-v3-turbo`` is OpenAI's 2024 fast multilingual model:
    "large-v3-turbo": ModelMetadata(
        name="large-v3-turbo",
        # Real fp16 model.bin at the pinned revision is 1,617,884,929 bytes
        download_size_mb=1618,
        required_vram_mb=2000,
        backend="whisper",
        multilingual=True,
        supported_languages=None,
        description="Turbo model, near-large-v3 accuracy at 8x speed. Recommended for most users.",
        network_behavior="downloads-on-first-use-consent-gated",
        # Canonical HF org (renamed from mobiuslabsgmbh; faster-whisper
        # 1.2.1's _MODELS alias still points at the old slug).
        repo_id="dropbox-dash/faster-whisper-large-v3-turbo",
        speed_rating="fast",
        accuracy_rating="high",
        # WER 5.5% real-world representative: 0.5 above large-v3's 5.0,
        # preserving the measured turbo gap (OpenASR means 7.83 vs 7.44).
        wer=5.5,
    ),
    # added to registry so get_model_status() can resolve the
    "parakeet": ModelMetadata(
        name="parakeet",
        display_name="Parakeet-TDT-0.6b-V3",
        download_size_mb=1275,
        required_vram_mb=3072,
        backend="parakeet",
        multilingual=True,
        supported_languages=None,
        description="NVIDIA Parakeet TDT 0.6b v3. ONNX fp16 export (grikdotnet), fast CPU/GPU ASR without PyTorch.",
        network_behavior="downloads-on-first-use-consent-gated",
        repo_id="grikdotnet/parakeet-tdt-0.6b-fp16",
        speed_rating="fast",
        accuracy_rating="high",
        # WER 6.34% real-world representative: official NVIDIA model-card
        # OpenASR average (LS clean 1.93% understates everyday errors).
        wer=6.34,
    ),
    # Qwen3-ASR ships as two sizes with separate ONNX exports.
    "qwen3-1.7b": ModelMetadata(
        name="qwen3-1.7b",
        display_name="qwen3 1.7B",
        # 3,942.3 MiB of int4 ONNX files at the pinned revision.
        download_size_mb=3943,
        required_vram_mb=4096,
        backend="qwen",
        multilingual=True,
        supported_languages=None,
        description="Qwen3-ASR 1.7B (ONNX int4). Multilingual ASR without PyTorch.",
        network_behavior="downloads-on-first-use-consent-gated",
        repo_id="andrewleech/qwen3-asr-1.7b-onnx",
        speed_rating="medium",
        accuracy_rating="high",
        # WER 5.76% real-world representative: OpenASR average
        # (LS clean 1.63% understates everyday errors).
        wer=5.76,
    ),
    "qwen3-0.6b": ModelMetadata(
        name="qwen3-0.6b",
        display_name="qwen3 0.6B",
        # 1,940.1 MiB of int4 ONNX files at the pinned revision.
        download_size_mb=1940,
        required_vram_mb=2048,
        backend="qwen",
        multilingual=True,
        supported_languages=None,
        description="Qwen3-ASR 0.6B (ONNX int4). Smaller, faster multilingual ASR without PyTorch.",
        network_behavior="downloads-on-first-use-consent-gated",
        repo_id="andrewleech/qwen3-asr-0.6b-onnx",
        speed_rating="fast",
        accuracy_rating="high",
    ),
}


#: Registry keys this app used before the qwen3 rename. A ``config.json``
#: written by an older build carries one of these, the schema v6 migration
#: rewrites it on load, and lookups still resolve it if the migration is
#: skipped (unreadable ``schema_version``).
LEGACY_MODEL_ALIASES: dict[str, str] = {"qwen": "qwen3-1.7b", "qwen-0.6b": "qwen3-0.6b"}


def get_model_metadata(model_size: str) -> ModelMetadata | None:
    """Return metadata for ``model_size`` or ``None`` if unknown."""
    meta = MODEL_REGISTRY.get(model_size)
    if meta is not None:
        return meta
    return MODEL_REGISTRY.get(LEGACY_MODEL_ALIASES.get(model_size, ""))


def get_all_models() -> list[ModelMetadata]:
    """Return all registered models in registry order."""
    return list(MODEL_REGISTRY.values())


__all__ = [
    "ModelMetadata",
    "MODEL_REGISTRY",
    "DEFAULT_MODEL_SIZE",
    "LEGACY_MODEL_ALIASES",
    "NO_MODEL_SIZE",
    "get_model_metadata",
    "get_all_models",
]
