// Display-name helpers for config values shown in the UI.
// The backend config stores machine values ("cuda", "cpu", "tiny",
// "en"). These helpers map them to user-facing labels so every surface
// that shows them (the Home share image, the About/Diagnostics rows)
// renders the same friendly text. The internal config values are NOT
// changed, only the rendered text.
// - device: "cuda" → "GPU" (friendly; the config keeps "cuda" to avoid
//   a wider refactor). "cpu" → "CPU". Unknown values pass through.
// - model: capitalize the first letter ("tiny" → "Tiny") so Model /
//   Device / Language share one capitalization convention wherever
//   they are shown together.
// - language: map the ISO code to the full localized name ("en" →
//   "English", "" → "Auto-detect") using the same i18n label keys as
//   the Settings language select (single source: lib/utils/languages).
import { t } from "@/i18n/i18n";
import type { LausuConfig } from "@/types/config";
import { activeCloudModel, cloudModelLabel } from "./cloudCatalog";
import { LANGUAGE_LABEL_KEYS } from "./languages";
import { isModelActive } from "./modelActive";
import { getModelVariantDisplayName, INITIAL_MODELS } from "./modelCatalog";

/** "cuda" → "GPU", "cpu" → "CPU" (display only; config stays "cuda"). */
export function formatDevice(device: string): string {
	if (device === "cuda") return "GPU";
	if (device === "cpu") return "CPU";
	return device;
}

/** Capitalize the first letter of a model name ("tiny" → "Tiny"). */
export function formatModel(model: string): string {
	if (!model) return "";
	return model.charAt(0).toUpperCase() + model.slice(1);
}

/**
 * Display name of the ACTIVE speech model — the selected cloud model or the
 * local variant — or "" when none is active. Cloud activation only writes
 * `asr_backend`/`cloud_provider`/`cloud_model`, leaving `model_size`
 * untouched, so reading `model_size` alone would name a model the user is
 * not running. The name matches the Models page row for the same model
 * (`cloudModelLabel` / `getModelVariantDisplayName`), so the two surfaces
 * never disagree.
 */
export function formatActiveModel(cfg: Partial<LausuConfig> | null): string {
	if (!cfg) return "";
	const cloud = activeCloudModel(cfg);
	if (cloud) return cloudModelLabel(cloud.provider, cloud.model);
	if (cfg.asr_backend === "cloud") return "";
	const model = cfg.model_size ?? "";
	if (model === "") return "";
	const backend = cfg.asr_backend ?? "whisper";
	const info = INITIAL_MODELS.find((m) => isModelActive(m, backend, model));
	return info ? getModelVariantDisplayName(info) : formatModel(model);
}

export function formatLanguage(code: string): string {
	if (!code) return t("settings.languageAutoDetect");
	const labelKey = LANGUAGE_LABEL_KEYS[code];
	return labelKey ? t(labelKey) : code;
}
