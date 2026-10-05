// Behaviour + contract tests for the streaming-transcription toggle.
//
// Pins the narrow behaviour surface: the switch reflects
// config.streaming_transcription (defaulting ON for missing values),
// flipping it persists the boolean, and both keys exist in ALL eight
// locales with genuine translations (C-I18N-1 / C-I18N-2).

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GeneralSettingsSection } from "@/components/settings/GeneralSettingsSection";
import type { SettingsSectionSharedProps } from "@/components/settings/types";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ensureLocaleLoaded, flatten } from "@/i18n/store";
import ar from "@/i18n/translations/ar.json";
import de from "@/i18n/translations/de.json";
import en from "@/i18n/translations/en.json";
import es from "@/i18n/translations/es.json";
import fr from "@/i18n/translations/fr.json";
import hi from "@/i18n/translations/hi.json";
import ru from "@/i18n/translations/ru.json";
import zh from "@/i18n/translations/zh.json";
import type { LausuConfig } from "@/types/config";

const LOCALE_FLAT: Record<string, Map<string, string>> = {
	ar: flatten(ar as Record<string, unknown>),
	de: flatten(de as Record<string, unknown>),
	en: flatten(en as Record<string, unknown>),
	es: flatten(es as Record<string, unknown>),
	fr: flatten(fr as Record<string, unknown>),
	hi: flatten(hi as Record<string, unknown>),
	ru: flatten(ru as Record<string, unknown>),
	zh: flatten(zh as Record<string, unknown>),
};

function t(locale: string, key: string): string | undefined {
	return LOCALE_FLAT[locale]?.get(key);
}

function baseConfig(): LausuConfig {
	return {
		autostart: false,
		language: "auto",
		device: "cpu",
		model_size: "large-v3",
		active_plugin: "",
		fast_startup: true,
		show_notifications: true,
		tray_left_click_action: "toggle_dictation",
	} as unknown as LausuConfig;
}

function renderSection(overrides: Partial<LausuConfig> = {}) {
	const updateConfig = vi.fn();
	const props: SettingsSectionSharedProps = {
		config: { ...baseConfig(), ...overrides },
		updateConfig,
		updateConfigDebounced: vi.fn(),
		isVisible: () => true,
	};
	render(
		<TooltipProvider>
			<GeneralSettingsSection {...props} />
		</TooltipProvider>,
	);
	return { updateConfig };
}

describe("GeneralSettingsSection streaming-transcription row", () => {
	beforeEach(async () => {
		vi.stubGlobal("window", window);
		await ensureLocaleLoaded("en");
	});

	afterEach(() => {
		cleanup();
		vi.unstubAllGlobals();
	});

	it("renders ON when the config value is true", async () => {
		renderSection({ streaming_transcription: true });
		const toggle = await screen.findByLabelText(
			t("en", "settings.streamingTranscription") ?? "",
		);
		expect(toggle.getAttribute("aria-checked")).toBe("true");
	});

	it("renders ON for a missing value (default ON)", async () => {
		renderSection({ streaming_transcription: undefined });
		const toggle = await screen.findByLabelText(
			t("en", "settings.streamingTranscription") ?? "",
		);
		expect(toggle.getAttribute("aria-checked")).toBe("true");
	});

	it("persists the flipped boolean", async () => {
		const { updateConfig } = renderSection({ streaming_transcription: true });
		const toggle = await screen.findByLabelText(
			t("en", "settings.streamingTranscription") ?? "",
		);
		fireEvent.click(toggle);
		expect(updateConfig).toHaveBeenCalledWith({
			streaming_transcription: false,
		});
	});
});

describe("streamingTranscription locale coverage", () => {
	for (const locale of Object.keys(LOCALE_FLAT)) {
		it(`ships both keys in ${locale}`, () => {
			expect(t(locale, "settings.streamingTranscription")).toBeTruthy();
			expect(
				t(locale, "settings.streamingTranscriptionDescription"),
			).toBeTruthy();
		});
	}

	it("has no untranslated English in non-English locales", () => {
		const english = t("en", "settings.streamingTranscription");
		for (const locale of Object.keys(LOCALE_FLAT)) {
			if (locale === "en") continue;
			expect(t(locale, "settings.streamingTranscription")).not.toBe(english);
		}
	});
});
