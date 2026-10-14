import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import {
	applyActiveState,
	getActiveFamilyId,
	isModelActive,
	MODEL_DEFAULT,
	type ModelInfo,
	resolveActiveModel,
} from "@/lib/utils/models";
import { MODEL_DEFAULT as MODEL_DEFAULT_COMPAT } from "@/pages/onboarding/lib/constants";
import type { LausuConfig } from "@/types/config";
import type { ModelStatusMap } from "@/types/ipc";

function makeStatus(downloaded: boolean): ModelStatusMap {
	return {
		tiny: { downloaded, deps_ok: true },
	};
}

function makeModel(backend: string, name = backend): ModelInfo {
	return {
		name,
		size: "~1MB",
		speed: "Fast",
		backend,
		downloaded: false,
		depsOk: true,
		isActive: false,
	};
}

function makeConfig(model_size: string): LausuConfig {
	return {
		model_size,
		asr_backend: "whisper",
	} as LausuConfig;
}

describe("isModelActive, empty model_size means nothing is active", () => {
	it("returns false for whisper models when activeModel is empty", () => {
		expect(isModelActive(makeModel("whisper", "tiny"), "whisper", "")).toBe(
			false,
		);
	});

	it("returns false for backend-keyed models (qwen/parakeet) when activeModel is empty", () => {
		// qwen / parakeet are keyed by backend alone, without the guard
		// they would render active even with an empty model_size.
		expect(isModelActive(makeModel("qwen"), "qwen", "")).toBe(false);
		expect(isModelActive(makeModel("parakeet"), "parakeet", "")).toBe(false);
	});

	it("still returns true for a real selection", () => {
		expect(isModelActive(makeModel("whisper", "tiny"), "whisper", "tiny")).toBe(
			true,
		);
	});
});
describe("applyActiveState / getActiveFamilyId with no model selected", () => {
	it("clears every active flag when model_size is empty", () => {
		const models = [
			makeModel("whisper", "tiny"),
			makeModel("qwen"),
			makeModel("parakeet"),
		];
		const applied = applyActiveState(models, makeConfig(""));
		expect(applied.every((m) => !m.isActive)).toBe(true);
	});

	it("getActiveFamilyId returns null when model_size is empty", () => {
		expect(getActiveFamilyId(makeConfig(""))).toBeNull();
	});
});

describe("resolveActiveModel, shared no-model truth (Analytics + About)", () => {
	it("returns null/null when the configured model is empty (no model selected)", () => {
		expect(resolveActiveModel("", makeStatus(true), "cuda")).toEqual({
			model: null,
			device: null,
		});
	});
	it("returns null/null when the configured model's weights are NOT on disk", () => {
		// Config defaults to "tiny" / "cuda" even with nothing
		// installed, the resolver must NOT surface them.
		expect(resolveActiveModel("tiny", makeStatus(false), "cuda")).toEqual({
			model: null,
			device: null,
		});
	});

	it("returns null/null when the status map lacks the configured model", () => {
		expect(resolveActiveModel("tiny", {}, "cuda")).toEqual({
			model: null,
			device: null,
		});
	});

	it("returns the REAL model + device when the weights are installed", () => {
		expect(resolveActiveModel("tiny", makeStatus(true), "cuda")).toEqual({
			model: "tiny",
			device: "cuda",
		});
	});

	it("returns the real model with a null device when the config lacks one", () => {
		expect(resolveActiveModel("tiny", makeStatus(true), undefined)).toEqual({
			model: "tiny",
			device: null,
		});
	});
});

describe("MODEL_DEFAULT, canonical home + compat re-export", () => {
	it("is the empty-string no-model sentinel (must stay in lockstep with the backend DEFAULT_MODEL_SIZE)", () => {
		// The value itself is pinned so a naive "tiny" reintroduction
		// fails here before it can phantom-mark a model active.
		expect(MODEL_DEFAULT).toBe("");
	});

	it("is the SAME binding via the onboarding constants re-export (compat importers see the canonical value)", () => {
		// The onboarding constants module re-exports the lib constant —
		// both import paths must resolve to the identical value so the
		// wizard and the models lib can never drift apart.
		expect(MODEL_DEFAULT_COMPAT).toBe(MODEL_DEFAULT);
	});

	it("every lib/utils model module is free of pages-layer imports (lib must never import from pages, inverted layering)", () => {
		// Source-scan guard for the layering contract: comments are
		// stripped first so a doc mention of the pages layer cannot
		// false-positive.
		for (const file of [
			"src/renderer/src/lib/utils/models.ts",
			"src/renderer/src/lib/utils/modelCatalog.ts",
			"src/renderer/src/lib/utils/cloudCatalog.ts",
			"src/renderer/src/lib/utils/modelActive.ts",
			"src/renderer/src/lib/utils/format.ts",
		]) {
			const src = readFileSync(file, "utf8")
				.replace(/\/\*[\s\S]*?\*\//g, "")
				.replace(/\/\/.*$/gm, "");
			expect(src, file).not.toMatch(/from\s+["']@\/pages\//);
		}
	});
});
