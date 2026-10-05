// Selected-plugin id for the Plugins detail view. The `Page` union has no
// `pluginDetail` literal (one sidebar destination owns both views), so the
// id travels through this one-shot store instead of the nav history —
// same pattern as `stores/useModelsTab.ts`. Kept local to the plugins
// package so no shared navigation module has to grow a plugin-specific
// deep-link option.

import { create } from "zustand";

interface PluginSelectionState {
	/** Null while the list view is showing. */
	selectedPluginId: string | null;
	selectPlugin: (pluginId: string) => void;
	clearSelection: () => void;
}

export const usePluginSelection = create<PluginSelectionState>((set) => ({
	selectedPluginId: null,
	selectPlugin: (pluginId) => set({ selectedPluginId: pluginId }),
	clearSelection: () => set({ selectedPluginId: null }),
}));
