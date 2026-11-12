// Measured-skeleton sample for the Models page. While `config` is null
// the <Skeleton> measures this sample's render, so it must carry every
// field the panels read: the config (tiny active, so the active card
// shape measures), the model list, and a catalog entry per model.

import { SAMPLE_CONFIG } from "@/components/skullet/sampleConfig";
import {
	INITIAL_MODELS,
	type ModelInfo,
	type ModelMetadata,
} from "@/lib/utils/modelCatalog";
import type { LausuConfig } from "@/types/config";

// Typical active local-model config: the sample measures the
// "tiny selected + downloaded" card row the page normally shows.
export const MODELS_SAMPLE_CONFIG: LausuConfig = {
	...SAMPLE_CONFIG,
	model_size: "tiny",
	asr_backend: "whisper",
	cloud_provider: "",
	cloud_model: "",
};

// The bundled list with tiny marked downloaded/active, matching the
// state the sample config above describes.
export const SAMPLE_MODELS: ModelInfo[] = INITIAL_MODELS.map((model) => ({
	...model,
	downloaded: model.name === "tiny",
	isActive: model.name === "tiny",
}));

// One entry per bundled model: LocalModelsPanel reads each variant's
// entry for its metadata line, so every name must resolve. Values mirror
// `MODEL_REGISTRY` in `server/model_registry.py` (sizes, VRAM, WER, repo
// ids, descriptions): the earlier sample carried stale numbers and
// non-existent repos, so the unseen skeleton measured different text
// than the real catalog rendered.
export const SAMPLE_MODEL_CATALOG: Record<string, ModelMetadata> = {
	tiny: {
		name: "tiny",
		download_size_mb: 75,
		required_vram_mb: 512,
		backend: "whisper",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: true,
		supports_language_detection: true,
		description: "Fastest multilingual model. Low accuracy, good for testing.",
		repo_id: "Systran/faster-whisper-tiny",
		is_distilled: false,
		speed_rating: "fast",
		accuracy_rating: "low",
		wer: 12.3,
	},
	"large-v3": {
		name: "large-v3",
		download_size_mb: 3000,
		required_vram_mb: 3072,
		backend: "whisper",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: true,
		supports_language_detection: true,
		description:
			"Highest-accuracy Whisper model. Slow on CPU; GPU strongly recommended.",
		repo_id: "Systran/faster-whisper-large-v3",
		is_distilled: false,
		speed_rating: "slow",
		accuracy_rating: "high",
		wer: 5.0,
	},
	"large-v3-turbo": {
		name: "large-v3-turbo",
		download_size_mb: 1618,
		required_vram_mb: 2000,
		backend: "whisper",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: true,
		supports_language_detection: true,
		description:
			"Turbo model, near-large-v3 accuracy at 8x speed. Recommended for most users.",
		repo_id: "dropbox-dash/faster-whisper-large-v3-turbo",
		is_distilled: false,
		speed_rating: "fast",
		accuracy_rating: "high",
		wer: 5.5,
	},
	"qwen3-1.7b": {
		name: "qwen3-1.7b",
		display_name: "qwen3 1.7B",
		download_size_mb: 3943,
		required_vram_mb: 4096,
		backend: "qwen",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: false,
		supports_language_detection: true,
		description:
			"Qwen3-ASR 1.7B (ONNX int4). Multilingual ASR without PyTorch.",
		repo_id: "andrewleech/qwen3-asr-1.7b-onnx",
		is_distilled: false,
		speed_rating: "medium",
		accuracy_rating: "high",
		wer: 5.76,
	},
	"qwen3-0.6b": {
		name: "qwen3-0.6b",
		display_name: "qwen3 0.6B",
		download_size_mb: 1940,
		required_vram_mb: 2048,
		backend: "qwen",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: false,
		supports_language_detection: true,
		description:
			"Qwen3-ASR 0.6B (ONNX int4). Smaller, faster multilingual ASR without PyTorch.",
		repo_id: "andrewleech/qwen3-asr-0.6b-onnx",
		is_distilled: false,
		speed_rating: "fast",
		accuracy_rating: "high",
		wer: null,
	},
	parakeet: {
		name: "parakeet",
		display_name: "Parakeet Ultra",
		download_size_mb: 670,
		required_vram_mb: 2048,
		backend: "parakeet",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: false,
		supports_language_detection: true,
		description:
			"Parakeet Ultra (NVIDIA Parakeet TDT 0.6b, post-trained by Moondream). ONNX int8, 25 languages.",
		repo_id: "Masterx/parakeet-tdt-0.6b-ultra-onnx",
		is_distilled: false,
		speed_rating: "fast",
		accuracy_rating: "high",
		wer: 5.8,
	},
};
