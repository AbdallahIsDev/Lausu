import { create } from "zustand";

/** Local / Cloud tab on Models — shared by the page + title-bar switcher. */
export type ModelsTab = "local" | "cloud";

export interface ModelsTabState {
	activeTab: ModelsTab;
	setActiveTab: (tab: ModelsTab) => void;
}

function readPersisted(): ModelsTab {
	try {
		const raw = sessionStorage.getItem("vt:filters:models.activeTab");
		const parsed = raw ? (JSON.parse(raw) as ModelsTab) : "local";
		return parsed === "cloud" ? "cloud" : "local";
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
