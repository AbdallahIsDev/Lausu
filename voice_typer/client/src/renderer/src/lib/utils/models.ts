/**
 * Model-page helpers and shared types ( extraction).
 *
 */

import { t } from "@/i18n/i18n";
import {
	formatVram as _formatVram,
	formatWer as _formatWer,
} from "@/lib/format";
import type { LausuConfig } from "@/types/config";
import type { ModelStatusMap } from "@/types/ipc";

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
		size: "809 MB",
		speed: "Fast",
		backend: "whisper",
		downloaded: false,
		depsOk: true,
		isActive: false,
	},
	{
		name: "qwen",
		size: "Variable",
		speed: "Fast",
		backend: "qwen",
		downloaded: false,
		// Qwen requires the optional `qwen_asr` pip package (probed by
		depsOk: true,
		isActive: false,
		depsInstallable: true,
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

export type CloudProviderKey = "openai" | "groq" | "deepgram" | "gemini";

/**
 * One model served by a cloud provider.
 *
 * A provider owns MANY of these. The old shape welded exactly one model
 * onto each provider (`CloudProvider.model`), which forced the setup UI to
 * hang a Configure action off every model row even though all of a
 * provider's models share one API key. Adding a model is now a one-line
 * change here, which is the point: these lists grow.
 */
export interface CloudModel {
	/** Provider model id, exactly as the API expects it. */
	id: string;
	/**
	 * How the provider WRITES this model's name, for ids the generic
	 * dash-splitter mangles (`"gpt-4o-transcribe"` →
	 * `"Gpt 4o Transcribe"`). Omit when `formatModelDisplayName(id)` is
	 * already right (`"whisper-large-v3"` → `"Whisper Large V3"`); read
	 * it through `cloudModelLabel()` rather than off the field.
	 */
	displayName?: string;
	/**
	 * Real-world representative WER (%) on the SAME pooled scale the
	 * Local tab uses (lower is better), or `null` when no pooled
	 * benchmark covers this model. `null` renders as an em dash rather
	 * than a guessed number — inventing one would silently break the
	 * cross-tab comparison the column exists for.
	 *
	 * The SCALE matters: the local registry's numbers are real-world
	 * representative averages (Coval's pooled leaderboard puts Whisper
	 * Large v3 at 5.0%, and the local `large-v3` entry is 5.0), NOT
	 * LibriSpeech-clean numbers (~2.8% for the same model, which
	 * understate everyday errors 2-3x).
	 */
	wer: number | null;
	/** Transcription speed tier (`"fast"` | `"medium"` | `"slow"`),
	 *  rendered by `SpeedTag` exactly as the local model rows do. */
	speed_rating: string;
}

export interface CloudProvider {
	key: CloudProviderKey;
	/** Transcription endpoint. `{model}` is substituted by the backend
	 *  for providers whose model id is part of the URL (Gemini). */
	url: string;
	/** Model id used when the provider is activated without a choice. */
	defaultModel: string;
	/** Models this provider serves. Grows over time. */
	models: readonly CloudModel[];
}

export const CLOUD_PROVIDERS: readonly CloudProvider[] = [
	{
		key: "openai",
		url: "https://api.openai.com/v1/audio/transcriptions",
		defaultModel: "whisper-1",
		// Source: OpenAI's transcription guides (developers.openai.com,
		// 2026-10-12). `gpt-transcribe` and `gpt-live-transcribe` shipped
		// 2026-07-28; only the first is listed here. This provider posts to
		// the BATCH transcriptions endpoint, and by OpenAI's own model matrix
		// `gpt-live-transcribe` and `gpt-realtime-whisper` are Realtime-API
		// models (WebSocket/WebRTC transcription sessions) that the batch
		// endpoint does not serve — listing them would offer a row that
		// cannot transcribe. whisper-1 stays the default: it is the only
		// model here with a pooled real-world figure, so it is the only one
		// the WER column can compare against the Local tab.
		models: [
			{
				id: "whisper-1",
				// WER 5.5, DERIVED. `whisper-1` is the Whisper large-v2
				// generation; Coval's pooled leaderboard (2026-10-11) scores
				// Whisper Large v3 at 5.0%, and v2 sits ~0.5 behind v3 on the
				// same corpora — the same generation gap the local registry
				// applies to large-v3-turbo (5.5). Coval has no whisper-1 row,
				// so this is a derivation, not a published figure.
				wer: 5.5,
				// Batch-only endpoint: no streaming, and the highest
				// wall-clock latency of the models this provider serves
				// (docs/cloud-transcription-setup.md).
				speed_rating: "medium",
			},
			{
				id: "gpt-transcribe",
				// OpenAI writes the new generation with a hyphen before
				// "Transcribe" ("GPT-Transcribe"), unlike the GPT-4o tiers
				// below; the generic splitter would render "Gpt Transcribe".
				displayName: "GPT-Transcribe",
				// No pooled real-world figure covers it yet, so the cell
				// shows an em dash rather than a guess.
				wer: null,
				// OpenAI's own model page publishes Speed "Medium" for this
				// model (Performance "Highest") — the same tier as whisper-1
				// and the GPT-4o tiers below. This REPLACES an earlier
				// inferred "fast": the inference was wrong, and the published
				// figure supersedes it.
				speed_rating: "medium",
			},
			{
				id: "gpt-4o-transcribe",
				// OpenAI writes it "GPT-4o" (caps + no dash before the 4o);
				// the generic splitter would render "Gpt 4o Transcribe".
				displayName: "GPT-4o Transcribe",
				// No pooled real-world figure covers the GPT-4o transcribe
				// tiers, so the cell shows an em dash rather than a guess.
				wer: null,
				// OpenAI's model page publishes Speed "Medium" (Performance
				// "Higher"). This said "fast" until 2026-10-12, which
				// contradicted the vendor's own label; the mini tier below is
				// genuinely "Fast", so the two tiers really do differ.
				speed_rating: "medium",
			},
			{
				id: "gpt-4o-mini-transcribe",
				displayName: "GPT-4o mini Transcribe",
				wer: null,
				// OpenAI publishes Speed "Fast" (Performance "High") for this
				// one — unlike its larger sibling — so this was already right.
				speed_rating: "fast",
			},
		],
	},
	{
		key: "groq",
		url: "https://api.groq.com/openai/v1/audio/transcriptions",
		defaultModel: "whisper-large-v3",
		// Source: Groq's Speech to Text docs (console.groq.com, 2026-10-12) —
		// exactly two models, whisper-large-v3 and whisper-large-v3-turbo.
		models: [
			{
				id: "whisper-large-v3",
				// WER 5.0: Coval pooled "Whisper Large v3" (2026-10-11). Groq
				// serves the SAME weights as the local `large-v3` entry, so the
				// two figures agree by construction rather than by coincidence.
				wer: 5.0,
				// Groq's LPU is the lowest-latency cloud ASR path (<300 ms for
				// a short clip).
				speed_rating: "fast",
			},
			{
				id: "whisper-large-v3-turbo",
				// WER 5.5, DERIVED — the same generation gap the local registry
				// applies to `large-v3-turbo`. Groq publishes 12% for this
				// model, but on a different (harder) corpus than Coval's pool,
				// so it is deliberately NOT used here: the column has to stay
				// comparable with the Local tab.
				wer: 5.5,
				// Groq documents turbo at 216x real-time vs 189x for the full
				// model, and at $0.04/hr vs $0.111/hr.
				speed_rating: "fast",
			},
		],
	},
	{
		key: "deepgram",
		url: "https://api.deepgram.com/v1/listen",
		defaultModel: "nova-3",
		// Source: Deepgram's Models & Languages overview
		// (developers.deepgram.com, 2026-10-12). The current general-purpose
		// line is nova-3 (highest performing, widest language coverage) with
		// nova-2 kept for the languages nova-3 does not cover yet. Flux is
		// excluded on purpose: it is a streaming voice-agent model with
		// model-native turn detection, not a batch dictation engine.
		models: [
			{
				id: "nova-3",
				// No pooled real-world figure covers Nova 3 yet.
				wer: null,
				// Deepgram documents nova-3 as 47.4% better WER than its
				// predecessor on batch, and 54.2% on streaming.
				speed_rating: "fast",
			},
			{
				id: "nova-2",
				// WER 6.4: Coval pooled "Nova 2" (2026-10-11).
				wer: 6.4,
				// Streaming engine, 130 ms p95 time-to-final-segment on the
				// same leaderboard.
				speed_rating: "fast",
			},
		],
	},
	{
		key: "gemini",
		url: "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
		defaultModel: "gemini-3.5-transcribe",
		// Source: Google's Gemini API model page (ai.google.dev, 2026-10-12).
		// `gemini-3.5-transcribe` is a DEDICATED speech-to-text model, served by
		// the Unary `generateContent` call this provider already makes — the
		// previous entries here were general-purpose Flash models borrowed as an
		// ASR fallback. The realtime sibling, `gemini-3.5-transcribe-live`,
		// belongs to the Live API (WebSocket) and is deliberately absent for the
		// same reason the OpenAI realtime ids are: this provider posts a
		// finished file, not a live stream.
		models: [
			{
				id: "gemini-3.5-transcribe",
				// No pooled real-world figure covers it yet, so the cell shows
				// an em dash rather than a guess.
				wer: null,
				// Google's model page describes it as "low-latency, accurate
				// transcription"; no real-time-factor figure is published.
				speed_rating: "fast",
			},
		],
	},
] as const;

/**
 * Identifies ONE cloud model: the provider that serves it plus the
 * model id. Used as the in-flight marker while an activation is being
 * persisted, so only the clicked row shows its spinner.
 */
export interface CloudModelRef {
	provider: CloudProviderKey;
	model: string;
}

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
 * The name to render for a cloud model: the catalogue's explicit
 * `displayName` when it has one, otherwise the shared dash-splitter the
 * Local rows use. Takes the (provider, model id) PAIR rather than the
 * entry so the activation toast — which only ever has the two ids in
 * hand — and the row heading resolve through the same lookup and can
 * never disagree.
 */
export function cloudModelLabel(providerKey: string, modelId: string): string {
	const model = CLOUD_PROVIDERS.find(
		(provider) => provider.key === providerKey,
	)?.models.find((entry) => entry.id === modelId);
	return model?.displayName ?? formatModelDisplayName(modelId);
}

/**
 * WER cell for a cloud model row. `null` (no pooled benchmark covers this
 * model) renders as an em dash — deliberately NOT a made-up number, because
 * the column exists so a user can compare error rates across the Local and
 * Cloud tabs.
 */
export function formatCloudWer(wer: number | null): string {
	return wer === null ? "—" : formatWer(wer);
}

/**
 * True when `modelId` is the cloud model currently in use: the active
 * backend is cloud, `providerKey` is the configured provider, and the model
 * matches (or none has been chosen yet, in which case the provider's
 * default is the one actually being served).
 */
export function isCloudModelActive(
	provider: CloudProvider,
	modelId: string,
	cfg: LausuConfig | null,
): boolean {
	if (cfg?.asr_backend !== "cloud") return false;
	if ((cfg.cloud_provider ?? "") !== provider.key) return false;
	const selected = cfg.cloud_model?.trim()
		? cfg.cloud_model
		: provider.defaultModel;
	return selected === modelId;
}

/**
 * The model a provider serves when the user picks the PROVIDER without
 * picking a model — the exact counterpart of the backend's
 * `_PROVIDER_DEFAULTS[provider]["model"]` (`server/cloud/_defaults.py`).
 * The two tables are pinned against each other by
 * `tests/test_cloud_provider_catalogue_parity.py`, so a provider whose
 * entry is missing here is a bug in this file, not a legitimate state;
 * the empty string keeps the caller from writing a bogus model id.
 */
export function cloudDefaultModel(providerKey: string): string {
	return (
		CLOUD_PROVIDERS.find((provider) => provider.key === providerKey)
			?.defaultModel ?? ""
	);
}

/**
 * The provider's BRAND name ("OpenAI", "Groq", "Deepgram", "Google") —
 * the whole of the provider's identity, and nothing about which model
 * it serves. The cloud rows used to render "OpenAI Whisper API", which
 * welded three different facts (provider + model + the word "API") into
 * one label; the model name belongs in the row's own heading, one level
 * down inside the provider's group.
 */
export function getProviderLabel(providerKey: string): string {
	switch (providerKey) {
		case "openai":
			return t("models.providers.openai.label");
		case "groq":
			return t("models.providers.groq.label");
		case "deepgram":
			return t("models.providers.deepgram.label");
		case "gemini":
			return t("models.providers.gemini.label");
		default:
			return providerKey;
	}
}

// ── API-key format validation ─────────────────────────────────────────
// Each provider mints keys in a fixed shape, and each shape is published
// as a machine-readable detector rule — that is the only authoritative
// statement of "what a key for this provider looks like". Sources:
//   • OpenAI   — "sk-" (legacy, 48 chars) or "sk-proj-" (project-scoped,
//                longer). RegexVault's audited pattern is
//                `^sk-[A-Za-z0-9_-]{20,128}$`; the `sk-proj-` body is
//                covered because "-" is inside the class.
//   • Groq     — "gsk_" + exactly 52 alphanumerics (secretlint's
//                `secretlint-rule-groq`, mirrored by trufflehog's
//                `pkg/detectors/groq` and GitHub secret scanning).
//   • Deepgram — 40 lowercase alphanumerics, no prefix (trufflehog
//                `pkg/detectors/deepgram`: `\b([0-9a-z]{40})\b`).
//   • Google   — "AIza" + 35 of [A-Za-z0-9_-], 39 chars total
//                (Microsoft Purview SIT "Google API key"). The Gemini
//                API key issued by AI Studio is a Google API key.
//
// Why a shape check at all: without it the Save action wrote ANY typed
// string into the credential store and then reported success, so
// "GFHFGHHFGH" produced a green "API key saved" toast and a provider
// that could never authenticate. A shape match is not a validity
// guarantee — only the provider can say that, which is what Test
// Connection is for — but it does reject the case where the user typed
// something that cannot possibly be a key.
const API_KEY_PATTERNS: Record<string, RegExp> = {
	openai: /^sk-[A-Za-z0-9_-]{20,}$/,
	groq: /^gsk_[A-Za-z0-9]{52}$/,
	deepgram: /^[0-9a-z]{40}$/,
	gemini: /^AIza[A-Za-z0-9_-]{35}$/,
};

/**
 * True when `value` has the published shape of an API key for
 * `providerKey`. Unknown providers (a self-hosted endpoint configured
 * outside this UI) accept any non-empty value — there is no published
 * shape to check against, and refusing would break them.
 */
export function isValidApiKeyFormat(
	providerKey: string,
	value: string,
): boolean {
	const pattern = API_KEY_PATTERNS[providerKey];
	const trimmed = value.trim();
	if (!pattern) return trimmed.length > 0;
	return pattern.test(trimmed);
}

/**
 * Map the backend's `test_cloud_connection` failure token to the i18n
 * key that explains it in words. The backend deliberately returns a
 * short stable token (`_http_error_message` in
 * `server/handlers/cloud_test_handlers.py`) so the wording stays a
 * renderer concern; rendering the token raw is what produced the
 * meaningless "Connection failed: 400 http_error".
 *
 * `no_api_key` maps to the existing "enter a key first" copy: it means
 * the same thing to the user as the pre-flight guard's message.
 */
export function connectionFailureKey(token: string): string {
	switch (token) {
		case "auth_failed":
			return "models.test.failure.auth";
		case "rate_limited":
			return "models.test.failure.rateLimited";
		case "server_error":
			return "models.test.failure.server";
		case "network_error":
			return "models.test.failure.network";
		case "no_api_key":
			return "models.test.needApiKey";
		default:
			return "models.test.failure.http";
	}
}

const MODEL_SIZE_NORMALIZER = /^(?:~|≈)?\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z]+)$/;
export function formatModelSize(size: string): string {
	const trimmed = size.trim();
	if (trimmed === "Variable") return t("models.variable");
	const match = MODEL_SIZE_NORMALIZER.exec(trimmed);
	if (!match) return trimmed;
	// optional, hence the explicit guard before formatting).
	const [, number, unit] = match;
	if (number === undefined || unit === undefined) return trimmed;
	return `${number} ${unit.toUpperCase()}`;
}

