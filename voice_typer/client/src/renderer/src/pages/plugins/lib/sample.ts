import type { PluginInfo } from "@/types/plugins";

// Measured-skeleton sample for the Plugins list. `registry.discover()`
// answers `[]` on a build without a plugin workspace (the shipped case),
// and the page renders its empty state for that — so the sample is the
// empty list too. Four invented cards measured a grid the page never
// showed on first load.
export const SAMPLE_PLUGINS: PluginInfo[] = [];

// Measured-skeleton sample for the shared-settings block below the cards.
// It reserves the exact heading + two rows while `get_config` is in flight,
// so the page never grows when the real values land (C-SKELETON-1).
export const SAMPLE_ACTIVE_PLUGIN: PluginInfo = {
	id: "sample-active-plugin",
	name: "Sample Dictation",
	description: "Sample plugin description for skeleton measurement.",
	vendor: "Sample Vendor",
	icon: "",
	active: true,
};
