// One answer to "what is dictating?" — shared by the sidebar, Models page,
// tray mirror and hotkey guard. The plugin name is pushed with `get_config`
// (`active_plugin_name`); the raw model fields can be stale while it is set.

import type { LausuConfig } from "@/types/config";
import { hasActiveSpeechModel } from "./modelActive";

export type ActiveEngine =
	| { kind: "plugin"; name: string }
	| { kind: "local" }
	| { kind: "none" };

export function activeEngine(cfg: Partial<LausuConfig> | null): ActiveEngine {
	const pluginName = cfg?.active_plugin_name?.trim() ?? "";
	if (pluginName) return { kind: "plugin", name: pluginName };
	// Cloud without a provider is a proven "none" even before model_size
	// hydrates. For local backends, an absent (not empty) model_size means the
	// config is still loading — never hide the UI mid-boot (C-CACHE-10).
	if (cfg?.asr_backend === "cloud") {
		return (cfg.cloud_provider ?? "") !== ""
			? { kind: "local" }
			: { kind: "none" };
	}
	if (cfg?.model_size === undefined) return { kind: "local" };
	if (hasActiveSpeechModel(cfg)) return { kind: "local" };
	return { kind: "none" };
}

/** True only when a plugin currently owns the hotkey. */
export function pluginOwnsDictation(cfg: LausuConfig | null): boolean {
	return activeEngine(cfg).kind === "plugin";
}
