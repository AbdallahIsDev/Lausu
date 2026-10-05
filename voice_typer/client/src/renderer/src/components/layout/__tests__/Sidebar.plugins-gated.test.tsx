import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({
		children,
		icon,
	}: {
		children?: React.ReactNode;
		icon?: { name?: string };
	}) => (
		<span data-testid="hugeicon" data-name={icon?.name}>
			{children}
		</span>
	),
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

// Gating is driven by the backend's `available` flag. Mocked per test.
const mockPluginsAvailable = vi.fn<() => boolean>();
vi.mock("@/hooks/usePluginCatalog", () => ({
	usePluginsAvailable: () => mockPluginsAvailable(),
}));

import { Sidebar } from "@/components/layout/Sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { t } from "@/i18n/i18n";

function renderSidebar() {
	return render(
		<TooltipProvider delayDuration={200} skipDelayDuration={500}>
			<Sidebar currentPage="home" onNavigate={() => {}} />
		</TooltipProvider>,
	);
}

/** Nav leaf buttons, excluding the submenu flyout. */
function navButtons(): HTMLElement[] {
	return Array.from(
		document.querySelectorAll<HTMLElement>(
			'nav[aria-label="Main navigation"] button',
		),
	);
}

describe("Sidebar, developer-gated Plugins entry", () => {
	afterEach(() => {
		cleanup();
		vi.clearAllMocks();
	});

	it("shows the Plugins destination on a developer install", () => {
		mockPluginsAvailable.mockReturnValue(true);
		renderSidebar();
		expect(screen.getByText(t("nav.plugins"))).toBeTruthy();
	});

	it("hides the Plugins destination on a shipped install", () => {
		mockPluginsAvailable.mockReturnValue(false);
		renderSidebar();
		expect(screen.queryByText(t("nav.plugins"))).toBeNull();
	});

	it("keeps the rest of the nav intact when Plugins is hidden", () => {
		mockPluginsAvailable.mockReturnValue(false);
		renderSidebar();
		// Home / History / Settings must survive the filter.
		expect(screen.getByText(t("nav.home"))).toBeTruthy();
		expect(screen.getByText(t("nav.history"))).toBeTruthy();
	});

	it("drops the gated item from keyboard order, not just the paint", () => {
		// A hidden-but-focusable entry would still be reachable by Tab on a
		// shipped build, so the roving-tabindex order must be filtered too.
		mockPluginsAvailable.mockReturnValue(false);
		renderSidebar();
		const labels = navButtons().map((b) => b.textContent ?? "");
		expect(labels.some((l) => l.includes(t("nav.plugins")))).toBe(false);
	});

	it("adds exactly one entry when the surface is available", () => {
		mockPluginsAvailable.mockReturnValue(true);
		renderSidebar();
		const withGate = navButtons().length;
		cleanup();
		mockPluginsAvailable.mockReturnValue(false);
		renderSidebar();
		const withoutGate = navButtons().length;
		expect(withGate - withoutGate).toBe(1);
	});
});
