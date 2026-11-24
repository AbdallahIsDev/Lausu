import { act, cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Memoized title-bar/sidebar chrome must re-localize in place when the UI
// language changes. These are the same light mocks the layout tests use to
// mount Sidebar and TitleBar without a live backend.
vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({ icon }: { icon?: { name?: string } }) => (
		<span data-testid="hugeicon" data-name={icon?.name} />
	),
}));
vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});
vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: vi.fn() }),
	usePythonEvent: () => () => {},
}));
vi.mock("@/hooks/usePluginCatalog", () => ({
	usePluginsAvailable: () => false,
	usePluginsUnlocked: () => false,
}));
vi.mock("@/components/layout/DeviceToggle", () => ({
	DeviceToggle: () => null,
}));

import { renderWithProviders } from "@/__tests__/helpers/render";
import { GlobalSearchBar } from "@/components/layout/GlobalSearchBar";
import { Sidebar } from "@/components/layout/Sidebar";
import { TitleBar } from "@/components/layout/TitleBar";
import { ensureLocaleLoaded, type Locale, setLocale } from "@/i18n/i18n";

const EN = {
	navHome: "Home",
	goBack: "Go back",
	searchPlaceholder: "Search History",
	localModels: "Local Models",
	analyticsToday: "Today",
};
const AR = {
	navHome: "الرئيسية",
	goBack: "العودة",
	searchPlaceholder: "ابحث في السجل...",
	localModels: "نماذج محلية",
	analyticsToday: "اليوم",
};

function mountChrome() {
	return renderWithProviders(
		<>
			<Sidebar currentPage="home" onNavigate={() => {}} />
			<TitleBar
				isMaximized={false}
				onOpenHelp={() => {}}
				themeMode="light"
				onThemeChange={() => {}}
			/>
			<GlobalSearchBar currentPage="history" />
		</>,
	);
}

describe("memoized chrome re-localizes live on language switch", () => {
	beforeEach(async () => {
		await act(async () => {
			setLocale("en" as Locale);
			await ensureLocaleLoaded("ar" as Locale);
		});
	});

	afterEach(() => {
		act(() => {
			setLocale("en" as Locale);
		});
		cleanup();
	});

	it("relabels nav, title-bar aria and search placeholder in place without remounting", async () => {
		mountChrome();

		// Capture the actual DOM nodes while English is active.
		const navLabel = screen.getByText(EN.navHome);
		const backButton = screen.getByRole("button", { name: EN.goBack });
		const searchInput = screen.getByPlaceholderText(EN.searchPlaceholder);

		await act(async () => {
			setLocale("ar" as Locale);
		});

		// The same nodes now carry the Arabic catalog values — proving an
		// in-place re-render, not a remount that happened to look translated.
		expect(navLabel.textContent).toBe(AR.navHome);
		expect(backButton.getAttribute("aria-label")).toBe(AR.goBack);
		expect((searchInput as HTMLInputElement).placeholder).toBe(
			AR.searchPlaceholder,
		);
		expect(screen.getByText(AR.navHome)).toBe(navLabel);
		expect(screen.getByRole("button", { name: AR.goBack })).toBe(backButton);
		expect(screen.getByPlaceholderText(AR.searchPlaceholder)).toBe(searchInput);
	});

	it("re-localizes the Models and Analytics middle-strip switches in place", async () => {
		function mountStrip(page: "models" | "analytics") {
			return renderWithProviders(
				<TitleBar
					currentPage={page}
					isMaximized={false}
					onOpenHelp={() => {}}
					themeMode="light"
					onThemeChange={() => {}}
				/>,
			);
		}

		mountStrip("models");
		const localTab = screen.getByText(EN.localModels);
		await act(async () => {
			setLocale("ar" as Locale);
		});
		expect(localTab.textContent).toBe(AR.localModels);
		expect(screen.getByText(AR.localModels)).toBe(localTab);
		cleanup();

		await act(async () => {
			setLocale("en" as Locale);
		});
		mountStrip("analytics");
		const todayPill = screen.getByText(EN.analyticsToday);
		await act(async () => {
			setLocale("ar" as Locale);
		});
		expect(todayPill.textContent).toBe(AR.analyticsToday);
		expect(screen.getByText(AR.analyticsToday)).toBe(todayPill);
	});
});
