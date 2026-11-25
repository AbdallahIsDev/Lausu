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

const mockPluginsAvailable = vi.fn<() => boolean>();
vi.mock("@/hooks/usePluginCatalog", () => ({
	usePluginsAvailable: () => mockPluginsAvailable(),
	usePluginsUnlocked: () => mockPluginsAvailable(),
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

function navButtons(): HTMLElement[] {
	return Array.from(
		document.querySelectorAll<HTMLElement>(
			'nav[aria-label="Main navigation"] button',
		),
	);
}

describe("Sidebar, Plugins is no longer a sidebar destination", () => {
	afterEach(() => {
		cleanup();
		vi.clearAllMocks();
	});

	it("never shows Plugins, even on a developer install", () => {
		mockPluginsAvailable.mockReturnValue(true);
		renderSidebar();
		expect(screen.queryByText(t("nav.plugins"))).toBeNull();
	});

	it("shows the same nav on shipped installs", () => {
		mockPluginsAvailable.mockReturnValue(false);
		renderSidebar();
		expect(screen.getByText(t("nav.home"))).toBeTruthy();
		expect(screen.getByText(t("nav.history"))).toBeTruthy();
		expect(screen.getByText(t("nav.settings"))).toBeTruthy();
	});

	it("keeps the gated nav item out of paint and keyboard order", () => {
		mockPluginsAvailable.mockReturnValue(true);
		renderSidebar();
		const labels = navButtons().map((b) => b.textContent ?? "");
		expect(labels.some((l) => l.includes(t("nav.plugins")))).toBe(false);
	});

	it("does not change the nav length with the developer flag", () => {
		mockPluginsAvailable.mockReturnValue(true);
		renderSidebar();
		const withGate = navButtons().length;
		cleanup();
		mockPluginsAvailable.mockReturnValue(false);
		renderSidebar();
		expect(navButtons().length).toBe(withGate);
	});
});