const SPEED_I18N_MAP: Record<string, string> = {
	Fastest: "models.speed.fastest",
	Fast: "models.speed.fast",
	Medium: "models.speed.medium",
	Slow: "models.speed.slow",
	Variable: "models.speed.variable",
};

/**
 * Capitalize the first letter of a word ("fast" → "Fast"). Defensive:
 * backend catalog entries may omit the field (ERR-1: qwen catalog-only
 */
function capitalizeFirst(value: string | null | undefined): string {
	if (typeof value !== "string") return "";
	return value.length > 0
		? value.charAt(0).toUpperCase() + value.slice(1)
		: value;
}

/**
 * Format a speed rating for display. Accepts both the legacy
 * capitalized source values ("Fast", "Fastest") and the backend
 */
export function formatModelSpeed(speed: string | null | undefined): string {
	if (typeof speed !== "string" || speed.length === 0) return "";
	const key = SPEED_I18N_MAP[speed] ?? SPEED_I18N_MAP[capitalizeFirst(speed)];
	return key ? t(key) : capitalizeFirst(speed);
}

// `voice_typer/client/src`, so there is nothing to wire, the helper
export function formatVram(mb: number): string {
	return _formatVram(mb);
}

/**
 * Re-export of the locale-aware WER percent formatter (see lib/format.ts).
 */
