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
			makeConfig({ asr_backend: "qwen", model_size: "qwen" }),
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
