import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The shell must keep the sidebar on the PHYSICAL left in every locale.
// These mocks are the same shape App.test.tsx uses to mount App without a
// live backend: they keep the test focused on the row/main/sidebar geometry.
const { mockCall } = vi.hoisted(() => ({ mockCall: vi.fn() }));

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: mockCall }),
	usePythonEvent: () => () => {},
}));
vi.mock("@/hooks/useConnection", () => ({
	useConnection: () => ({
		recordingState: "idle" as const,
		connectionStatus: "connected" as const,
		lastError: null,
		handleRetryConnection: () => {},
	}),
}));
vi.mock("@/hooks/useTheme", () => ({
	useTheme: () => ({
		themeMode: "system" as const,
		handleThemeChange: () => {},
		reloadThemeFromConfig: () => {},
		textSize: 14,
		setTextSize: () => {},
	}),
}));
vi.mock("@/hooks/useSoundFeedback", () => ({ useSoundFeedback: () => {} }));
vi.mock("@/hooks/usePluginCatalog", () => ({
	usePluginsAvailable: () => false,
}));

vi.mock("@/components/layout/Sidebar", () => ({
	Sidebar: () => <nav data-testid="sidebar" />,
}));
vi.mock("@/components/layout/TitleBar", () => ({
	TitleBar: () => <div data-testid="titlebar" />,
}));
vi.mock("@/router/PageSwitch", () => ({
	PageSwitch: () => <div data-testid="page" />,
}));
vi.mock("@/components/skullet/AppSkulletProvider", () => ({
	AppSkulletProvider: ({ children }: { children: React.ReactNode }) => (
		<>{children}</>
	),
}));
vi.mock("@/components/ui/sonner", () => ({ Toaster: () => null }));
vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		dismiss: vi.fn(),
	},
	Toaster: () => null,
}));
vi.mock("next-themes", () => ({
	useTheme: () => ({ theme: "light" as const }),
}));
vi.mock("@/components/debug/DebugPanel", () => ({ DebugPanel: () => null }));
vi.mock("@/components/consent/ConsentGateDialog", () => ({
	default: () => null,
}));
vi.mock("@/components/help/HelpOverlay", () => ({ HelpOverlay: () => null }));
vi.mock("@/components/common/A11yLiveRegions", () => ({
	A11yLiveRegions: () => null,
}));

vi.mock("@hugeicons/react", () => ({ HugeiconsIcon: () => <span /> }));
vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

import { ensureLocaleLoaded, setLocale } from "@/i18n/i18n";

describe("RTL shell layout: sidebar stays on the physical left", () => {
	beforeEach(async () => {
		await act(async () => {
			setLocale("en");
			await ensureLocaleLoaded("ar");
		});
	});

	afterEach(() => {
		act(() => {
			setLocale("en");
		});
		cleanup();
	});

	it("pins the row LTR, the main column RTL, and the sidebar as the row's first child under dir=rtl", async () => {
		await act(async () => {
			setLocale("ar");
		});
		expect(document.documentElement.dir).toBe("rtl");

		const { default: App } = await import("@/App");
		render(<App />);

		const sidebar = screen.getByTestId("sidebar");
		const row = sidebar.parentElement;
		expect(row).toBeTruthy();
		// (a) The row never mirrors, so the sidebar keeps its physical side.
		expect(row?.getAttribute("dir")).toBe("ltr");
		// (c) Sidebar is the row's first element child in every locale.
		expect(row?.firstElementChild).toBe(sidebar);

		// (b) Only the main column follows the document direction.
		const mainColumn = row?.children[1] as HTMLElement | undefined;
		expect(mainColumn).toBeTruthy();
		expect(mainColumn?.getAttribute("dir")).toBe("rtl");

		// (d) Logical border/radius classes mirror with the column direction.
		const main = mainColumn?.querySelector("main");
		expect(main).toBeTruthy();
		expect(main?.classList.contains("rounded-s-lg")).toBe(true);
		expect(main?.classList.contains("border-s")).toBe(true);
		expect(main?.classList.contains("rounded-l-lg")).toBe(false);
		expect(main?.classList.contains("border-l")).toBe(false);
	});

	it("keeps the row LTR and the sidebar first even in an LTR locale", async () => {
		await act(async () => {
			setLocale("en");
		});
		const { default: App } = await import("@/App");
		render(<App />);

		const sidebar = screen.getByTestId("sidebar");
		const row = sidebar.parentElement;
		expect(row?.getAttribute("dir")).toBe("ltr");
		expect(row?.firstElementChild).toBe(sidebar);
		const mainColumn = row?.children[1] as HTMLElement | undefined;
		expect(mainColumn?.getAttribute("dir")).toBe("ltr");
	});
});