export function formatWer(wer: number): string {
	return _formatWer(wer);
}

/**
 * : format an unknown caught value as a user-friendly string.
 *
 */
export function formatErrorMessage(
	err: unknown,
	fallback: string = t("models.errors.unknown"),
): string {
	if (err instanceof Error) {
		return err.message || fallback;
	}
	if (typeof err === "string") {
		return err || fallback;
	}
	if (err && typeof err === "object") {
		const obj = err as { _error?: unknown; message?: unknown; error?: unknown };
		if (typeof obj._error === "string" && obj._error) return obj._error;
		if (typeof obj.message === "string" && obj.message) return obj.message;
		if (typeof obj.error === "string" && obj.error) return obj.error;
	}
	return fallback;
}

export function formatModelDisplayName(rawId: string): string {
	return rawId
		.split("-")
		.filter((part) => part.length > 0)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}

/**
 * Resolve the user-facing display name for a model variant row.
 *
 */
export function getModelVariantDisplayName(
	model: ModelInfo,
	meta?: ModelMetadata | null,
): string {
	if (meta?.display_name) return meta.display_name;
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
	return activeBackend === m.backend;
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

// `total_bytes: number` and made `models_dir?: string` optional). The
// `models_dir?` both optional so richer backend responses still
import type { DiskInfo } from "@/types/ipc";

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
		model.backend === "parakeet"
	);
}
