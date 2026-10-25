import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
	formatModelDisplayName,
	formatModelSize,
	getModelVariantDisplayName,
	INITIAL_MODELS,
	type ModelInfo,
	requiresHuggingFaceConsent,
} from "@/lib/utils/models";

function makeModel(name: string, backend: string): ModelInfo {
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

describe("formatModelDisplayName, slug → display label (display-layer only)", () => {
	it("capitalizes single-word slugs", () => {
		expect(formatModelDisplayName("tiny")).toBe("Tiny");
		expect(formatModelDisplayName("qwen3")).toBe("Qwen3");
		expect(formatModelDisplayName("parakeet")).toBe("Parakeet");
	});

	it("treats each hyphen as a word separator and Title-Cases each word", () => {
		expect(formatModelDisplayName("large-v3")).toBe("Large V3");
		expect(formatModelDisplayName("large-v3-turbo")).toBe("Large V3 Turbo");
		expect(formatModelDisplayName("whisper-1")).toBe("Whisper 1");
		expect(formatModelDisplayName("nova-2")).toBe("Nova 2");
	});

	it("never alters the raw slug (presentation-only formatting)", () => {
		const slug = "large-v3-turbo";
		formatModelDisplayName(slug);
		expect(slug).toBe("large-v3-turbo");
	});

	it("handles edge cases (empty / consecutive hyphens)", () => {
		expect(formatModelDisplayName("")).toBe("");
		expect(formatModelDisplayName("a--b")).toBe("A B");
	});
});

describe("getModelVariantDisplayName, family prefix + display_name priority", () => {
	it("prepends 'Whisper' to formatted whisper-variant slugs", () => {
		expect(getModelVariantDisplayName(makeModel("tiny", "whisper"))).toBe(
			"Whisper Tiny",
		);
		expect(getModelVariantDisplayName(makeModel("large-v3", "whisper"))).toBe(
			"Whisper Large V3",
		);
		expect(
			getModelVariantDisplayName(makeModel("large-v3-turbo", "whisper")),
		).toBe("Whisper Large V3 Turbo");
	});

	it("keeps the backend display_name as the top priority (no double prefix)", () => {
		expect(
			getModelVariantDisplayName(makeModel("parakeet", "parakeet"), {
				display_name: "Parakeet-TDT-0.6b-V3",
			} as never),
		).toBe("Parakeet-TDT-0.6b-V3");
		expect(
			getModelVariantDisplayName(makeModel("qwen3-1.7b", "qwen"), {
				display_name: "Qwen-3",
			} as never),
		).toBe("Qwen-3");
	});

	it("formats non-whisper slugs without a family prefix", () => {
		expect(getModelVariantDisplayName(makeModel("parakeet", "parakeet"))).toBe(
			"Parakeet",
		);
	});

	it("uses the catalogue displayName for the two Qwen sizes", () => {
		for (const name of ["qwen3-1.7b", "qwen3-0.6b"]) {
			const info = INITIAL_MODELS.find((m) => m.name === name);
			expect(info, name).toBeDefined();
			if (!info) continue;
			expect(getModelVariantDisplayName(info)).toBe(info.displayName);
		}
	});

	it("mirrors the backend registry display names (catalogue ↔ model_registry.py)", () => {
		const source = readFileSync(
			resolve(process.cwd(), "../../voice_typer/server/model_registry.py"),
			"utf-8",
		);
		for (const name of ["qwen3-1.7b", "qwen3-0.6b"]) {
			const block = new RegExp(
				`"${name}": ModelMetadata\\(([\\s\\S]*?)\\n    \\),`,
			).exec(source);
			expect(block, `${name} entry in model_registry.py`).not.toBeNull();
			const registryName = /display_name="([^"]+)"/.exec(block?.[1] ?? "")?.[1];
			const info = INITIAL_MODELS.find((m) => m.name === name);
			expect(info?.displayName, name).toBe(registryName);
		}
	});
});

describe("requiresHuggingFaceConsent, JIT consent gate scope (point 4)", () => {
	it("gates whisper + parakeet (HF-downloading models)", () => {
		expect(requiresHuggingFaceConsent(makeModel("tiny", "whisper"))).toBe(true);
		expect(
			requiresHuggingFaceConsent(makeModel("large-v3", "distil-whisper")),
		).toBe(true);
		expect(requiresHuggingFaceConsent(makeModel("parakeet", "parakeet"))).toBe(
			true,
		);
	});

	it("gates every Qwen size too (both download their ONNX export from HF)", () => {
		expect(requiresHuggingFaceConsent(makeModel("qwen3-1.7b", "qwen"))).toBe(
			true,
		);
		expect(requiresHuggingFaceConsent(makeModel("qwen3-0.6b", "qwen"))).toBe(
			true,
		);
	});
});

describe("formatModelSize, canonical `<number> <UNIT>` display (2026-08-21)", () => {
	it("strips the ~ approximation marker and inserts the number/unit space", () => {
		expect(formatModelSize("~75MB")).toBe("75 MB");
		expect(formatModelSize("~3GB")).toBe("3 GB");
		expect(formatModelSize("~809MB")).toBe("809 MB");
		expect(formatModelSize("~2.5GB")).toBe("2.5 GB");
	});

	it("normalizes an already-canonical size (no-op) and the ≈ marker", () => {
		expect(formatModelSize("75 MB")).toBe("75 MB");
		expect(formatModelSize("≈809MB")).toBe("809 MB");
	});

	it("uppercases the unit and trims surrounding whitespace", () => {
		expect(formatModelSize(" 3gb ")).toBe("3 GB");
		expect(formatModelSize("999TB")).toBe("999 TB");
		// Generic for arbitrary providers, supports a potential TB size.
		expect(formatModelSize("~1.2TB")).toBe("1.2 TB");
	});

	it("keeps the Variable sentinel translated", () => {
		expect(formatModelSize("Variable")).toBe("Variable");
	});

	it("passes through unrecognized strings untouched", () => {
		expect(formatModelSize("custom-path")).toBe("custom-path");
	});
});
