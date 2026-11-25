import { describe, expect, it } from "vitest";
import { activeEngine } from "@/lib/utils/activeEngine";
import {
	applyActiveState,
	hasActiveSpeechModel,
} from "@/lib/utils/modelActive";
import type { LausuConfig } from "@/types/config";

const base = {
	model_size: "parakeet",
	asr_backend: "parakeet",
	active_plugin: "",
} as unknown as LausuConfig;

describe("activeEngine — one answer for sidebar, Models, tray and hotkey", () => {
	it("reports a plugin when a plugin owns dictation, even with a model configured", () => {
		const cfg = {
			...base,
			active_plugin: "anthropic_stt",
			active_plugin_name: "Claude STT",
		} as unknown as LausuConfig;
		expect(activeEngine(cfg)).toEqual({ kind: "plugin", name: "Claude STT" });
		const models = applyActiveState(
			[
				{
					name: "parakeet",
					backend: "parakeet",
					size: "~1MB",
					speed: "Fast",
					downloaded: true,
					depsOk: true,
					isActive: true,
				},
			],
			cfg,
		);
		expect(models.every((m) => !m.isActive)).toBe(true);
		expect(hasActiveSpeechModel(cfg)).toBe(true);
	});

	it("reports the local model only when no plugin owns dictation", () => {
		expect(activeEngine(base)).toEqual({ kind: "local" });
	});

	it("reports none when there is no plugin and no model", () => {
		const cfg = {
			...base,
			model_size: "",
			asr_backend: "",
		} as unknown as LausuConfig;
		expect(activeEngine(cfg)).toEqual({ kind: "none" });
		expect(hasActiveSpeechModel(cfg)).toBe(false);
	});
});
