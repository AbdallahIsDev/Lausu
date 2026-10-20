/**
 * Cloud provider catalogue: the providers, the models each serves, brand
 * labels, API-key shape checks, and the active-row predicates.
 *
 * The tables here are pinned against the backend's `_PROVIDER_DEFAULTS` by
 * `tests/test_cloud_provider_catalogue_parity.py`, which parses THIS file.
 * Split out of `lib/utils/models.ts`; the barrel (`./models`) re-exports
 * every symbol below, so existing import paths keep resolving.
 */

import { t } from "@/i18n/i18n";
import type { LausuConfig } from "@/types/config";
import { formatModelDisplayName, formatWer } from "./format";

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
	/**
	 * Listed but never selectable: a streaming-only model the batch
	 * endpoint cannot serve. Renders a marker instead of Select.
	 * Stays set on every streaming id even once the app can stream
	 * it: it still needs a live session, never a batch call.
	 */
	realtimeOnly?: boolean;
	/**
	 * The app streams this id over its own WS transport, so the row
	 * is selectable despite `realtimeOnly`.
	 */
	realtimeWs?: boolean;
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
		// 2026-10-12). `gpt-transcribe` shipped 2026-07-28 alongside the two
		// realtime ids below. This provider posts to the BATCH transcriptions
		// endpoint; the realtime rows are listed as guard entries
		// (`realtimeOnly`) so the tab stays honest about the lineup without
		// offering a Select that can never transcribe. whisper-1 stays the
		// default: it is the only model here with a pooled real-world
		// figure, so it is the only one the WER column can compare
		// against the Local tab.
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
			{
				id: "gpt-live-transcribe",
				displayName: "GPT-Live-Transcribe",
				// No pooled figure covers it, so the cell shows an em dash.
				wer: null,
				// OpenAI positions it as the low-latency Realtime-API streaming tier.
				speed_rating: "fast",
				realtimeOnly: true,
				// App WS transport covers OpenAI sessions.
				realtimeWs: true,
			},
			{
				id: "gpt-realtime-whisper",
				displayName: "GPT-Realtime-Whisper",
				// No pooled figure covers it, so the cell shows an em dash.
				wer: null,
				// OpenAI positions it as the low-latency Realtime-API streaming tier.
				speed_rating: "fast",
				realtimeOnly: true,
				// App WS transport covers OpenAI sessions.
				realtimeWs: true,
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
		// is listed as a guard entry (`realtimeOnly`): it belongs to the
		// Live API (WebSocket), so it renders a marker, never Select.
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
			{
				id: "gemini-3.5-transcribe-live",
				// No pooled figure covers it, so the cell shows an em dash.
				wer: null,
				// Google positions it as the low-latency Live-API streaming tier.
				speed_rating: "fast",
				realtimeOnly: true,
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
 * True when the catalogue flags the model realtime-only: listed so the
 * tab stays honest about the lineup, never activatable on this endpoint.
 */
export function isRealtimeCloudModel(
	providerKey: string,
	modelId: string,
): boolean {
	return (
		CLOUD_PROVIDERS.find(
			(provider) => provider.key === providerKey,
		)?.models.find((entry) => entry.id === modelId)?.realtimeOnly === true
	);
}

/**
 * True when the app streams this realtime id over its own WS transport.
 */
export function isRealtimeWsSupported(
	providerKey: string,
	modelId: string,
): boolean {
	const entry = CLOUD_PROVIDERS.find(
		(provider) => provider.key === providerKey,
	)?.models.find((model) => model.id === modelId);
	return entry?.realtimeOnly === true && entry?.realtimeWs === true;
}

/**
 * True when the row stays display-only: realtime with no app transport.
 */
export function isRealtimeGuardOnly(
	providerKey: string,
	modelId: string,
): boolean {
	return (
		isRealtimeCloudModel(providerKey, modelId) &&
		!isRealtimeWsSupported(providerKey, modelId)
	);
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
	// A guard-only row is never the active one, even if the config names it.
	if (isRealtimeGuardOnly(provider.key, modelId)) return false;
	const active = activeCloudModel(cfg);
	return active?.provider === provider.key && active.model === modelId;
}

/**
 * The cloud model the config actually serves: the configured `cloud_model`,
 * or the provider's default when none has been chosen yet (picking a
 * PROVIDER without a model still runs one). `null` when the cloud backend
 * is not active or no provider is selected — the same "nothing usable"
 * line `hasActiveSpeechModel` draws.
 */
export function activeCloudModel(
	cfg: Partial<LausuConfig> | null,
): { provider: string; model: string } | null {
	if (cfg?.asr_backend !== "cloud") return null;
	const provider = (cfg.cloud_provider ?? "").trim();
	if (provider === "") return null;
	const model = cfg.cloud_model?.trim() || cloudDefaultModel(provider);
	return model === "" ? null : { provider, model };
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
