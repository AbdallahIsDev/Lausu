// The canonical registry of the Settings landing rows and their section
// pages. One hub card lists SETTINGS_HUB_ROWS; every row either opens a
// Settings section page (settingsGeneral … settingsAdvanced) or an
// existing full page (Chat, Providers). The section subset is also used
// for the sidebar's roving-tabindex fallback, search deep links and
// route-chunk prefetch; `Page` in types/ipc/enums.ts must stay in sync.

import {
	AiBrain03Icon,
	CpuIcon,
	KeyboardIcon,
	MessageMultiple01Icon,
	PaintBoardIcon,
	Shield01Icon,
	SlidersHorizontalIcon,
	TextIcon,
	VolumeHighIcon,
} from "@hugeicons/core-free-icons";
import type { IconSvgElement } from "@hugeicons/react";
import type { Page } from "@/types/ipc";

/** Pages that render a focused Settings section card set. */
export const SETTINGS_SECTION_PAGES = [
	"settingsGeneral",
	"settingsHotkeys",
	"settingsTranscription",
	"settingsAudio",
	"settingsAppearance",
	"settingsPrivacy",
	"settingsAdvanced",
] as const;

export type SettingsSectionPage = (typeof SETTINGS_SECTION_PAGES)[number];

/** Every page reachable from a Settings hub row. */
export type SettingsHubPage = SettingsSectionPage | "chat" | "providers";

export function settingsSkeletonId(
	page: SettingsSectionPage | "settings",
): string {
	return page === "settings" ? "settings-hub" : `settings-page-${page}`;
}

export interface SettingsHubRow {
	page: SettingsHubPage;
	/** i18n key for the row title (and the destination heading). */
	titleKey: string;
	/** i18n key for search keywords. No longer rendered on the row. */
	descriptionKey: string;
	icon: IconSvgElement;
}

type RowData = Omit<SettingsHubRow, "page">;

const SETTINGS_HUB_ROW_DEFS: Record<SettingsHubPage, RowData> = {
	settingsGeneral: {
		titleKey: "settings.generalOverlayTitle",
		descriptionKey: "settings.generalOverlayDescription",
		icon: SlidersHorizontalIcon,
	},
	settingsHotkeys: {
		titleKey: "settings.hotkeysRecordingTitle",
		descriptionKey: "settings.hotkeysRecordingDescription",
		icon: KeyboardIcon,
	},
	settingsTranscription: {
		titleKey: "settings.textEnhancementTitle",
		descriptionKey: "settings.textEnhancementDescription",
		icon: TextIcon,
	},
	settingsAudio: {
		titleKey: "settings.audioEnhancement.title",
		descriptionKey: "settings.audioEnhancement.description",
		icon: VolumeHighIcon,
	},
	settingsAppearance: {
		titleKey: "settings.appearance.title",
		descriptionKey: "settings.appearance.description",
		icon: PaintBoardIcon,
	},
	settingsPrivacy: {
		titleKey: "settings.privacyConsentTitle",
		descriptionKey: "settings.privacyConsentDescription",
		icon: Shield01Icon,
	},
	settingsAdvanced: {
		titleKey: "settings.hub.advancedTitle",
		descriptionKey: "settings.hub.advancedDescription",
		icon: CpuIcon,
	},
	chat: {
		titleKey: "nav.chat",
		descriptionKey: "settings.hub.chatDescription",
		icon: MessageMultiple01Icon,
	},
	providers: {
		titleKey: "nav.providers",
		descriptionKey: "settings.hub.providersDescription",
		icon: AiBrain03Icon,
	},
};

/** Landing rows, in display order. Chat and Providers are appended. */
export const SETTINGS_HUB_ROWS: readonly SettingsHubRow[] = (
	[...SETTINGS_SECTION_PAGES, "chat", "providers"] as SettingsHubPage[]
).map((page) => ({ page, ...SETTINGS_HUB_ROW_DEFS[page] }));

/** Row title keys for document titles + search result group headers. */
export const SECTION_TITLE_BY_PAGE: Record<SettingsHubPage, string> =
	Object.fromEntries(
		SETTINGS_HUB_ROWS.map((row) => [row.page, row.titleKey]),
	) as Record<SettingsHubPage, string>;

export function isSettingsSectionPage(page: Page): page is SettingsSectionPage {
	return (SETTINGS_SECTION_PAGES as readonly string[]).includes(page);
}

export function isSettingsSurface(
	page: Page,
): page is SettingsSectionPage | "settings" {
	return page === "settings" || isSettingsSectionPage(page);
}
