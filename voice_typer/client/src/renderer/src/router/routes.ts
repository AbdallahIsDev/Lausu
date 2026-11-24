import type { Page } from "../types/ipc";

export interface RouteDef {
	page: Page;
}

export const ROUTES: Record<Page, RouteDef> = {
	home: { page: "home" },
	chat: { page: "chat" },
	history: { page: "history" },
	microphone: { page: "microphone" },
	models: { page: "models" },
	templates: { page: "templates" },
	vocabulary: { page: "vocabulary" },
	media: { page: "media" },
	plugins: { page: "plugins" },
	providers: { page: "providers" },
	dictionarySnippets: { page: "dictionarySnippets" },
	settings: { page: "settings" },
	settingsGeneral: { page: "settingsGeneral" },
	settingsOverlay: { page: "settingsOverlay" },
	settingsDictionarySnippets: { page: "settingsDictionarySnippets" },
	settingsHotkeys: { page: "settingsHotkeys" },
	settingsTranscription: { page: "settingsTranscription" },
	settingsAudio: { page: "settingsAudio" },
	settingsAppearance: { page: "settingsAppearance" },
	settingsPrivacy: { page: "settingsPrivacy" },
	settingsAboutPrivacy: { page: "settingsAboutPrivacy" },
	settingsAdvanced: { page: "settingsAdvanced" },
	analytics: { page: "analytics" },
	aboutAndPrivacy: { page: "aboutAndPrivacy" },
	onboarding: { page: "onboarding" },
};

export function isKnownPage(path: unknown): path is Page {
	return typeof path === "string" && path in ROUTES;
}

/** The tab a legacy collection route selects on the merged page. */
export type DictionaryTab = "dictionary" | "snippets";

export interface ResolvedRoute {
	page: Page;
	dictionaryTab?: DictionaryTab;
}

// Legacy deep links (settings sections, old collection pages, About) stay
// VALID but land on their current home. One table is consumed by the nav
// store (so every caller — tray, onboarding, search — is remapped at the
// source) and by PageSwitch (defence in depth for a direct route render).
const LEGACY_ROUTES: Partial<Record<Page, ResolvedRoute>> = {
	settingsOverlay: { page: "settingsGeneral" },
	settingsDictionarySnippets: { page: "dictionarySnippets" },
	settingsAboutPrivacy: { page: "settingsPrivacy" },
	aboutAndPrivacy: { page: "settingsPrivacy" },
	// The standalone Plugins page moved into Models as a gated developer tab.
	plugins: { page: "models" },
	templates: { page: "dictionarySnippets", dictionaryTab: "snippets" },
	vocabulary: { page: "dictionarySnippets", dictionaryTab: "dictionary" },
};

export function resolvePageAlias(page: Page): ResolvedRoute {
	return LEGACY_ROUTES[page] ?? { page };
}

export function isLegacyPage(page: Page): boolean {
	return page in LEGACY_ROUTES;
}
