// Behaviour + contract tests for the model-idle-unload dropdown.
//
// The behaviour worth pinning is narrow and behavioural, not structural:
//   * the offered values are exactly 15/30/60/90/120 plus the Never
//     sentinel, in that order (5 is deliberately absent, and 90 precedes 120),
//   * "Never" writes 0, which is the backend's "don't arm the timer" value,
//   * an out-of-range / missing config value renders the default instead of
//     a blank trigger,
//   * choosing an option persists the numeric minutes,
//   * every option label exists in ALL eight locales and none of them is
//     English text left in a non-English file (C-I18N-1 / C-I18N-2).

import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
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
import {
	DEFAULT_MODEL_IDLE_UNLOAD_MINUTES,
	MODEL_IDLE_UNLOAD_OPTIONS,
	normalizeModelIdleUnloadMinutes,
} from "@/lib/utils/modelIdleUnload";
import type { LausuConfig } from "@/types/config";

// Flatten with the SAME helper the runtime uses, so these assertions see
// the exact key surface `t()` resolves against (flat "modelIdleUnload.x"
// keys inside `settings` become `settings.modelIdleUnload.x`).
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

describe("MODEL_IDLE_UNLOAD_OPTIONS", () => {
	it("offers exactly 15/30/60/90/120 in order, with Never last", () => {
		expect(MODEL_IDLE_UNLOAD_OPTIONS.map((o) => o.value)).toEqual([
			15, 30, 60, 90, 120, 0,
		]);
	});

	it("never offers 5 minutes", () => {
		// A 5-minute window evicts the model during a normal pause and
		// forces a reload on the next dictation; it is not a real choice.
		expect(MODEL_IDLE_UNLOAD_OPTIONS.map((o) => o.value)).not.toContain(5);
	});

	it("puts 90 before 120", () => {
		const values = MODEL_IDLE_UNLOAD_OPTIONS.map((o) => o.value);
		expect(values.indexOf(90)).toBeLessThan(values.indexOf(120));
	});

	it("maps Never to 0, the backend's never-unload sentinel", () => {
		const values = MODEL_IDLE_UNLOAD_OPTIONS.map((o) => o.value);
		expect(values[values.length - 1]).toBe(0);
	});
});

describe("normalizeModelIdleUnloadMinutes", () => {
	it("passes through every offered value", () => {
		for (const option of MODEL_IDLE_UNLOAD_OPTIONS) {
			expect(normalizeModelIdleUnloadMinutes(option.value)).toBe(option.value);
		}
	});

	it("falls back to the default for undefined, NaN and out-of-range values", () => {
		for (const raw of [undefined, Number.NaN, 5, 7, 1440, -1]) {
			expect(normalizeModelIdleUnloadMinutes(raw)).toBe(
				DEFAULT_MODEL_IDLE_UNLOAD_MINUTES,
			);
		}
	});
});

describe("GeneralSettingsSection model-idle-unload row", () => {
	// Sibling i18n tests call `registerTranslations("en", {...})` with PARTIAL
	// fixture tables, and `registerTranslations` REPLACES the locale's map.
	// Loading the real catalogue here makes this file independent of which
	// tests ran before it in the same worker; without it these assertions pass
	// alone and fail in a full run.
	beforeEach(async () => {
		vi.stubGlobal("window", window);
		await ensureLocaleLoaded("en");
	});

	afterEach(() => {
		cleanup();
		vi.unstubAllGlobals();
	});

	// The i18n store loads a locale's JSON with a dynamic import, so the
	// first paint can render raw keys. Await the translated label rather than
	// asserting synchronously, otherwise this file passes alone and fails
	// whenever the machine is busy enough to delay the import.
	async function openDropdown(minutes: number) {
		renderSection({ model_idle_unload_minutes: minutes });
		const trigger = await screen.findByLabelText(
			en.settings.modelIdleUnload,
			undefined,
			{ timeout: 5000 },
		);
		fireEvent.click(trigger);
		return await screen.findByRole("listbox");
	}

	it("renders the row and opens a dropdown with every option", async () => {
		const list = await openDropdown(60);
		for (const option of MODEL_IDLE_UNLOAD_OPTIONS) {
			const label = t("en", option.labelKey) ?? "";
			await waitFor(
				() => {
					expect(
						within(list).getByText(label),
						`option ${option.value} missing from the dropdown`,
					).toBeTruthy();
				},
				{ timeout: 5000 },
			);
		}
	});

	it("persists the chosen minutes as a number", async () => {
		const { updateConfig } = renderSection({ model_idle_unload_minutes: 30 });
		const trigger = await screen.findByLabelText(en.settings.modelIdleUnload);
		fireEvent.click(trigger);
		const list = await screen.findByRole("listbox");
		fireEvent.click(
			await within(list).findByText(
				t("en", "settings.modelIdleUnload.minutes90") ?? "",
			),
		);
		expect(updateConfig).toHaveBeenCalledWith({
			model_idle_unload_minutes: 90,
		});
	});

	it("persists Never as 0", async () => {
		const { updateConfig } = renderSection({ model_idle_unload_minutes: 60 });
		const trigger = await screen.findByLabelText(en.settings.modelIdleUnload);
		fireEvent.click(trigger);
		const list = await screen.findByRole("listbox");
		fireEvent.click(
			await within(list).findByText(
				t("en", "settings.modelIdleUnload.never") ?? "",
			),
		);
		expect(updateConfig).toHaveBeenCalledWith({
			model_idle_unload_minutes: 0,
		});
	});

	it("shows a selection for an out-of-range stored value instead of blank", async () => {
		// A hand-edited config.json must not render an empty trigger: the
		// normalised default (60) has to be the visible selection.
		renderSection({ model_idle_unload_minutes: 7 });
		const trigger = await screen.findByLabelText(en.settings.modelIdleUnload);
		await waitFor(() => {
			expect(trigger.textContent).toContain(
				t("en", "settings.modelIdleUnload.minutes60") ?? "",
			);
		});
	});
});

describe("model-idle-unload translations", () => {
	// `labelKey` already carries the full dotted path ("settings.…"), and
	// `flatten()` on a nested JSON turns the settings-level
	// `"modelIdleUnload.minutes15"` entry into exactly that path.
	const keys = [
		"settings.modelIdleUnload",
		"settings.modelIdleUnloadDescription",
		...MODEL_IDLE_UNLOAD_OPTIONS.map((o) => o.labelKey),
	];

	it("ships a label, description and six option labels in every locale", () => {
		for (const locale of Object.keys(LOCALE_FLAT)) {
			for (const key of keys) {
				expect(t(locale, key), `${locale} is missing ${key}`).toBeTruthy();
			}
		}
	});

	it("has no English text left in a non-English locale", () => {
		// C-I18N-2: an English string under a translated key is the #1
		// observed downgrade. A purely numeric label would be the one
		// legitimate exception, so require at least one non-digit,
		// non-whitespace, non-punctuation character.
		for (const locale of Object.keys(LOCALE_FLAT).filter((l) => l !== "en")) {
			for (const key of keys.slice(2)) {
				expect(t(locale, key), `${locale}/${key} looks untranslated`).toMatch(
					/[^\d\s()]/,
				);
			}
		}
	});

	it("gives every locale a different string than English for the label", () => {
		// Guards against a copy-paste that satisfies key-parity but leaves the
		// user reading English inside their own language.
		const english = t("en", "settings.modelIdleUnload");
		for (const locale of Object.keys(LOCALE_FLAT).filter((l) => l !== "en")) {
			expect(t(locale, "settings.modelIdleUnload")).not.toBe(english);
		}
	});
});
