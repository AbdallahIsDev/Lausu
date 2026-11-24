import { create } from "zustand";

/** Local / Cloud / Text-to-Speech tab on Models — shared by the page + title-bar switcher.
 *  `plugins` is developer-only: gated in both the switcher and the page. */
export type ModelsTab = "local" | "cloud" | "tts" | "plugins";

export interface ModelsTabState {
	activeTab: ModelsTab;
	setActiveTab: (tab: ModelsTab) => void;
}

function readPersisted(): ModelsTab {
	try {
		const raw = sessionStorage.getItem("vt:filters:models.activeTab");
		const parsed = raw ? (JSON.parse(raw) as ModelsTab) : "local";
		return parsed === "cloud" || parsed === "tts" || parsed === "plugins"
			? parsed
			: "local";
	} catch {
		return "local";
	}
}

export const useModelsTab = create<ModelsTabState>((set) => ({
	activeTab: typeof sessionStorage === "undefined" ? "local" : readPersisted(),
	setActiveTab: (tab: ModelsTab) => {
		try {
			sessionStorage.setItem(
				"vt:filters:models.activeTab",
				JSON.stringify(tab),
			);
		} catch {
			/* best-effort */
		}
		set({ activeTab: tab });
	},
}));
