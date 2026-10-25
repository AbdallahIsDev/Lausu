/**
 * Local model catalogue: the bundled model list, its metadata and family
 * shapes, and the download-side predicates (free disk space, HF consent).
 *
 * Split out of `lib/utils/models.ts`; the barrel (`./models`) re-exports
 * every symbol below, so existing import paths keep resolving.
 */

import type { DiskInfo } from "@/types/ipc";
import { formatModelDisplayName } from "./format";

// but `lib/` must never import from `pages/` (inverted layering; this
// The renderer default must match the backend's canonical default
export const MODEL_DEFAULT = "";

export interface ModelInfo {
	name: string;
	size: string;
	speed: string;
	backend: string;
	downloaded: boolean;
	depsOk: boolean;
	isActive: boolean;
	/**
	 * User-facing name for surfaces with no backend metadata at hand
	 * (About rows, Home share image). The Models page prefers the registry
	 * `display_name`; this mirrors it, and `models-display-names.test.ts`
	 * pins the two against `model_registry.py`.
	 */
	displayName?: string;
	// (`downloaded`). Do NOT re-add an always-available concept without
	/**
	 * Model requires extra system dependencies that
	 * can be installed via a dedicated action (e.g. Parakeet's torch
	 */
	depsInstallable?: boolean;
}

export interface ModelMetadata {
	name: string;
	display_name?: string;
	download_size_mb: number;
	required_vram_mb: number;
	backend: string;
	multilingual: boolean;
	supported_languages: string[] | null; // null = all languages
	description: string;
	repo_id: string;
	is_distilled: boolean;
	speed_rating: string; // "fast" | "medium" | "slow"
	accuracy_rating: string; // "low" | "medium" | "high"
	/**
	 * Representative WER (%) (lower is better): real-world average for
	 * every model. Per-entry sources live in
	 * voice_typer/server/model_registry.py.
	 */
	wer?: number | null;
}

export interface ModelFamily {
	id: string;
	name: string;
	description: string | null;
	variants: ModelInfo[];
}

export const INITIAL_MODELS: ModelInfo[] = [
	{
		name: "tiny",
		size: "75 MB",
		speed: "Fastest",
		backend: "whisper",
		downloaded: false,
		depsOk: true,
		isActive: false,
	},
	{
		name: "large-v3",
		size: "3 GB",
		speed: "Slow",
		backend: "whisper",
		downloaded: false,
		depsOk: true,
		isActive: false,
	},
	{
		name: "large-v3-turbo",
		size: "1.6 GB",
		speed: "Fast",
		backend: "whisper",
		downloaded: false,
		depsOk: true,
		isActive: false,
	},
	{
		name: "qwen3-1.7b",
		displayName: "qwen3 1.7B",
		size: "3.9 GB",
		speed: "Medium",
		backend: "qwen",
		downloaded: false,
		depsOk: true,
		isActive: false,
	},
	{
		name: "qwen3-0.6b",
		displayName: "qwen3 0.6B",
		size: "1.9 GB",
		speed: "Fast",
		backend: "qwen",
		downloaded: false,
		depsOk: true,
		isActive: false,
	},
	{
		name: "parakeet",
		size: "2.5 GB",
		speed: "Fast",
		backend: "parakeet",
		downloaded: false,
		depsOk: false,
		isActive: false,
		depsInstallable: true,
	},
];

/**
 * Resolve the user-facing display name for a model variant row.
 *
 */
export function getModelVariantDisplayName(
	model: ModelInfo,
	meta?: ModelMetadata | null,
): string {
	if (meta?.display_name) return meta.display_name;
	if (model.displayName) return model.displayName;
	const formatted = formatModelDisplayName(model.name);
	if (model.backend === "whisper" || model.backend === "distil-whisper") {
		return `Whisper ${formatted}`;
	}
	return formatted;
}

export function groupModelsByFamily(models: ModelInfo[]): ModelFamily[] {
	const whisper = models.filter(
		(m) => m.backend === "whisper" || m.backend === "distil-whisper",
	);
	const qwen = models.filter((m) => m.backend === "qwen");
	const parakeet = models.filter((m) => m.backend === "parakeet");
	const families: ModelFamily[] = [];
	if (whisper.length > 0) {
		families.push({
			id: "whisper",
			name: "OpenAI",
			description: null,
			variants: whisper,
		});
	}
	if (qwen.length > 0) {
		families.push({
			id: "qwen",
			name: "Qwen",
			description: null,
			variants: qwen,
		});
	}
	if (parakeet.length > 0) {
		families.push({
			id: "parakeet",
			name: "Nvidia",
			description: null,
			variants: parakeet,
		});
	}
	return families;
}

// `total_bytes: number` and made `models_dir?: string` optional). The
// `models_dir?` both optional so richer backend responses still

export type { DiskInfo };

/**
 * : returns true when there is not enough free disk space to
 * download a model of the given size (in MB). A 10% safety margin is
 */
export function hasInsufficientDiskSpace(
	disk: DiskInfo | null,
	modelSizeMb: number,
): boolean {
	if (!disk) return false;
	const requiredBytes = modelSizeMb * 1024 * 1024 * 1.1;
	return disk.free_bytes < requiredBytes;
}

export function requiresHuggingFaceConsent(model: ModelInfo): boolean {
	return (
		model.backend === "whisper" ||
		model.backend === "distil-whisper" ||
		model.backend === "qwen" ||
		model.backend === "parakeet"
	);
}
