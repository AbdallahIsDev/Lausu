/**
 * Cloud catalogue + activation-state tests.
 *
 * The Cloud tab's model list is DATA (`CLOUD_PROVIDERS[].models`) and is
 * expected to grow, so these tests assert INVARIANTS over the catalogue
 * rather than restating its contents: a provider's default must be one
 * of its own models, ids must not collide, and — the load-bearing one —
 * at most ONE model can read as active across the Local and Cloud tabs
 * combined.
 */
import { describe, expect, it } from "vitest";
import type { CloudProvider } from "@/lib/utils/models";
import {
	applyActiveState,
	CLOUD_PROVIDERS,
	cloudModelLabel,
	formatCloudWer,
	formatWer,
	hasActiveSpeechModel,
	INITIAL_MODELS,
	isCloudModelActive,
	isNoModelSelected,
	isRealtimeCloudModel,
	isRealtimeGuardOnly,
	isRealtimeWsSupported,
} from "@/lib/utils/models";
import type { LausuConfig } from "@/types/config";

function makeConfig(overrides: Partial<LausuConfig>): LausuConfig {
	return {
		asr_backend: "whisper",
		model_size: "",
		cloud_provider: "",
		cloud_model: "",
		...overrides,
	} as LausuConfig;
}

/** Look a provider up by key, with the undefined branch made explicit so
 *  `noUncheckedIndexedAccess` is satisfied without a non-null assertion. */
function providerByKey(key: string): CloudProvider {
	const found = CLOUD_PROVIDERS.find((provider) => provider.key === key);
	if (!found) throw new Error(`no ${key} provider in the catalogue`);
	return found;
}

/** Every cloud model that reads as active under `cfg`. */
function activeCloudModels(cfg: LausuConfig): string[] {
	return CLOUD_PROVIDERS.flatMap((provider) =>
		provider.models
			.filter((model) => isCloudModelActive(provider, model.id, cfg))
			.map((model) => `${provider.key}/${model.id}`),
	);
}

/** Every LOCAL model that reads as active under `cfg`. */
function activeLocalModels(cfg: LausuConfig): string[] {
	return applyActiveState(INITIAL_MODELS, cfg)
		.filter((model) => model.isActive)
		.map((model) => model.name);
}

describe("CLOUD_PROVIDERS catalogue invariants", () => {
	it("every provider's defaultModel is one of the models it serves", () => {
		// `isCloudModelActive` falls back to `defaultModel` when
		// `cloud_model` is empty (onboarding picks a provider without
		// picking a model), so a default outside the list would leave the
		// tab showing no active row at all.
		for (const provider of CLOUD_PROVIDERS) {
			const ids = provider.models.map((model) => model.id);
			expect(
				ids,
				`${provider.key}.defaultModel must be one of its own models`,
			).toContain(provider.defaultModel);
		}
	});

	it("serves at least one model per provider and never repeats an id inside one", () => {
		for (const provider of CLOUD_PROVIDERS) {
			const ids = provider.models.map((model) => model.id);
			expect(ids.length).toBeGreaterThan(0);
			expect(new Set(ids).size).toBe(ids.length);
		}
	});

	it("keeps model ids globally unique (the row key is the bare id)", () => {
		const all = CLOUD_PROVIDERS.flatMap((provider) =>
			provider.models.map((model) => model.id),
		);
		expect(new Set(all).size).toBe(all.length);
	});

	it("every provider points at an https endpoint", () => {
		for (const provider of CLOUD_PROVIDERS) {
			expect(provider.url.startsWith("https://")).toBe(true);
		}
	});
});

describe("OpenAI catalogue", () => {
	it("lists gpt-transcribe under OpenAI's own hyphenated casing", () => {
		// The generic splitter renders "Gpt Transcribe", which is not how
		// OpenAI writes it. The label is what the row heading AND the
		// activation toast both read, so a missing displayName is visible.
		expect(cloudModelLabel("openai", "gpt-transcribe")).toBe("GPT-Transcribe");
	});

	it("serves gpt-transcribe alongside the measured default and the GPT-4o tiers", () => {
		const ids = providerByKey("openai").models.map((model) => model.id);
		expect(ids).toContain("gpt-transcribe");
		expect(ids).toContain("whisper-1");
		expect(ids).toContain("gpt-4o-transcribe");
		expect(ids).toContain("gpt-4o-mini-transcribe");
		// The default stays the one model with a pooled WER, so the Cloud
		// tab's accuracy column remains comparable with the Local tab.
		expect(providerByKey("openai").defaultModel).toBe("whisper-1");
	});

	it("lists the Realtime-API ids as realtime rows the app streams over WS", () => {
		// `gpt-live-transcribe` and `gpt-realtime-whisper` belong to
		// Realtime API sessions, NOT to `POST /v1/audio/transcriptions` —
		// but the app now streams OpenAI sessions over its own WS
		// transport, so these rows are selectable despite `realtimeOnly`.
		for (const id of ["gpt-live-transcribe", "gpt-realtime-whisper"]) {
			const entry = providerByKey("openai").models.find(
				(model) => model.id === id,
			);
			expect(entry?.realtimeOnly).toBe(true);
			expect(isRealtimeCloudModel("openai", id)).toBe(true);
			expect(isRealtimeWsSupported("openai", id)).toBe(true);
			expect(isRealtimeGuardOnly("openai", id)).toBe(false);
		}
		expect(isRealtimeCloudModel("openai", "whisper-1")).toBe(false);
		expect(isRealtimeWsSupported("openai", "whisper-1")).toBe(false);
	});
});

