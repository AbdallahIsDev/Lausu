import type { PluginInfo } from "@/types/plugins";

// Measured-skeleton sample for the Plugins list. `registry.discover()`
// answers `[]` on a build without a plugin workspace (the shipped case),
// and the page renders its empty state for that — so the sample is the
// empty list too. Four invented cards measured a grid the page never
// showed on first load.
export const SAMPLE_PLUGINS: PluginInfo[] = [];

// Detail sample: one full plugin with two settings so the detail page
// measures its heading plus both setting rows while loading.
export const SAMPLE_PLUGIN_DETAIL: PluginInfo = {
	id: "sample-plugin-alpha",
	name: "Alpha Dictation",
	description: "Sample plugin for skeleton measurement.",
	vendor: "Sample Vendor",
	icon: "",
	active: true,
	settings: [
		{
			key: "enabled",
			type: "bool",
			label: "Enabled",
			description: "Turn this sample setting on.",
			default: true,
		},
		{
			key: "mode",
			type: "string",
			label: "Mode",
			description: "Sample text setting.",
			default: "standard",
		},
	],
	values: { enabled: true, mode: "standard" },
};
