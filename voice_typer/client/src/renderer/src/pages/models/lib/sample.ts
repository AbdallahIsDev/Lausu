// Measured-skeleton sample for the Models page. While `config` is null
// the <Skeleton> measures this sample's render, so it must carry every
// field the panels read: the config (a production model active, so the
// active card shape measures), the model list, and a catalog entry per model.

import { SAMPLE_CONFIG } from "@/components/skullet/sampleConfig";
import {
	INITIAL_MODELS,
	type ModelInfo,
	type ModelMetadata,
} from "@/lib/utils/modelCatalog";
import type { LausuConfig } from "@/types/config";

// Typical active local-model config: the sample measures the
// "large-v3-turbo selected + downloaded" card row the page normally shows.
export const MODELS_SAMPLE_CONFIG: LausuConfig = {
	...SAMPLE_CONFIG,
	model_size: "large-v3-turbo",
	asr_backend: "whisper",
	cloud_provider: "",
	cloud_model: "",
};

// The bundled list with the configured production model marked
// downloaded/active, matching the state the sample config describes.
export const SAMPLE_MODELS: ModelInfo[] = INITIAL_MODELS.map((model) => ({
	...model,
	downloaded: model.name === "large-v3-turbo",
	isActive: model.name === "large-v3-turbo",
}));

// One entry per bundled model: LocalModelsPanel reads each variant's
// entry for its metadata line, so every name must resolve. Values mirror
// the single catalogue in `server/gguf_model_registry.py` (sizes, VRAM, WER, repo
// ids, descriptions): the earlier sample carried stale numbers and
// non-existent repos, so the unseen skeleton measured different text
// than the real catalog rendered.
export const SAMPLE_MODEL_CATALOG: Record<string, ModelMetadata> = {
	"large-v3": {
		name: "large-v3",
		download_size_mb: 1297,
		required_vram_mb: 3072,
		backend: "whisper",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: true,
		supports_language_detection: true,
		description:
			"Highest-accuracy Whisper model. Slow on CPU; GPU strongly recommended.",
		repo_id: "handy-computer/whisper-large-v3-gguf",
		is_distilled: false,
		speed_rating: "slow",
		accuracy_rating: "high",
		wer: 5.0,
	},
	"large-v3-turbo": {
		name: "large-v3-turbo",
		download_size_mb: 886,
		required_vram_mb: 2000,
		backend: "whisper",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: true,
		supports_language_detection: true,
		description:
			"Turbo model, near-large-v3 accuracy at 8x speed. Recommended for most users.",
		repo_id: "handy-computer/whisper-large-v3-turbo-gguf",
		is_distilled: false,
		speed_rating: "fast",
		accuracy_rating: "high",
		wer: 5.5,
	},
	"qwen3-1.7b": {
		name: "qwen3-1.7b",
		display_name: "qwen3 1.7B",
		download_size_mb: 1319,
		required_vram_mb: 4096,
		backend: "qwen",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: false,
		supports_language_detection: true,
		description:
			"Qwen3-ASR 1.7B GGUF Q4_K_M. Multilingual ASR in one local model.",
		repo_id: "handy-computer/Qwen3-ASR-1.7B-gguf",
		is_distilled: false,
		speed_rating: "medium",
		accuracy_rating: "high",
		wer: 5.76,
	},
	"qwen3-0.6b": {
		name: "qwen3-0.6b",
		display_name: "qwen3 0.6B",
		download_size_mb: 850,
		required_vram_mb: 2048,
		backend: "qwen",
		multilingual: true,
		supported_languages: null,
		accepts_language_hint: false,
		supports_language_detection: true,
		description: "Qwen3-ASR 0.6B GGUF Q8_0. Smaller, faster multilingual ASR.",
		repo_id: "handy-computer/Qwen3-ASR-0.6B-gguf",
		is_distilled: false,
		speed_rating: "fast",
		accuracy_rating: "high",
		wer: null,
	},
	parakeet: {
		name: "parakeet",
		display_name: "Parakeet Ultra",
		download_size_mb: 740,
		required_vram_mb: 2048,
		backend: "parakeet",
		multilingual: true,
		supported_languages: [
			"bg",
			"hr",
			"cs",
			"da",
			"nl",
			"en",
			"et",
			"fi",
			"fr",
			"de",
			"el",
			"hu",
			"it",
			"lv",
			"lt",
			"mt",
			"pl",
			"pt",
			"ro",
			"sk",
			"sl",
			"es",
			"sv",
			"ru",
			"uk",
		],
		accepts_language_hint: false,
		supports_language_detection: true,
		description:
			"Parakeet Ultra (NVIDIA Parakeet TDT 0.6b). GGUF Q8_0, 25 languages.",
		repo_id: "handy-computer/parakeet-ultra-gguf",
		is_distilled: false,
		speed_rating: "fast",
		accuracy_rating: "high",
		wer: 5.8,
	},
};