describe("Gemini catalogue — one dedicated ASR model", () => {
	it("serves gemini-3.5-transcribe as its default, beside the realtime guard row", () => {
		const provider = providerByKey("gemini");
		const ids = provider.models.map((model) => model.id);
		expect(ids).toContain("gemini-3.5-transcribe");
		expect(ids).toContain("gemini-3.5-transcribe-live");
		// The default must be one of the provider's own models
		// (`isCloudModelActive` falls back to it when `cloud_model` is empty,
		// which is the state onboarding leaves behind).
		expect(provider.defaultModel).toBe("gemini-3.5-transcribe");
	});

	it("labels it the way Google writes it, with no displayName override", () => {
		// `formatModelDisplayName` already splits this id correctly, so an
		// override would only be a second place to drift.
		expect(cloudModelLabel("gemini", "gemini-3.5-transcribe")).toBe(
			"Gemini 3.5 Transcribe",
		);
	});

	it("lists the Live-API sibling as a realtime-only guard row", () => {
		// `gemini-3.5-transcribe-live` is the Live API (WebSocket) variant
		// of the same model, for continuous microphone audio. This
		// provider posts one finished file to `{model}:generateContent`,
		// so the row renders a marker, never Select.
		const entry = providerByKey("gemini").models.find(
			(model) => model.id === "gemini-3.5-transcribe-live",
		);
		expect(entry?.realtimeOnly).toBe(true);
		expect(isRealtimeCloudModel("gemini", "gemini-3.5-transcribe-live")).toBe(
			true,
		);
		expect(isRealtimeCloudModel("gemini", "gemini-3.5-transcribe")).toBe(false);
	});

	it("no longer offers the general-purpose Flash models it replaced", () => {
		// The Flash entries were borrowed multimodal models, not dedicated ASR
		// engines; they were removed on the user's instruction, not by
		// accident, so re-adding one should be a deliberate edit.
		const ids = providerByKey("gemini").models.map((model) => model.id);
		expect(ids).not.toContain("gemini-3.8-flash");
		expect(ids).not.toContain("gemini-2.5-flash");
		expect(ids).not.toContain("gemini-2.0-flash");
	});
});

