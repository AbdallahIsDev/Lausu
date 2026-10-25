/**
 * Selection and activation: whether a model is genuinely usable, and which
 * catalogue entry the current config selects.
 *
 * Split out of `lib/utils/models.ts`; the barrel (`./models`) re-exports
 * every symbol below, so existing import paths keep resolving.
 */

import type { LausuConfig } from "@/types/config";
import type { ModelStatusMap } from "@/types/ipc";
import type { ModelInfo } from "./modelCatalog";
import { INITIAL_MODELS, MODEL_DEFAULT } from "./modelCatalog";

/**
 * True when a speech model is genuinely usable — a LOCAL one, or a cloud
 * provider selected as the backend.
 *
 * This exists because the "no model selected" question used to be asked
 * as `cfg.model_size === ""`, which is a LOCAL-only question: a cloud
 * activation writes `asr_backend` / `cloud_provider` / `cloud_model` and
 * leaves `model_size` untouched, so a user whose only model is a cloud
 * one was told "No speech model is selected" (in red, on Home) while
 * dictation worked.
 *
 * `asr_backend === "cloud"` alone is not enough: with no provider the
 * backend reports itself not-loaded and the registry degrades to whisper,
 * so the app really does have nothing usable. `false` for a null config
 * means "still loading", never "nothing selected".
 */
export function hasActiveSpeechModel(cfg: LausuConfig | null): boolean {
	if (!cfg) return false;
	if (cfg.asr_backend === "cloud") return (cfg.cloud_provider ?? "") !== "";
	return (cfg.model_size ?? "") !== "";
}

/**
 * The negation of `hasActiveSpeechModel`, spelled out for the call sites
 * that read better that way (the Home status line, the Models banner).
 * A null config is NOT "no model selected" — it is "not loaded yet".
 */
export function isNoModelSelected(cfg: LausuConfig | null): boolean {
	return cfg ? !hasActiveSpeechModel(cfg) : false;
}

/**
 * Returns true if the given model entry matches the active backend/model
 * pair from the config. Whisper is keyed by both `asr_backend === "whisper"`
 */
export function isModelActive(
	m: ModelInfo,
	activeBackend: string,
	activeModel: string,
): boolean {
	if (!activeModel) {
		return false;
	}
	if (m.backend === "whisper") {
		return activeBackend === "whisper" && m.name === activeModel;
	}
	if (activeBackend !== m.backend) return false;
	// A family with more than one catalogue entry (the two Qwen sizes) is
	// keyed by NAME: one backend can never have two active variants. Single
	// -variant families keep the backend match so a stale `model_size`
	// still labels the installed model.
	const familyVariants = INITIAL_MODELS.filter(
		(x) => x.backend === m.backend,
	).length;
	return familyVariants > 1 ? m.name === activeModel : true;
}

/**
 * Map a config's active backend/model over a models list, returning a
 * new array with `isActive` set on the matching entry (and cleared on
 */
export function applyActiveState(
	models: ModelInfo[],
	cfg: LausuConfig | null,
): ModelInfo[] {
	if (!cfg) return models;
	const activeBackend = cfg.asr_backend ?? "whisper";
	const activeModel = cfg.model_size ?? MODEL_DEFAULT;
	return models.map((m) => ({
		...m,
		isActive: isModelActive(m, activeBackend, activeModel),
	}));
}

/**
 * Returns the family ID that contains the currently active model,
 * or null if no model is active or no family match is found.
 */
export function getActiveFamilyId(cfg: LausuConfig | null): string | null {
	if (!cfg) return null;
	const activeBackend = cfg.asr_backend ?? "whisper";
	const activeModel = cfg.model_size ?? MODEL_DEFAULT;
	for (const m of INITIAL_MODELS) {
		if (!isModelActive(m, activeBackend, activeModel)) continue;
		if (m.backend === "whisper" || m.backend === "distil-whisper")
			return "whisper";
		if (m.backend === "qwen") return "qwen";
		if (m.backend === "parakeet") return "parakeet";
	}
	return null;
}

// matched). Its own docstring claimed "Used by the sync-guard effect
// that auto-expands the active family accordion", but `rg 'sync-guard'`
// up the sync-guard effect OR a test that exercises it.

// state and must never be surfaced as a live selection when the model's

export interface ResolvedActiveModel {
	/**
	 * The installed, active model registry name, or null when the
	 * configured model's weights aren't on disk (or none configured).
	 */
	model: string | null;
	/**
	 * The device the active model runs on (from config), or null.
	 */
	device: string | null;
}

/**
 * Resolve the genuinely-active model from the configured model size +
 * the backend's `get_model_status` install truth.
 */
export function resolveActiveModel(
	configuredModel: string,
	modelStatusMap: ModelStatusMap,
	configuredDevice: string | null | undefined,
): ResolvedActiveModel {
	const installed =
		configuredModel !== "" &&
		modelStatusMap[configuredModel]?.downloaded === true;
	return installed
		? { model: configuredModel, device: configuredDevice ?? null }
		: { model: null, device: null };
}