describe("realtime-only catalogue guard", () => {
	const realtimePairs: Array<[string, string]> = [
		["openai", "gpt-live-transcribe"],
		["openai", "gpt-realtime-whisper"],
		["gemini", "gemini-3.5-transcribe-live"],
	];

	it("flags exactly the three streaming ids, nothing else", () => {
		const flagged = CLOUD_PROVIDERS.flatMap((provider) =>
			provider.models
				.filter((model) => model.realtimeOnly === true)
				.map((model) => `${provider.key}/${model.id}`),
		);
		expect(flagged.sort()).toEqual(
			realtimePairs.map(([key, id]) => `${key}/${id}`).sort(),
		);
	});

	it("marks exactly the two OpenAI rows as WS-supported, gemini stays guard-only", () => {
		// Count-based: the app streams OpenAI sessions only; the Live
		// API uses a different protocol with no app transport.
		const supported = CLOUD_PROVIDERS.flatMap((provider) =>
			provider.models
				.filter((model) => isRealtimeWsSupported(provider.key, model.id))
				.map((model) => `${provider.key}/${model.id}`),
		);
		expect(supported.sort()).toEqual(
			["openai/gpt-live-transcribe", "openai/gpt-realtime-whisper"].sort(),
		);
		expect(isRealtimeGuardOnly("gemini", "gemini-3.5-transcribe-live")).toBe(
			true,
		);
		expect(isRealtimeWsSupported("gemini", "gemini-3.5-transcribe-live")).toBe(
			false,
		);
	});

	it("never uses a realtime model as a provider default", () => {
		// The defaults stay the batch ids, so the empty-`cloud_model`
		// fallback always resolves to a transcribable model.
		expect(providerByKey("openai").defaultModel).toBe("whisper-1");
		expect(providerByKey("groq").defaultModel).toBe("whisper-large-v3");
		expect(providerByKey("deepgram").defaultModel).toBe("nova-3");
		expect(providerByKey("gemini").defaultModel).toBe("gemini-3.5-transcribe");
		for (const provider of CLOUD_PROVIDERS) {
			const flagged = provider.models
				.filter((model) => model.realtimeOnly === true)
				.map((model) => model.id);
			expect(flagged).not.toContain(provider.defaultModel);
		}
	});

	it("keeps every id — realtime included — globally unique", () => {
		const all = CLOUD_PROVIDERS.flatMap((provider) =>
			provider.models.map((model) => model.id),
		);
		for (const [, id] of realtimePairs) {
			expect(all.filter((entry) => entry === id)).toHaveLength(1);
		}
		expect(new Set(all).size).toBe(all.length);
	});

	it("reads a guard-only model as never active, even when the config names it", () => {
		const c = makeConfig({
			asr_backend: "cloud",
			cloud_provider: "gemini",
			cloud_model: "gemini-3.5-transcribe-live",
		});
		expect(
			isCloudModelActive(
				providerByKey("gemini"),
				"gemini-3.5-transcribe-live",
				c,
			),
		).toBe(false);
	});

	it("reads a WS-supported realtime model as active when the config names it", () => {
		for (const id of ["gpt-live-transcribe", "gpt-realtime-whisper"]) {
			const c = makeConfig({
				asr_backend: "cloud",
				cloud_provider: "openai",
				cloud_model: id,
			});
			expect(isCloudModelActive(providerByKey("openai"), id, c)).toBe(true);
		}
	});

	it("labels the realtime rows through the catalogue", () => {
		expect(cloudModelLabel("openai", "gpt-live-transcribe")).toBe(
			"GPT-Live-Transcribe",
		);
		expect(cloudModelLabel("openai", "gpt-realtime-whisper")).toBe(
			"GPT-Realtime-Whisper",
		);
		expect(cloudModelLabel("gemini", "gemini-3.5-transcribe-live")).toBe(
			"Gemini 3.5 Transcribe Live",
		);
	});
});

describe("formatCloudWer, em dash instead of a guessed number", () => {
	it("renders null as an em dash (no pooled benchmark covers the model)", () => {
		expect(formatCloudWer(null)).toBe("—");
	});

	it("delegates a real figure to the shared WER formatter (same scale as Local)", () => {
		expect(formatCloudWer(5.5)).toBe(formatWer(5.5));
		expect(formatCloudWer(5)).toBe(formatWer(5));
	});
});

describe("cloudModelLabel, display name resolution", () => {
	it("prefers the catalogue's explicit displayName", () => {
		expect(cloudModelLabel("openai", "gpt-4o-transcribe")).toBe(
			"GPT-4o Transcribe",
		);
	});

	it("falls back to the shared dash-splitter", () => {
		expect(cloudModelLabel("groq", "whisper-large-v3")).toBe(
			"Whisper Large V3",
		);
		expect(cloudModelLabel("deepgram", "nova-3")).toBe("Nova 3");
	});

	it("still formats an id the catalogue does not know (defensive)", () => {
		expect(cloudModelLabel("openai", "some-future-model")).toBe(
			"Some Future Model",
		);
	});
});

describe("isCloudModelActive", () => {
	const cfg = (overrides: Partial<LausuConfig>) => makeConfig(overrides);

	it("is false without a config, or when the backend is not cloud", () => {
		const provider = providerByKey("openai");
		expect(isCloudModelActive(provider, provider.defaultModel, null)).toBe(
			false,
		);
		expect(
			isCloudModelActive(
				provider,
				provider.defaultModel,
				cfg({ asr_backend: "whisper", cloud_provider: provider.key }),
			),
		).toBe(false);
	});

	it("is false for a different provider", () => {
		const openai = providerByKey("openai");
		expect(
			isCloudModelActive(
				openai,
				openai.defaultModel,
				cfg({ asr_backend: "cloud", cloud_provider: "groq" }),
			),
		).toBe(false);
	});

	it("is true only for the model the config names", () => {
		const groq = providerByKey("groq");
		const other = groq.models.find((m) => m.id !== groq.defaultModel);
		if (!other) throw new Error("groq serves a single model");

		const base = cfg({
			asr_backend: "cloud",
			cloud_provider: "groq",
			cloud_model: other.id,
		});
		expect(isCloudModelActive(groq, other.id, base)).toBe(true);
		expect(isCloudModelActive(groq, groq.defaultModel, base)).toBe(false);
	});

	it("treats an empty or whitespace cloud_model as the provider's default", () => {
		const deepgram = providerByKey("deepgram");
		for (const empty of ["", "   "]) {
			const c = cfg({
				asr_backend: "cloud",
				cloud_provider: "deepgram",
				cloud_model: empty,
			});
			expect(isCloudModelActive(deepgram, deepgram.defaultModel, c)).toBe(true);
		}
	});
});

// ── The one-active-model rule, across BOTH tabs ───────────────────────
// The user's requirement: "only one model can be active at a time across
// all local and cloud models … we must prevent a local model and a cloud
// model from being active simultaneously." It holds structurally —
// `config.asr_backend` is a SINGLE value ("whisper" | "qwen" | "parakeet"
// | "cloud") — and these tests are what pins that it stays structural:
// the local side and the cloud side read the same field, in opposite
// directions.
describe("exactly one active model across local + cloud", () => {
	it("a cloud activation leaves NO local model active (model_size still set)", () => {
		const c = makeConfig({
			asr_backend: "cloud",
			// Deliberately left pointing at a real local model: switching
			// the backend is what deactivates it, not clearing the field.
			model_size: "large-v3",
			cloud_provider: "groq",
			cloud_model: "whisper-large-v3",
		});
		expect(activeLocalModels(c)).toEqual([]);
		expect(activeCloudModels(c)).toEqual(["groq/whisper-large-v3"]);
	});

	it("a local activation leaves NO cloud model active (provider still set)", () => {
		const c = makeConfig({
			asr_backend: "whisper",
			model_size: "large-v3",
			// The cloud selection survives in config — it is simply not
			// the active backend, so no cloud row may read as active.
			cloud_provider: "groq",
			cloud_model: "whisper-large-v3",
		});
		expect(activeLocalModels(c)).toEqual(["large-v3"]);
		expect(activeCloudModels(c)).toEqual([]);
	});

	it("never reports more than one active model in total, whatever the config", () => {
		const configs: LausuConfig[] = [
			makeConfig({ asr_backend: "whisper", model_size: "large-v3" }),
			makeConfig({ asr_backend: "qwen", model_size: "qwen3-1.7b" }),
			makeConfig({ asr_backend: "parakeet", model_size: "parakeet" }),
			makeConfig({
				asr_backend: "cloud",
				model_size: "large-v3",
				cloud_provider: "openai",
				cloud_model: "whisper-1",
			}),
			makeConfig({
				asr_backend: "cloud",
				model_size: "tiny",
				cloud_provider: "gemini",
				cloud_model: "",
			}),
		];
		for (const c of configs) {
			const total = activeLocalModels(c).length + activeCloudModels(c).length;
			expect(total, `config ${JSON.stringify(c)}`).toBeLessThanOrEqual(1);
		}
	});
});

// ── "is a model selected at all?" across both tabs ────────────────────
// Home's red "No model selected" hint and the Models page's dismissible
// banner both used to ask `cfg.model_size === ""`, a LOCAL-only question.
// A cloud activation writes asr_backend / cloud_provider / cloud_model and
// leaves model_size untouched, so a cloud-only user was told their model
// was missing while dictation worked.
describe("hasActiveSpeechModel / isNoModelSelected", () => {
	it("a local selection counts", () => {
		const c = makeConfig({ asr_backend: "whisper", model_size: "large-v3" });
		expect(hasActiveSpeechModel(c)).toBe(true);
		expect(isNoModelSelected(c)).toBe(false);
	});

	it("an active cloud provider counts even with an EMPTY model_size", () => {
		const c = makeConfig({
			asr_backend: "cloud",
			model_size: "",
			cloud_provider: "groq",
			cloud_model: "whisper-large-v3",
		});
		expect(hasActiveSpeechModel(c)).toBe(true);
		expect(isNoModelSelected(c)).toBe(false);
	});

	it("cloud as the backend with NO provider does not count (it degrades to whisper)", () => {
		const c = makeConfig({
			asr_backend: "cloud",
			model_size: "",
			cloud_provider: "",
		});
		expect(hasActiveSpeechModel(c)).toBe(false);
		expect(isNoModelSelected(c)).toBe(true);
	});

	it("a provider set while a LOCAL backend is active does not count", () => {
		// The cloud selection survives in config; it is simply not the
		// active backend, so it is not a selected model.
		const c = makeConfig({
			asr_backend: "whisper",
			model_size: "",
			cloud_provider: "groq",
			cloud_model: "whisper-large-v3",
		});
		expect(hasActiveSpeechModel(c)).toBe(false);
		expect(isNoModelSelected(c)).toBe(true);
	});

	it("nothing selected anywhere reads as no model", () => {
		expect(isNoModelSelected(makeConfig({}))).toBe(true);
	});

	it("a null config is 'not loaded yet', never 'no model selected'", () => {
		// Preserves the pre-existing semantics: the loading frame must not
		// flash the red hint, and the Models page's dismissed-flag effect
		// must not clear itself on mount.
		expect(hasActiveSpeechModel(null)).toBe(false);
		expect(isNoModelSelected(null)).toBe(false);
	});
});
